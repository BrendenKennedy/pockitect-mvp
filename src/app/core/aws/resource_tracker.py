"""
AWS Resource Tracker

Tracks all AWS resources created by Pockitect for reliable cleanup.
Uses both:
1. Local JSON file for persistence across test runs
2. AWS resource tags for cloud-native tracking
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)

POCKITECT_TAG_KEY = "pockitect:managed"
POCKITECT_TAG_VALUE = "true"
POCKITECT_PROJECT_TAG = "pockitect:project"
POCKITECT_CREATED_TAG = "pockitect:created"


@dataclass
class TrackedResource:
    resource_type: str
    resource_id: str
    region: str
    project_name: str
    created_at: str
    arn: Optional[str] = None
    name: Optional[str] = None
    parent_id: Optional[str] = None
    status: str = "active"


@dataclass
class ResourceRegistry:
    resources: list[TrackedResource] = field(default_factory=list)
    last_updated: str = ""

    def add(self, resource: TrackedResource):
        for existing in self.resources:
            if existing.resource_id == resource.resource_id and existing.region == resource.region:
                existing.status = resource.status
                existing.name = resource.name or existing.name
                return
        self.resources.append(resource)
        self.last_updated = datetime.utcnow().isoformat()

    def mark_deleted(self, resource_id: str, region: str = None):
        for r in self.resources:
            if r.resource_id == resource_id:
                if region is None or r.region == region:
                    r.status = "deleted"
                    self.last_updated = datetime.utcnow().isoformat()
                    return True
        return False

    def get_active(
        self,
        resource_type: str = None,
        region: str = None,
        project: str = None,
    ) -> list[TrackedResource]:
        result = []
        for r in self.resources:
            if r.status == "deleted":
                continue
            if resource_type and r.resource_type != resource_type:
                continue
            if region and r.region != region:
                continue
            if project and r.project_name != project:
                continue
            result.append(r)
        return result

    def to_dict(self) -> dict:
        return {
            "resources": [asdict(r) for r in self.resources],
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceRegistry":
        registry = cls()
        registry.last_updated = data.get("last_updated", "")
        for r in data.get("resources", []):
            registry.resources.append(TrackedResource(**r))
        return registry


class ResourceTracker:
    DEFAULT_REGISTRY_PATH = Path.home() / ".pockitect" / "resource_registry.json"

    def __init__(self, registry_path: Path = None, session: boto3.Session = None):
        self.registry_path = registry_path or self.DEFAULT_REGISTRY_PATH
        self.registry = self._load_registry()
        self._clients = {}
        self._session = session or get_session()

    def _load_registry(self) -> ResourceRegistry:
        if self.registry_path.exists():
            try:
                with open(self.registry_path) as f:
                    data = json.load(f)
                return ResourceRegistry.from_dict(data)
            except Exception as e:
                logger.warning(f"Could not load registry: {e}")
        return ResourceRegistry()

    def _save_registry(self):
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump(self.registry.to_dict(), f, indent=2)

    def _get_client(self, service: str, region: str):
        key = (service, region)
        if key not in self._clients:
            self._clients[key] = self._session.client(service, region_name=region)
        return self._clients[key]

    def track(
        self,
        resource_type: str,
        resource_id: str,
        region: str,
        project_name: str,
        arn: str = None,
        name: str = None,
        parent_id: str = None,
    ) -> TrackedResource:
        resource = TrackedResource(
            resource_type=resource_type,
            resource_id=resource_id,
            region=region,
            project_name=project_name,
            created_at=datetime.utcnow().isoformat(),
            arn=arn,
            name=name,
            parent_id=parent_id,
        )

        self.registry.add(resource)
        self._save_registry()
        self._tag_resource(resource)

        logger.info(f"Tracked {resource_type}: {resource_id} in {region}")
        return resource

    def _tag_resource(self, resource: TrackedResource):
        tags = [
            {"Key": POCKITECT_TAG_KEY, "Value": POCKITECT_TAG_VALUE},
            {"Key": POCKITECT_PROJECT_TAG, "Value": resource.project_name},
            {"Key": POCKITECT_CREATED_TAG, "Value": resource.created_at},
        ]

        try:
            if resource.resource_type in [
                "ec2_instance",
                "vpc",
                "subnet",
                "security_group",
                "internet_gateway",
                "route_table",
                "key_pair",
            ]:
                ec2 = self._get_client("ec2", resource.region)
                ec2.create_tags(Resources=[resource.resource_id], Tags=tags)
            elif resource.resource_type == "s3_bucket":
                s3 = self._get_client("s3", resource.region)
                s3.put_bucket_tagging(
                    Bucket=resource.resource_id,
                    Tagging={"TagSet": tags},
                )
            elif resource.resource_type in ["iam_role", "instance_profile"]:
                iam = self._get_client("iam", resource.region)
                if resource.resource_type == "iam_role":
                    iam.tag_role(RoleName=resource.resource_id, Tags=tags)
                else:
                    iam.tag_instance_profile(
                        InstanceProfileName=resource.resource_id,
                        Tags=tags,
                    )
            elif resource.resource_type == "rds_instance" and resource.arn:
                rds = self._get_client("rds", resource.region)
                rds.add_tags_to_resource(ResourceName=resource.arn, Tags=tags)
        except ClientError as e:
            logger.warning(
                f"Could not tag {resource.resource_type} {resource.resource_id}: {e}"
            )

    def mark_deleted(self, resource_id: str, region: str = None):
        if self.registry.mark_deleted(resource_id, region):
            self._save_registry()
            logger.info(f"Marked deleted: {resource_id}")

    def get_active_resources(
        self,
        resource_type: str = None,
        region: str = None,
        project: str = None,
    ) -> list[TrackedResource]:
        return self.registry.get_active(resource_type, region, project)

    def scan_aws_for_pockitect_resources(
        self, regions: list[str] = None
    ) -> list[TrackedResource]:
        if regions is None:
            regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        found = []

        for region in regions:
            logger.info(f"Scanning {region} for Pockitect resources...")
            ec2 = self._get_client("ec2", region)

            try:
                instances = ec2.describe_instances(
                    Filters=[
                        {"Name": f"tag:{POCKITECT_TAG_KEY}", "Values": [POCKITECT_TAG_VALUE]}
                    ]
                )
                for res in instances.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        if inst["State"]["Name"] not in ["terminated", "shutting-down"]:
                            project = self._get_tag(inst.get("Tags", []), POCKITECT_PROJECT_TAG)
                            found.append(
                                TrackedResource(
                                    resource_type="ec2_instance",
                                    resource_id=inst["InstanceId"],
                                    region=region,
                                    project_name=project or "unknown",
                                    created_at=self._get_tag(
                                        inst.get("Tags", []), POCKITECT_CREATED_TAG
                                    )
                                    or "",
                                    name=self._get_tag(inst.get("Tags", []), "Name"),
                                )
                            )
            except ClientError as e:
                logger.warning(f"Could not scan instances in {region}: {e}")

            try:
                vpcs = ec2.describe_vpcs(
                    Filters=[
                        {"Name": f"tag:{POCKITECT_TAG_KEY}", "Values": [POCKITECT_TAG_VALUE]}
                    ]
                )
                for vpc in vpcs.get("Vpcs", []):
                    project = self._get_tag(vpc.get("Tags", []), POCKITECT_PROJECT_TAG)
                    found.append(
                        TrackedResource(
                            resource_type="vpc",
                            resource_id=vpc["VpcId"],
                            region=region,
                            project_name=project or "unknown",
                            created_at=self._get_tag(
                                vpc.get("Tags", []), POCKITECT_CREATED_TAG
                            )
                            or "",
                            name=self._get_tag(vpc.get("Tags", []), "Name"),
                        )
                    )
            except ClientError as e:
                logger.warning(f"Could not scan VPCs in {region}: {e}")

            try:
                sgs = ec2.describe_security_groups(
                    Filters=[
                        {"Name": f"tag:{POCKITECT_TAG_KEY}", "Values": [POCKITECT_TAG_VALUE]}
                    ]
                )
                for sg in sgs.get("SecurityGroups", []):
                    project = self._get_tag(sg.get("Tags", []), POCKITECT_PROJECT_TAG)
                    found.append(
                        TrackedResource(
                            resource_type="security_group",
                            resource_id=sg["GroupId"],
                            region=region,
                            project_name=project or "unknown",
                            created_at=self._get_tag(
                                sg.get("Tags", []), POCKITECT_CREATED_TAG
                            )
                            or "",
                            name=sg.get("GroupName"),
                            parent_id=sg.get("VpcId"),
                        )
                    )
            except ClientError as e:
                logger.warning(f"Could not scan security groups in {region}: {e}")

            try:
                subnets = ec2.describe_subnets(
                    Filters=[
                        {"Name": f"tag:{POCKITECT_TAG_KEY}", "Values": [POCKITECT_TAG_VALUE]}
                    ]
                )
                for sub in subnets.get("Subnets", []):
                    project = self._get_tag(sub.get("Tags", []), POCKITECT_PROJECT_TAG)
                    found.append(
                        TrackedResource(
                            resource_type="subnet",
                            resource_id=sub["SubnetId"],
                            region=region,
                            project_name=project or "unknown",
                            created_at=self._get_tag(
                                sub.get("Tags", []), POCKITECT_CREATED_TAG
                            )
                            or "",
                            name=self._get_tag(sub.get("Tags", []), "Name"),
                            parent_id=sub.get("VpcId"),
                        )
                    )
            except ClientError as e:
                logger.warning(f"Could not scan subnets in {region}: {e}")

        for r in found:
            self.registry.add(r)
        self._save_registry()

        return found

    def _get_tag(self, tags: list, key: str) -> Optional[str]:
        for tag in tags:
            if tag.get("Key") == key:
                return tag.get("Value")
        return None
