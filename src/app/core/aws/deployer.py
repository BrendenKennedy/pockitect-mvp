import asyncio
import logging
from typing import Dict, Any, Callable, Optional

import yaml

from app.core.redis_client import RedisClient
from app.core.aws.credentials_helper import get_session
from app.core.aws.ami_resolver import AmiResolver
from app.core.aws.resources import AWSResourceManager

logger = logging.getLogger(__name__)

class ResourceDeployer:
    def __init__(self, region_name: str = 'us-east-1'):
        self.region_name = region_name
        self.session = get_session(region_name=region_name)
        self.redis = RedisClient()
        self.manager: Optional[AWSResourceManager] = None

    async def deploy(self, template_path: str, progress_callback: Optional[Callable] = None):
        """
        Deploy resources defined in a YAML template.
        """
        try:
            with open(template_path, 'r') as f:
                template = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load template: {e}")

        project_name = template.get('project', {}).get('name', 'unnamed')
        region = template.get('project', {}).get('region', self.region_name)
        
        # Update session if region differs
        if region != self.region_name:
            self.region_name = region
            self.session = get_session(region_name=region)
        self.manager = AWSResourceManager(region, project_name=project_name)

        resources = template.get('resources', {})
        total_steps = len(resources)
        current_step = 0

        # Context to pass IDs between steps (e.g. vpc_id -> subnet)
        context = {}

        # Simple dependency ordering: VPC -> Subnet -> SG -> EC2
        # A real topological sort would be better, but this is MVP.
        ordered_types = ['vpc', 'subnet', 'security_group', 'ec2_instance', 's3_bucket']
        
        # Helper to find resource by type in template
        sorted_resources = []
        for r_type in ordered_types:
            for name, config in resources.items():
                if config.get('type') == r_type:
                    sorted_resources.append((name, config))

        for name, config in sorted_resources:
            current_step += 1
            msg = f"Deploying {name} ({config['type']})..."
            if progress_callback:
                progress_callback(msg, step=current_step, total=total_steps)

            try:
                # Run sync deployment step in thread
                result = await asyncio.to_thread(self._deploy_resource, name, config, context)
                
                # Update context with outputs
                if result:
                    context.update(result)

                    resource_id = result.get(f"{name}.id")
                    self.redis.publish_status(
                        "resource_status",
                        data={
                            "project": project_name,
                            "region": region,
                            "resource_name": name,
                            "resource_type": config.get("type"),
                            "resource_id": resource_id,
                            "status": "created",
                        },
                        status="success",
                    )
                    logger.info(f"Deployed {name}: {result}")

            except Exception as e:
                self.redis.publish_status(
                    "resource_status",
                    data={
                        "project": project_name,
                        "region": region,
                        "resource_name": name,
                        "resource_type": config.get("type"),
                        "status": "failed",
                        "error": str(e),
                    },
                    status="error",
                )
                logger.error(f"Failed to deploy {name}: {e}")
                raise e

    def _deploy_resource(self, name: str, config: Dict, context: Dict) -> Dict:
        """
        Sync function to deploy a single resource.
        Returns a dict of outputs (e.g. {'vpc_id': 'vpc-123'}).
        """
        r_type = config.get('type')
        manager = self.manager
        if not manager:
            raise RuntimeError("Resource manager not initialized.")

        if r_type == 'vpc':
            cidr = config.get('properties', {}).get('cidr_block', '10.0.0.0/16')
            result = manager.create_vpc(cidr, name)
            if not result.success:
                raise ValueError(result.error or "Failed to create VPC")
            vpc_id = result.resource_id
            return {f"{name}.id": vpc_id, 'vpc_id': vpc_id}

        elif r_type == 'subnet':
            vpc_id = context.get('vpc_id') or config.get('properties', {}).get('vpc_id')
            if not vpc_id:
                raise ValueError("Subnet requires vpc_id")
            cidr = config.get('properties', {}).get('cidr_block', '10.0.1.0/24')
            existing = manager.ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "cidr-block", "Values": [cidr]}]
            ).get("Subnets", [])
            if existing:
                subnet_id = existing[0]["SubnetId"]
                return {f"{name}.id": subnet_id, 'subnet_id': subnet_id}
            result = manager.create_subnet(vpc_id=vpc_id, cidr_block=cidr, name=name)
            if not result.success and result.error:
                if "InvalidSubnet.Conflict" in result.error or "InvalidSubnet.Range" in result.error:
                    from app.core.aws.managed_vpc_service import ManagedVpcService

                    svc = ManagedVpcService()
                    vpc_cidr = None
                    try:
                        vpc_cidr = manager.ec2.describe_vpcs(VpcIds=[vpc_id]).get("Vpcs", [{}])[0].get("CidrBlock")
                    except Exception:
                        vpc_cidr = None
                    alt_cidr = svc.pick_available_subnet_cidr(self.region_name, vpc_id, vpc_cidr) if vpc_cidr else None
                    if alt_cidr:
                        result = manager.create_subnet(vpc_id=vpc_id, cidr_block=alt_cidr, name=name)
            if not result.success:
                raise ValueError(result.error or "Failed to create subnet")
            subnet_id = result.resource_id
            return {f"{name}.id": subnet_id, 'subnet_id': subnet_id}

        elif r_type == 'security_group':
            vpc_id = context.get('vpc_id') or config.get('properties', {}).get('vpc_id')
            desc = config.get('properties', {}).get('description', 'Managed by Pockitect')
            group_name = config.get('properties', {}).get('name') or name
            existing = manager.ec2.describe_security_groups(
                Filters=[
                    {"Name": "group-name", "Values": [group_name]},
                    {"Name": "vpc-id", "Values": [vpc_id]},
                ]
            ).get("SecurityGroups", [])
            if existing:
                sg_id = existing[0]["GroupId"]
                return {f"{name}.id": sg_id, 'security_group_id': sg_id}
            rules = config.get('properties', {}).get('ingress', [])
            result = manager.create_security_group(
                vpc_id=vpc_id,
                name=group_name,
                description=desc,
                rules=rules,
            )
            if not result.success:
                raise ValueError(result.error or "Failed to create security group")
            sg_id = result.resource_id
            return {f"{name}.id": sg_id, 'security_group_id': sg_id}

        elif r_type == 'ec2_instance':
            image_id = config.get('properties', {}).get('image_id')
            instance_type = config.get('properties', {}).get('instance_type', 't2.micro')
            subnet_id = context.get('subnet_id')
            sg_id = context.get('security_group_id')
            resolver = AmiResolver(self.session, self.region_name)
            image_id = resolver.resolve(image_id)
            if not image_id:
                raise ValueError("No AMI resolved for ec2_instance; set compute.image_id")
            if not subnet_id or not sg_id:
                raise ValueError("EC2 instance requires subnet_id and security_group_id")

            result = manager.launch_instance(
                image_id=image_id,
                instance_type=instance_type,
                subnet_id=subnet_id,
                security_group_id=sg_id,
                name=name,
            )
            if not result.success:
                raise ValueError(result.error or "Failed to launch instance")
            instance_id = result.resource_id
            return {f"{name}.id": instance_id, 'instance_id': instance_id}

        elif r_type == 's3_bucket':
            bucket_name = config.get('properties', {}).get('name', name)
            result = manager.create_bucket(bucket_name)
            if not result.success:
                raise ValueError(result.error or "Failed to create bucket")
            return {f"{name}.id": bucket_name, 'bucket_name': bucket_name}

        return {}
