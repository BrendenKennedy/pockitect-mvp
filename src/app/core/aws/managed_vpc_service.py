import json
import logging
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import WORKSPACE_ROOT
from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)

MANAGED_ENVS = ("prod", "dev", "test")


@dataclass
class VpcInfo:
    vpc_id: str
    cidr_block: str
    name: str
    tags: Dict[str, str]


class ManagedVpcService:
    def __init__(self):
        self.mapping_path = WORKSPACE_ROOT / "data" / "managed_vpcs.json"

    def load_mapping(self) -> Dict[str, Dict[str, str]]:
        try:
            payload = json.loads(self.mapping_path.read_text(encoding="utf-8"))
            return payload.get("regions", {})
        except Exception:
            return {}

    def save_mapping(self, mapping: Dict[str, Dict[str, str]]) -> None:
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"regions": mapping}
        self.mapping_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_vpcs(self, region: str) -> List[VpcInfo]:
        try:
            session = get_session(region_name=region)
            ec2 = session.client("ec2", region_name=region)
            resp = ec2.describe_vpcs()
            vpcs = []
            for vpc in resp.get("Vpcs", []):
                tags = {t.get("Key"): t.get("Value") for t in vpc.get("Tags", [])}
                vpcs.append(
                    VpcInfo(
                        vpc_id=vpc["VpcId"],
                        cidr_block=vpc.get("CidrBlock", ""),
                        name=tags.get("Name", ""),
                        tags=tags,
                    )
                )
            return vpcs
        except Exception as exc:
            logger.error("Failed to list VPCs in %s: %s", region, exc)
            return []

    def find_managed_vpcs(self, region: str) -> Dict[str, str]:
        managed = {}
        for vpc in self.list_vpcs(region):
            env = vpc.tags.get("pockitect:managed_vpc")
            if env in MANAGED_ENVS:
                managed[env] = vpc.vpc_id
        return managed

    def ensure_vpc(self, region: str, env: str, cidr_block: str) -> Optional[str]:
        session = get_session(region_name=region)
        ec2 = session.client("ec2", region_name=region)
        name = f"pockitect-{env}"
        tags = [
            {"Key": "Name", "Value": name},
            {"Key": "pockitect:managed_vpc", "Value": env},
            {"Key": "pockitect:managed", "Value": "true"},
        ]
        try:
            logger.info("Creating managed VPC %s in %s with CIDR %s", env, region, cidr_block)
            resp = ec2.create_vpc(
                CidrBlock=cidr_block,
                TagSpecifications=[{"ResourceType": "vpc", "Tags": tags}],
            )
            vpc_id = resp["Vpc"]["VpcId"]
            waiter = ec2.get_waiter("vpc_available")
            waiter.wait(VpcIds=[vpc_id])
            ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})
            return vpc_id
        except Exception as exc:
            logger.error("Failed to create managed VPC %s in %s: %s", env, region, exc)
            return None

    def default_cidr_for_env(self, env: str) -> str:
        if env == "prod":
            return "10.0.0.0/16"
        if env == "dev":
            return "10.1.0.0/16"
        return "10.2.0.0/16"

    def get_vpc_cidr(self, region: str, vpc_id: str) -> Optional[str]:
        try:
            session = get_session(region_name=region)
            ec2 = session.client("ec2", region_name=region)
            resp = ec2.describe_vpcs(VpcIds=[vpc_id])
            vpcs = resp.get("Vpcs") or []
            if not vpcs:
                return None
            return vpcs[0].get("CidrBlock")
        except Exception as exc:
            logger.error("Failed to fetch VPC CIDR for %s in %s: %s", vpc_id, region, exc)
            return None

    def pick_subnet_cidr(self, vpc_cidr: str, preferred_prefix: int = 24) -> Optional[str]:
        try:
            network = ipaddress.ip_network(vpc_cidr, strict=False)
            prefix = preferred_prefix
            if prefix < network.prefixlen:
                prefix = network.prefixlen
            subnets = list(network.subnets(new_prefix=prefix))
            if not subnets:
                return None
            return str(subnets[1] if len(subnets) > 1 else subnets[0])
        except Exception as exc:
            logger.error("Failed to derive subnet CIDR from %s: %s", vpc_cidr, exc)
            return None

    def pick_available_subnet_cidr(
        self, region: str, vpc_id: str, vpc_cidr: str, preferred_prefix: int = 24
    ) -> Optional[str]:
        try:
            session = get_session(region_name=region)
            ec2 = session.client("ec2", region_name=region)
            resp = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
            existing = []
            for sn in resp.get("Subnets", []):
                cidr = sn.get("CidrBlock")
                if cidr:
                    existing.append(ipaddress.ip_network(cidr, strict=False))

            network = ipaddress.ip_network(vpc_cidr, strict=False)
            prefix = preferred_prefix
            if prefix < network.prefixlen:
                prefix = network.prefixlen
            for candidate in network.subnets(new_prefix=prefix):
                if all(not candidate.overlaps(exist) for exist in existing):
                    return str(candidate)
            return None
        except Exception as exc:
            logger.error(
                "Failed to pick available subnet CIDR for %s in %s: %s", vpc_id, region, exc
            )
            return None
