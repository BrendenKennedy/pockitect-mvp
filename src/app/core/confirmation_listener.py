import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from botocore.exceptions import ClientError

from app.core.config import CHANNEL_STATUS
from app.core.redis_client import PubSubManager, RedisClient
from app.core.aws.credentials_helper import get_session
from app.core.aws.resources import AWSResourceManager
from app.core.task_manager import get_executor

logger = logging.getLogger(__name__)


class ConfirmationListener:
    """
    Listens for completion events and confirms AWS state before emitting final status events.
    """

    def __init__(self):
        self.redis = RedisClient()
        self._executor = get_executor()
        self.pubsub_manager: Optional[PubSubManager] = None
        self._terminate_errors: Dict[str, List[str]] = {}

    def start(self):
        if self.pubsub_manager:
            return
        self.pubsub_manager = PubSubManager([CHANNEL_STATUS], self._handle_message)
        self.pubsub_manager.start()
        logger.info("ConfirmationListener started.")

    def stop(self):
        if self.pubsub_manager:
            self.pubsub_manager.stop()
            self.pubsub_manager = None

    def _handle_message(self, channel: str, data: Any):
        if channel != CHANNEL_STATUS or not isinstance(data, dict):
            return
        event_type = data.get("type")
        status = data.get("status")
        request_id = data.get("request_id")

        if event_type == "terminate_error":
            if request_id:
                errors = self._terminate_errors.setdefault(request_id, [])
                payload = data.get("data", {}) or {}
                res_id = payload.get("resource_id", "unknown")
                error = payload.get("error", "unknown error")
                errors.append(f"{res_id}: {error}")
            return

        if event_type == "terminate_complete":
            self._executor.submit(self._run_async, self._confirm_terminate_async(data))
            return

        if event_type == "power" and status == "success":
            self._executor.submit(self._run_async, self._confirm_power_async(data))
            return

        if event_type == "deploy" and status == "success":
            self._executor.submit(self._run_async, self._confirm_deploy_async(data))
            return

    def _run_async(self, coro: asyncio.Future):
        asyncio.run(coro)

    async def _confirm_terminate_async(self, event: Dict[str, Any]):
        request_id = event.get("request_id")
        payload = event.get("data", {}) or {}
        resources = payload.get("resources") or []
        project = payload.get("project")

        confirmed: List[str] = []
        shared: List[str] = []
        failed: List[str] = []
        errors: List[str] = list(self._terminate_errors.pop(request_id, []))

        for res in resources:
            res_id = res.get("id")
            res_type = res.get("type")
            region = res.get("region")
            if not res_id or not res_type or not region:
                failed.append(res_id or "unknown")
                errors.append(f"{res_id or 'unknown'}: missing resource metadata")
                continue
            try:
                outcome = await self._wait_for_termination(
                    res_id, res_type, region, project
                )
                if outcome == "deleted":
                    confirmed.append(res_id)
                elif outcome == "shared":
                    shared.append(res_id)
                elif outcome == "ignored":
                    confirmed.append(res_id)
                else:
                    failed.append(res_id)
                    errors.append(f"{res_id}: still present")
            except Exception as exc:
                failed.append(res_id)
                errors.append(f"{res_id}: {exc}")

        if failed:
            self.redis.publish_status(
                "terminate_confirm_error",
                data={
                    "project": project,
                    "confirmed_ids": confirmed,
                    "shared_ids": shared,
                    "failed_ids": failed,
                    "errors": errors,
                },
                request_id=request_id,
                status="error",
            )
            return

        confirmed_resources = [r for r in resources if r.get("id") in confirmed]
        shared_resources = [r for r in resources if r.get("id") in shared]
        self.redis.publish_status(
            "terminate_confirmed",
            data={
                "project": project,
                "confirmed_ids": confirmed,
                "shared_ids": shared,
                "confirmed_resources": confirmed_resources,
                "shared_resources": shared_resources,
            },
            request_id=request_id,
            status="success",
        )

    async def _confirm_power_async(self, event: Dict[str, Any]):
        request_id = event.get("request_id")
        payload = event.get("data", {}) or {}
        action = payload.get("action")
        resources = payload.get("resources") or []
        project = payload.get("project")

        confirmed: List[str] = []
        failed: List[str] = []
        errors: List[str] = []

        for res in resources:
            res_id = res.get("id")
            res_type = res.get("type")
            region = res.get("region")
            if not res_id or not res_type or not region:
                failed.append(res_id or "unknown")
                errors.append(f"{res_id or 'unknown'}: missing resource metadata")
                continue
            try:
                if await self._wait_for_power_state(res_id, res_type, region, action):
                    confirmed.append(res_id)
                else:
                    failed.append(res_id)
                    errors.append(f"{res_id}: state mismatch")
            except Exception as exc:
                failed.append(res_id)
                errors.append(f"{res_id}: {exc}")

        if failed:
            self.redis.publish_status(
                "power_confirm_error",
                data={
                    "project": project,
                    "action": action,
                    "confirmed_ids": confirmed,
                    "failed_ids": failed,
                    "errors": errors,
                    "error": "Power confirmation failed.",
                    "resources": resources,
                },
                request_id=request_id,
                status="error",
            )
            return

        self.redis.publish_status(
            "power_confirmed",
            data={
                "project": project,
                "action": action,
                "confirmed_ids": confirmed,
                "message": "Power action confirmed.",
                "resources": resources,
            },
            request_id=request_id,
            status="success",
        )

    async def _confirm_deploy_async(self, event: Dict[str, Any]):
        request_id = event.get("request_id")
        payload = event.get("data", {}) or {}
        project = payload.get("project")
        region = payload.get("region")
        expected = payload.get("expected_resource_types") or []

        found_types = await self._wait_for_deploy_resources(project, region, expected)
        missing = [r for r in expected if r not in found_types]

        if missing:
            self.redis.publish_status(
                "deploy_confirm_error",
                data={
                    "project": project,
                    "region": region,
                    "expected_resource_types": expected,
                    "found_resource_types": sorted(found_types),
                    "missing_resource_types": missing,
                    "error": "Deployment confirmation failed.",
                },
                request_id=request_id,
                status="error",
            )
            return

        self.redis.publish_status(
            "deploy_confirmed",
            data={
                "project": project,
                "region": region,
                "expected_resource_types": expected,
                "found_resource_types": sorted(found_types),
                "message": "Deployment confirmed.",
            },
            request_id=request_id,
            status="success",
        )

    def _check_terminated_resource(
        self, resource_id: str, resource_type: str, region: str, project: Optional[str]
    ) -> str:
        exists, tags = self._fetch_resource_tags(resource_id, resource_type, region)
        if not exists:
            return "deleted"

        project_tags = self._split_project_tags(tags.get("pockitect:project"))
        if not project:
            return "exists"
        if not project_tags:
            return "ignored"
        if project not in project_tags:
            return "ignored"
        if len(project_tags) > 1:
            return "shared"
        return "exists"

    def _check_power_state(self, resource_id: str, resource_type: str, region: str, action: str) -> bool:
        manager = AWSResourceManager(region, enable_tracking=False)
        if resource_type == "ec2_instance":
            result = manager.get_instance_status(resource_id)
            if not result.success:
                raise RuntimeError(result.error or "instance status lookup failed")
            expected = "running" if action == "start" else "stopped"
            return result.data.get("state") == expected
        if resource_type == "rds_instance":
            result = manager.get_db_status(resource_id)
            if not result.success:
                raise RuntimeError(result.error or "db status lookup failed")
            expected = "available" if action == "start" else "stopped"
            return result.data.get("status") == expected
        raise RuntimeError(f"unsupported power resource: {resource_type}")

    async def _wait_for_termination(
        self,
        resource_id: str,
        resource_type: str,
        region: str,
        project: Optional[str],
        timeout: int = 900,
        interval: float = 5.0,
    ) -> str:
        start = time.monotonic()
        current_interval = interval
        while True:
            outcome = self._check_terminated_resource(resource_id, resource_type, region, project)
            if outcome in ("deleted", "shared", "ignored"):
                return outcome
            if time.monotonic() - start >= timeout:
                return "timeout"
            await asyncio.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 30.0)

    async def _wait_for_power_state(
        self,
        resource_id: str,
        resource_type: str,
        region: str,
        action: str,
        timeout: int = 600,
        interval: float = 5.0,
    ) -> bool:
        start = time.monotonic()
        current_interval = interval
        last_error: Optional[Exception] = None
        while True:
            try:
                if self._check_power_state(resource_id, resource_type, region, action):
                    return True
            except Exception as exc:
                last_error = exc
            if time.monotonic() - start >= timeout:
                if last_error:
                    raise last_error
                return False
            await asyncio.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 30.0)

    async def _wait_for_deploy_resources(
        self,
        project: Optional[str],
        region: Optional[str],
        expected: List[str],
        timeout: int = 900,
        interval: float = 10.0,
    ) -> Set[str]:
        start = time.monotonic()
        current_interval = interval
        found: Set[str] = set()
        while True:
            found = self._find_deployed_resource_types(project, region, expected)
            if all(resource in found for resource in expected):
                return found
            if time.monotonic() - start >= timeout:
                return found
            await asyncio.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 45.0)

    def _find_deployed_resource_types(
        self, project: Optional[str], region: Optional[str], expected: List[str]
    ) -> Set[str]:
        if not project:
            return set()
        found: Set[str] = set()
        region = region or "us-east-1"
        session = get_session(region_name=region)
        ec2 = session.client("ec2", region_name=region)

        if "ec2_instance" in expected:
            for inst in self._describe_ec2_instances(ec2):
                if self._tag_matches_project(inst.get("Tags", []), project):
                    found.add("ec2_instance")
                    break

        if "vpc" in expected:
            resp = ec2.describe_vpcs(Filters=[{"Name": "tag-key", "Values": ["pockitect:project"]}])
            for vpc in resp.get("Vpcs", []):
                if self._tag_matches_project(vpc.get("Tags", []), project):
                    found.add("vpc")
                    break

        if "subnet" in expected:
            resp = ec2.describe_subnets(Filters=[{"Name": "tag-key", "Values": ["pockitect:project"]}])
            for subnet in resp.get("Subnets", []):
                if self._tag_matches_project(subnet.get("Tags", []), project):
                    found.add("subnet")
                    break

        if "security_group" in expected:
            resp = ec2.describe_security_groups(Filters=[{"Name": "tag-key", "Values": ["pockitect:project"]}])
            for sg in resp.get("SecurityGroups", []):
                if self._tag_matches_project(sg.get("Tags", []), project):
                    found.add("security_group")
                    break

        if "s3_bucket" in expected:
            session_global = get_session()
            s3 = session_global.client("s3")
            for bucket in s3.list_buckets().get("Buckets", []):
                name = bucket.get("Name")
                if not name:
                    continue
                tags = self._get_s3_tags(s3, name)
                if self._tag_matches_project_dict(tags, project):
                    found.add("s3_bucket")
                    break

        return found

    def _describe_ec2_instances(self, ec2_client) -> List[Dict[str, Any]]:
        instances: List[Dict[str, Any]] = []
        paginator = ec2_client.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instances.append(inst)
        return instances

    def _fetch_resource_tags(
        self, resource_id: str, resource_type: str, region: str
    ) -> Tuple[bool, Dict[str, str]]:
        session = get_session(region_name=region)

        try:
            if resource_type == "ec2_instance":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_instances(InstanceIds=[resource_id])
                if not resp.get("Reservations"):
                    return False, {}
                inst = resp["Reservations"][0]["Instances"][0]
                state = inst.get("State", {}).get("Name")
                if state in ("terminated", "shutting-down"):
                    return False, {}
                return True, self._parse_tag_list(inst.get("Tags", []))

            if resource_type == "vpc":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_vpcs(VpcIds=[resource_id])
                if not resp.get("Vpcs"):
                    return False, {}
                return True, self._parse_tag_list(resp["Vpcs"][0].get("Tags", []))

            if resource_type == "subnet":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_subnets(SubnetIds=[resource_id])
                if not resp.get("Subnets"):
                    return False, {}
                return True, self._parse_tag_list(resp["Subnets"][0].get("Tags", []))

            if resource_type == "security_group":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_security_groups(GroupIds=[resource_id])
                if not resp.get("SecurityGroups"):
                    return False, {}
                return True, self._parse_tag_list(resp["SecurityGroups"][0].get("Tags", []))

            if resource_type == "network_interface":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_network_interfaces(NetworkInterfaceIds=[resource_id])
                if not resp.get("NetworkInterfaces"):
                    return False, {}
                return True, self._parse_tag_list(resp["NetworkInterfaces"][0].get("TagSet", []))

            if resource_type == "internet_gateway":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_internet_gateways(InternetGatewayIds=[resource_id])
                if not resp.get("InternetGateways"):
                    return False, {}
                return True, self._parse_tag_list(resp["InternetGateways"][0].get("Tags", []))

            if resource_type == "route_table":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_route_tables(RouteTableIds=[resource_id])
                if not resp.get("RouteTables"):
                    return False, {}
                return True, self._parse_tag_list(resp["RouteTables"][0].get("Tags", []))

            if resource_type == "vpc_endpoint":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_vpc_endpoints(VpcEndpointIds=[resource_id])
                if not resp.get("VpcEndpoints"):
                    return False, {}
                return True, self._parse_tag_list(resp["VpcEndpoints"][0].get("Tags", []))

            if resource_type == "vpc_peering_connection":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_vpc_peering_connections(
                    VpcPeeringConnectionIds=[resource_id]
                )
                if not resp.get("VpcPeeringConnections"):
                    return False, {}
                return True, self._parse_tag_list(resp["VpcPeeringConnections"][0].get("Tags", []))

            if resource_type == "nat_gateway":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_nat_gateways(NatGatewayIds=[resource_id])
                if not resp.get("NatGateways"):
                    return False, {}
                state = resp["NatGateways"][0].get("State")
                if state == "deleted":
                    return False, {}
                return True, self._parse_tag_list(resp["NatGateways"][0].get("Tags", []))

            if resource_type == "elastic_ip":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_addresses(PublicIps=[resource_id])
                if not resp.get("Addresses"):
                    return False, {}
                return True, self._parse_tag_list(resp["Addresses"][0].get("Tags", []))

            if resource_type == "ebs_volume":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_volumes(VolumeIds=[resource_id])
                if not resp.get("Volumes"):
                    return False, {}
                state = resp["Volumes"][0].get("State")
                if state == "deleted":
                    return False, {}
                return True, self._parse_tag_list(resp["Volumes"][0].get("Tags", []))

            if resource_type == "rds_instance":
                rds = session.client("rds", region_name=region)
                resp = rds.describe_db_instances(DBInstanceIdentifier=resource_id)
                if not resp.get("DBInstances"):
                    return False, {}
                db = resp["DBInstances"][0]
                arn = db.get("DBInstanceArn")
                tags = {}
                if arn:
                    tag_resp = rds.list_tags_for_resource(ResourceName=arn)
                    tags = self._parse_tag_list(tag_resp.get("TagList", []))
                return True, tags

            if resource_type == "s3_bucket":
                session_global = get_session()
                s3 = session_global.client("s3")
                if not self._s3_exists(s3, resource_id):
                    return False, {}
                return True, self._get_s3_tags(s3, resource_id)

            if resource_type == "iam_role":
                session_global = get_session()
                iam = session_global.client("iam")
                try:
                    iam.get_role(RoleName=resource_id)
                except ClientError as exc:
                    if self._is_not_found_error(exc):
                        return False, {}
                    raise
                tag_resp = iam.list_role_tags(RoleName=resource_id)
                return True, self._parse_tag_list(tag_resp.get("Tags", []))

            if resource_type == "instance_profile":
                session_global = get_session()
                iam = session_global.client("iam")
                try:
                    iam.get_instance_profile(InstanceProfileName=resource_id)
                except ClientError as exc:
                    if self._is_not_found_error(exc):
                        return False, {}
                    raise
                tag_resp = iam.list_instance_profile_tags(InstanceProfileName=resource_id)
                return True, self._parse_tag_list(tag_resp.get("Tags", []))

            if resource_type == "key_pair":
                ec2 = session.client("ec2", region_name=region)
                resp = ec2.describe_key_pairs(KeyPairIds=[resource_id])
                if not resp.get("KeyPairs"):
                    return False, {}
                return True, self._parse_tag_list(resp["KeyPairs"][0].get("Tags", []))

        except ClientError as exc:
            if self._is_not_found_error(exc):
                return False, {}
            raise

        return True, {}

    def _parse_tag_list(self, tags: List[Dict[str, Any]]) -> Dict[str, str]:
        return {t.get("Key"): t.get("Value") for t in tags if t.get("Key")}

    def _split_project_tags(self, value: Optional[str]) -> Set[str]:
        if not value:
            return set()
        return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}

    def _tag_matches_project(self, tags: List[Dict[str, Any]], project: str) -> bool:
        parsed = self._parse_tag_list(tags)
        return project in self._split_project_tags(parsed.get("pockitect:project"))

    def _tag_matches_project_dict(self, tags: Dict[str, str], project: str) -> bool:
        return project in self._split_project_tags(tags.get("pockitect:project"))

    def _s3_exists(self, s3_client, bucket: str) -> bool:
        try:
            s3_client.head_bucket(Bucket=bucket)
            return True
        except ClientError as exc:
            if self._is_not_found_error(exc):
                return False
            raise

    def _get_s3_tags(self, s3_client, bucket: str) -> Dict[str, str]:
        try:
            resp = s3_client.get_bucket_tagging(Bucket=bucket)
            return self._parse_tag_list(resp.get("TagSet", []))
        except ClientError as exc:
            if "NoSuchTagSet" in str(exc):
                return {}
            if self._is_not_found_error(exc):
                return {}
            raise

    def _is_not_found_error(self, exc: ClientError) -> bool:
        code = exc.response.get("Error", {}).get("Code", "")
        message = str(exc)
        return any(
            token in code or token in message
            for token in ["NotFound", "Invalid", "NoSuch", "404", "NotExist"]
        )
