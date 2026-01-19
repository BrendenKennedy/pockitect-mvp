import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Set

import boto3

from app.core.aws.credentials_helper import get_session
from app.core.aws.deleter import ResourceDeleter

logger = logging.getLogger(__name__)


@dataclass
class ResourceNode:
    id: str
    type: str
    region: str


class ChildFinder:
    """Helper to find dependent children of a resource."""

    def __init__(self, session: boto3.Session):
        self.session = session

    def find_children(self, parent_id: str, parent_type: str, region: str) -> List[ResourceNode]:
        children: List[ResourceNode] = []
        ec2 = self.session.client("ec2", region_name=region)

        if parent_type == "vpc":
            try:
                asg = self.session.client("autoscaling", region_name=region)
                my_subnets = set()
                sn_resp = ec2.describe_subnets(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                )
                for sn in sn_resp["Subnets"]:
                    my_subnets.add(sn["SubnetId"])

                if my_subnets:
                    paginator = asg.get_paginator("describe_auto_scaling_groups")
                    for page in paginator.paginate():
                        for group in page["AutoScalingGroups"]:
                            asg_subnets = group.get("VPCZoneIdentifier", "").split(",")
                            if any(s in my_subnets for s in asg_subnets if s):
                                children.append(
                                    ResourceNode(group["AutoScalingGroupName"], "autoscaling_group", region)
                                )
            except Exception:
                pass

            try:
                elbv2 = self.session.client("elbv2", region_name=region)
                paginator = elbv2.get_paginator("describe_load_balancers")
                for page in paginator.paginate():
                    for lb in page["LoadBalancers"]:
                        if lb.get("VpcId") == parent_id:
                            children.append(
                                ResourceNode(lb["LoadBalancerArn"], "load_balancer_v2", region)
                            )
            except Exception:
                pass

            try:
                elb = self.session.client("elb", region_name=region)
                all_elbs = elb.describe_load_balancers()
                for lb in all_elbs["LoadBalancerDescriptions"]:
                    if lb.get("VPCId") == parent_id:
                        children.append(
                            ResourceNode(lb["LoadBalancerName"], "load_balancer_v1", region)
                        )
            except Exception:
                pass

            try:
                eps = ec2.describe_vpc_endpoints(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                )
                for ep in eps["VpcEndpoints"]:
                    children.append(ResourceNode(ep["VpcEndpointId"], "vpc_endpoint", region))
            except Exception:
                pass

            try:
                pcxs = ec2.describe_vpc_peering_connections(
                    Filters=[{"Name": "requester-vpc-info.vpc-id", "Values": [parent_id]}]
                )
                for pcx in pcxs["VpcPeeringConnections"]:
                    if pcx["Status"]["Code"] != "deleted":
                        children.append(
                            ResourceNode(pcx["VpcPeeringConnectionId"], "vpc_peering_connection", region)
                        )
            except Exception:
                pass

            try:
                pcxs = ec2.describe_vpc_peering_connections(
                    Filters=[{"Name": "accepter-vpc-info.vpc-id", "Values": [parent_id]}]
                )
                for pcx in pcxs["VpcPeeringConnections"]:
                    if pcx["Status"]["Code"] != "deleted":
                        children.append(
                            ResourceNode(pcx["VpcPeeringConnectionId"], "vpc_peering_connection", region)
                        )
            except Exception:
                pass

            try:
                paginator = ec2.get_paginator("describe_subnets")
                for page in paginator.paginate(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                ):
                    for sn in page["Subnets"]:
                        children.append(ResourceNode(sn["SubnetId"], "subnet", region))
            except Exception:
                pass

            try:
                igws = ec2.describe_internet_gateways(
                    Filters=[{"Name": "attachment.vpc-id", "Values": [parent_id]}]
                )
                for igw in igws["InternetGateways"]:
                    children.append(
                        ResourceNode(igw["InternetGatewayId"], "internet_gateway", region)
                    )
            except Exception:
                pass

            try:
                sgs = ec2.describe_security_groups(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                )
                for sg in sgs["SecurityGroups"]:
                    if sg["GroupName"] != "default":
                        children.append(ResourceNode(sg["GroupId"], "security_group", region))
            except Exception:
                pass

            try:
                nacls = ec2.describe_network_acls(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                )
                for nacl in nacls["NetworkAcls"]:
                    if not nacl["IsDefault"]:
                        children.append(ResourceNode(nacl["NetworkAclId"], "network_acl", region))
            except Exception:
                pass

            try:
                rts = ec2.describe_route_tables(
                    Filters=[{"Name": "vpc-id", "Values": [parent_id]}]
                )
                for rt in rts["RouteTables"]:
                    is_main = any(assoc.get("Main", False) for assoc in rt.get("Associations", []))
                    if not is_main:
                        children.append(ResourceNode(rt["RouteTableId"], "route_table", region))
            except Exception:
                pass

        elif parent_type == "subnet":
            try:
                paginator = ec2.get_paginator("describe_instances")
                for page in paginator.paginate(
                    Filters=[{"Name": "subnet-id", "Values": [parent_id]}]
                ):
                    for res in page["Reservations"]:
                        for inst in res["Instances"]:
                            if inst["State"]["Name"] != "terminated":
                                children.append(
                                    ResourceNode(inst["InstanceId"], "ec2_instance", region)
                                )
            except Exception:
                pass

            try:
                nats = ec2.describe_nat_gateways(
                    Filters=[{"Name": "subnet-id", "Values": [parent_id]}]
                )
                for nat in nats["NatGateways"]:
                    if nat["State"] != "deleted":
                        children.append(ResourceNode(nat["NatGatewayId"], "nat_gateway", region))
            except Exception:
                pass

            try:
                enis = ec2.describe_network_interfaces(
                    Filters=[{"Name": "subnet-id", "Values": [parent_id]}]
                )
                for eni in enis["NetworkInterfaces"]:
                    children.append(
                        ResourceNode(eni["NetworkInterfaceId"], "network_interface", region)
                    )
            except Exception:
                pass

        return children


class RecursiveDeleter:
    """Deletes a resource tree by first deleting children."""

    def __init__(
        self,
        access_key: str = None,
        secret_key: str = None,
        session: boto3.Session = None,
    ):
        if session:
            self.session = session
        elif access_key and secret_key:
            self.session = get_session(
                access_key=access_key,
                secret_key=secret_key,
            )
        else:
            self.session = get_session()

        self.deleter = ResourceDeleter(session=self.session)
        self.finder = ChildFinder(self.session)
        self.deleted_cache: Set[str] = set()

    def delete_tree(
        self,
        resource_id: str,
        resource_type: str,
        region: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        if resource_id in self.deleted_cache:
            return True

        if callback:
            callback(f"Scanning dependencies for {resource_type} {resource_id}...")

        children = self.finder.find_children(resource_id, resource_type, region)

        if children and callback:
            callback(
                f"Found {len(children)} dependencies for {resource_type} {resource_id}. Cleaning up..."
            )

        for child in children:
            self.delete_tree(child.id, child.type, child.region, callback)

        if callback:
            callback(f"Deleting {resource_type} {resource_id}...")

        try:
            self.deleter.delete_resource(resource_id, resource_type, region)
            self.deleted_cache.add(resource_id)
            return True
        except Exception as e:
            if "Invalid" in str(e) or "NotFound" in str(e) or "does not exist" in str(e):
                self.deleted_cache.add(resource_id)
                return True

            if callback:
                callback(f"Failed to delete {resource_id}: {e}")
            raise
