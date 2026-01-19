import asyncio
import logging
import boto3
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any

from app.core.redis_client import RedisClient
from app.core.config import KEY_ALL_RESOURCES, CHANNEL_RESOURCE_UPDATE
from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)

# Standard AWS regions to scan
ALL_REGIONS = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-central-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-north-1',
    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'ap-southeast-1', 'ap-southeast-2', 'ap-south-1',
    'ca-central-1', 'sa-east-1'
]

@dataclass
class ScannedResource:
    id: str
    type: str
    region: str
    name: Optional[str] = None
    state: Optional[str] = None
    details: Dict = field(default_factory=dict)
    tags: Dict = field(default_factory=dict)

class ResourceScanner:
    def __init__(self, region_name: str = None):
        self.session = get_session(region_name=region_name)
        self.redis = RedisClient()

    async def scan_all(self, regions: List[str] = None) -> List[Dict]:
        """
        Scans all regions concurrently and updates Redis.
        """
        regions = regions or ALL_REGIONS
        tasks = []

        # 1. Global Resources (scan once, usually us-east-1 or global endpoint)
        tasks.append(self._scan_global_resources())

        # 2. Regional Resources
        for region in regions:
            tasks.append(self._scan_region(region))

        # Run all scans
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_resources = []
        for res in results_list:
            if isinstance(res, list):
                all_resources.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Scan error: {res}")

        # Bulk update Redis
        # We store each resource in the hash 'all_resources' with key = resource_id
        # Note: ID collisions across regions/types are possible, so we should prefix keys
        for res in all_resources:
            key = f"{res['region']}:{res['type']}:{res['id']}"
            self.redis.hset_json(KEY_ALL_RESOURCES, key, res)
            
        # Optional: Publish individual updates if needed (could be noisy for full scan)
        # self.redis.publish(CHANNEL_RESOURCE_UPDATE, {"count": len(all_resources)})
        
        return all_resources

    async def _scan_global_resources(self) -> List[Dict]:
        """Scan global resources like S3 and IAM."""
        return await asyncio.to_thread(self._scan_global_sync)

    def _scan_global_sync(self) -> List[Dict]:
        resources = []
        try:
            # S3
            s3 = self.session.client('s3')
            for bucket in s3.list_buckets().get('Buckets', []):
                res = ScannedResource(
                    id=bucket['Name'],
                    type='s3_bucket',
                    region='global',
                    name=bucket['Name'],
                    state='active',
                    details={'creation_date': bucket['CreationDate'].isoformat()}
                )
                resources.append(asdict(res))
        except Exception as e:
            logger.warning(f"S3 scan error: {e}")

        try:
            # IAM
            iam = self.session.client('iam')
            paginator = iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page.get('Roles', []):
                    res = ScannedResource(
                        id=role['RoleName'],
                        type='iam_role',
                        region='global',
                        name=role['RoleName'],
                        state='active',
                        details={'arn': role['Arn']}
                    )
                    resources.append(asdict(res))
        except Exception as e:
            logger.warning(f"IAM scan error: {e}")

        return resources

    async def _scan_region(self, region: str) -> List[Dict]:
        """Scan a specific region."""
        return await asyncio.to_thread(self._scan_region_sync, region)

    def _scan_region_sync(self, region: str) -> List[Dict]:
        resources = []
        try:
            ec2 = self.session.client('ec2', region_name=region)
            rds = self.session.client('rds', region_name=region)

            # EC2 Instances
            try:
                paginator = ec2.get_paginator('describe_instances')
                for page in paginator.paginate():
                    for reservation in page['Reservations']:
                        for inst in reservation['Instances']:
                            if inst['State']['Name'] == 'terminated':
                                continue
                            name = self._get_tag_value(inst.get('Tags', []), 'Name')
                            res = ScannedResource(
                                id=inst['InstanceId'],
                                type='ec2_instance',
                                region=region,
                                name=name,
                                state=inst['State']['Name'],
                                details={
                                    'type': inst['InstanceType'],
                                    'public_ip': inst.get('PublicIpAddress'),
                                    'vpc_id': inst.get('VpcId')
                                },
                                tags=self._parse_tags(inst.get('Tags', []))
                            )
                            resources.append(asdict(res))
            except Exception:
                pass

            # VPCs
            try:
                for vpc in ec2.describe_vpcs().get('Vpcs', []):
                    name = self._get_tag_value(vpc.get('Tags', []), 'Name')
                    res = ScannedResource(
                        id=vpc['VpcId'],
                        type='vpc',
                        region=region,
                        name=name,
                        state=vpc['State'],
                        details={'cidr': vpc['CidrBlock']},
                        tags=self._parse_tags(vpc.get('Tags', []))
                    )
                    resources.append(asdict(res))
            except Exception:
                pass
            
            # RDS
            try:
                for db in rds.describe_db_instances().get('DBInstances', []):
                    res = ScannedResource(
                        id=db['DBInstanceIdentifier'],
                        type='rds_instance',
                        region=region,
                        name=db['DBInstanceIdentifier'],
                        state=db['DBInstanceStatus'],
                        details={'engine': db['Engine'], 'class': db['DBInstanceClass']}
                    )
                    resources.append(asdict(res))
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Region scan error {region}: {e}")

        return resources

    def _get_tag_value(self, tags: List[Dict], key: str) -> Optional[str]:
        for tag in tags:
            if tag['Key'] == key:
                return tag['Value']
        return None

    def _parse_tags(self, tags: List[Dict]) -> Dict:
        return {t['Key']: t['Value'] for t in tags}
