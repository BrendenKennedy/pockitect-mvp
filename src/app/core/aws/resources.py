"""
Boto3 Wrapper for AWS Resource Management

Provides create/read/delete functions for each resource type used by Pockitect.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)


@dataclass
class ResourceResult:
    """Result of a resource operation."""

    success: bool
    resource_id: Optional[str] = None
    arn: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict] = None


class AWSResourceManager:
    """
    Manager for AWS resource operations.

    All methods return ResourceResult for consistent error handling.
    """

    def __init__(self, region: str, project_name: str = None, enable_tracking: bool = True):
        self.region = region
        self.project_name = project_name or "unknown"
        self._session = get_session(region_name=region)
        self._ec2 = None
        self._rds = None
        self._s3 = None
        self._iam = None

        self._tracker = None
        if enable_tracking:
            try:
                from app.core.aws.resource_tracker import ResourceTracker

                self._tracker = ResourceTracker()
            except Exception as e:
                logger.warning(f"Could not initialize resource tracker: {e}")

    def _track(
        self,
        resource_type: str,
        resource_id: str,
        name: str = None,
        arn: str = None,
        parent_id: str = None,
    ):
        if self._tracker:
            try:
                self._tracker.track(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    region=self.region,
                    project_name=self.project_name,
                    name=name,
                    arn=arn,
                    parent_id=parent_id,
                )
            except Exception as e:
                logger.warning(f"Could not track resource: {e}")

    def _build_tags(self, name: Optional[str] = None) -> list[dict]:
        tags = [{"Key": "ManagedBy", "Value": "Pockitect"}]
        if name:
            tags.append({"Key": "Name", "Value": name})
        if self.project_name:
            tags.append({"Key": "pockitect:project", "Value": self.project_name})
        return tags

    def _untrack(self, resource_id: str):
        if self._tracker:
            try:
                self._tracker.mark_deleted(resource_id, self.region)
            except Exception as e:
                logger.warning(f"Could not untrack resource: {e}")

    @property
    def ec2(self):
        if self._ec2 is None:
            self._ec2 = self._session.client("ec2", region_name=self.region)
        return self._ec2

    @property
    def rds(self):
        if self._rds is None:
            self._rds = self._session.client("rds", region_name=self.region)
        return self._rds

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = self._session.client("s3", region_name=self.region)
        return self._s3

    @property
    def iam(self):
        if self._iam is None:
            self._iam = self._session.client("iam", region_name=self.region)
        return self._iam

    def create_vpc(self, cidr_block: str, name: str) -> ResourceResult:
        try:
            response = self.ec2.create_vpc(
                CidrBlock=cidr_block,
                TagSpecifications=[
                    {"ResourceType": "vpc", "Tags": self._build_tags(name)}
                ],
            )
            vpc_id = response["Vpc"]["VpcId"]

            waiter = self.ec2.get_waiter("vpc_available")
            waiter.wait(VpcIds=[vpc_id])

            self.ec2.modify_vpc_attribute(
                VpcId=vpc_id,
                EnableDnsHostnames={"Value": True},
            )

            self._track("vpc", vpc_id, name=name)

            logger.info(f"Created VPC: {vpc_id}")
            return ResourceResult(success=True, resource_id=vpc_id)
        except ClientError as e:
            logger.error(f"Failed to create VPC: {e}")
            return ResourceResult(success=False, error=str(e))

    def get_default_vpc(self, preferred_azs: list[str] = None) -> ResourceResult:
        try:
            response = self.ec2.describe_vpcs(
                Filters=[{"Name": "is-default", "Values": ["true"]}]
            )

            if not response["Vpcs"]:
                return ResourceResult(success=False, error="No default VPC found")

            vpc_id = response["Vpcs"][0]["VpcId"]

            subnet_response = self.ec2.describe_subnets(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "default-for-az", "Values": ["true"]},
                ]
            )

            subnets = subnet_response.get("Subnets", [])
            if not subnets:
                return ResourceResult(success=False, error="No default subnet found")

            if preferred_azs is None:
                preferred_azs = ["a", "b", "c", "d"]

            def az_priority(subnet):
                az = subnet.get("AvailabilityZone", "")
                suffix = az[-1] if az else "z"
                if suffix in preferred_azs:
                    return preferred_azs.index(suffix)
                return 99

            subnets_sorted = sorted(subnets, key=az_priority)
            subnet_id = subnets_sorted[0]["SubnetId"]
            chosen_az = subnets_sorted[0].get("AvailabilityZone")

            logger.info(f"Selected default subnet {subnet_id} in {chosen_az}")

            return ResourceResult(
                success=True,
                resource_id=vpc_id,
                data={"subnet_id": subnet_id, "availability_zone": chosen_az},
            )
        except ClientError as e:
            logger.error(f"Failed to get default VPC: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_vpc(self, vpc_id: str) -> ResourceResult:
        try:
            self.ec2.delete_vpc(VpcId=vpc_id)
            logger.info(f"Deleted VPC: {vpc_id}")
            return ResourceResult(success=True, resource_id=vpc_id)
        except ClientError as e:
            logger.error(f"Failed to delete VPC: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_subnet(
        self,
        vpc_id: str,
        cidr_block: str,
        name: str,
        availability_zone: Optional[str] = None,
        map_public_ip: bool = True,
    ) -> ResourceResult:
        try:
            params = {
                "VpcId": vpc_id,
                "CidrBlock": cidr_block,
                "TagSpecifications": [
                    {"ResourceType": "subnet", "Tags": self._build_tags(name)}
                ],
            }

            if availability_zone:
                params["AvailabilityZone"] = availability_zone

            response = self.ec2.create_subnet(**params)
            subnet_id = response["Subnet"]["SubnetId"]

            if map_public_ip:
                self.ec2.modify_subnet_attribute(
                    SubnetId=subnet_id,
                    MapPublicIpOnLaunch={"Value": True},
                )

            self._track("subnet", subnet_id, name=name, parent_id=vpc_id)

            logger.info(f"Created subnet: {subnet_id}")
            return ResourceResult(success=True, resource_id=subnet_id)
        except ClientError as e:
            logger.error(f"Failed to create subnet: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_subnet(self, subnet_id: str) -> ResourceResult:
        try:
            self.ec2.delete_subnet(SubnetId=subnet_id)
            self._untrack(subnet_id)
            logger.info(f"Deleted subnet: {subnet_id}")
            return ResourceResult(success=True, resource_id=subnet_id)
        except ClientError as e:
            logger.error(f"Failed to delete subnet: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_security_group(
        self,
        vpc_id: str,
        name: str,
        description: str,
        rules: list[dict],
    ) -> ResourceResult:
        try:
            response = self.ec2.create_security_group(
                GroupName=name,
                Description=description,
                VpcId=vpc_id,
                TagSpecifications=[
                    {
                        "ResourceType": "security-group",
                        "Tags": self._build_tags(name),
                    }
                ],
            )
            sg_id = response["GroupId"]

            if rules:
                ip_permissions = []
                for rule in rules:
                    port = rule.get("port")
                    from_port = rule.get("from_port", port)
                    to_port = rule.get("to_port", port)
                    if from_port is None or to_port is None:
                        continue
                    ip_permissions.append(
                        {
                            "IpProtocol": rule.get("protocol", "tcp"),
                            "FromPort": int(from_port),
                            "ToPort": int(to_port),
                            "IpRanges": [
                                {
                                    "CidrIp": rule.get("cidr", "0.0.0.0/0"),
                                    "Description": rule.get("description", ""),
                                }
                            ],
                        }
                    )

                self.ec2.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=ip_permissions,
                )

            self._track("security_group", sg_id, name=name, parent_id=vpc_id)

            logger.info(f"Created security group: {sg_id}")
            return ResourceResult(success=True, resource_id=sg_id)
        except ClientError as e:
            logger.error(f"Failed to create security group: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_security_group(self, group_id: str) -> ResourceResult:
        try:
            self.ec2.delete_security_group(GroupId=group_id)
            self._untrack(group_id)
            logger.info(f"Deleted security group: {group_id}")
            return ResourceResult(success=True, resource_id=group_id)
        except ClientError as e:
            logger.error(f"Failed to delete security group: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_key_pair(self, name: str, save_path: Optional[Path] = None) -> ResourceResult:
        try:
            try:
                existing = self.ec2.describe_key_pairs(KeyNames=[name])
                if existing.get("KeyPairs"):
                    logger.info(f"Key pair '{name}' already exists. Deleting old one...")
                    try:
                        self.ec2.delete_key_pair(KeyName=name)
                        time.sleep(2)
                    except ClientError as del_e:
                        logger.warning(f"Failed to delete existing key pair: {del_e}")
            except ClientError as e:
                if "InvalidKeyPair.NotFound" not in str(e):
                    logger.warning(f"Error checking for existing key pair: {e}")

            response = self.ec2.create_key_pair(
                KeyName=name,
                KeyType="ed25519",
                TagSpecifications=[
                    {"ResourceType": "key-pair", "Tags": [{"Key": "Name", "Value": name}]}
                ],
            )

            key_pair_id = response["KeyPairId"]
            private_key = response["KeyMaterial"]

            if save_path is None:
                save_path = Path.home() / ".ssh"

            save_path.mkdir(parents=True, exist_ok=True)
            key_file = save_path / f"{name}.pem"

            key_file.write_text(private_key)
            key_file.chmod(0o600)

            logger.info(f"Created key pair: {key_pair_id}, saved to {key_file}")
            return ResourceResult(
                success=True,
                resource_id=key_pair_id,
                data={
                    "key_name": name,
                    "key_file": str(key_file),
                    "private_key_pem": private_key,
                },
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "InvalidKeyPair.Duplicate":
                logger.warning("Key pair duplicate detected, retrying after delay...")
                time.sleep(3)
                try:
                    try:
                        self.ec2.delete_key_pair(KeyName=name)
                        time.sleep(2)
                    except ClientError:
                        pass
                    response = self.ec2.create_key_pair(
                        KeyName=name,
                        KeyType="ed25519",
                        TagSpecifications=[
                            {"ResourceType": "key-pair", "Tags": [{"Key": "Name", "Value": name}]}
                        ],
                    )
                    key_pair_id = response["KeyPairId"]
                    private_key = response["KeyMaterial"]

                    if save_path is None:
                        save_path = Path.home() / ".ssh"
                    save_path.mkdir(parents=True, exist_ok=True)
                    key_file = save_path / f"{name}.pem"
                    key_file.write_text(private_key)
                    key_file.chmod(0o600)

                    logger.info(f"Created key pair after retry: {key_pair_id}")
                    return ResourceResult(
                        success=True,
                        resource_id=key_pair_id,
                        data={
                            "key_name": name,
                            "key_file": str(key_file),
                            "private_key_pem": private_key,
                        },
                    )
                except Exception as retry_e:
                    logger.error(f"Failed to create key pair after retry: {retry_e}")
                    return ResourceResult(success=False, error=str(retry_e))

            logger.error(f"Failed to create key pair: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_key_pair(self, name: str) -> ResourceResult:
        try:
            self.ec2.delete_key_pair(KeyName=name)
            logger.info(f"Deleted key pair: {name}")
            return ResourceResult(success=True)
        except ClientError as e:
            logger.error(f"Failed to delete key pair: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_instance_role(
        self,
        role_name: str,
        s3_access: bool = False,
        rds_access: bool = False,
    ) -> ResourceResult:
        try:
            try:
                existing_role = self.iam.get_role(RoleName=role_name)
                logger.info(f"IAM role {role_name} already exists, deleting it first")
                self.delete_instance_role(role_name)
            except ClientError as e:
                if "NoSuchEntity" not in str(e):
                    raise

            assume_role_policy = """{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }"""

            tags = [
                {"Key": "ManagedBy", "Value": "Pockitect"},
                {"Key": "pockitect:project", "Value": self.project_name},
            ]

            role_response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=assume_role_policy,
                Description="Pockitect managed EC2 instance role",
                Tags=tags,
            )
            role_arn = role_response["Role"]["Arn"]

            policies = ["arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"]

            if s3_access:
                s3_policy = """{
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                        "Resource": "*"
                    }]
                }"""
                self.iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="PockitectS3Access",
                    PolicyDocument=s3_policy,
                )

            if rds_access:
                policies.append("arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess")

            for policy_arn in policies:
                try:
                    self.iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
                except ClientError:
                    pass

            profile_name = f"{role_name}-profile"
            try:
                self.iam.create_instance_profile(InstanceProfileName=profile_name)
            except ClientError as e:
                if "EntityAlreadyExists" not in str(e):
                    raise

            try:
                self.iam.add_role_to_instance_profile(
                    InstanceProfileName=profile_name,
                    RoleName=role_name,
                )
            except ClientError as e:
                if "LimitExceeded" not in str(e):
                    raise

            time.sleep(10)

            profile_response = self.iam.get_instance_profile(
                InstanceProfileName=profile_name
            )
            profile_arn = profile_response["InstanceProfile"]["Arn"]

            self._track("iam_role", role_name, name=role_name, arn=role_arn)

            logger.info(f"Created IAM role: {role_name}")
            return ResourceResult(
                success=True,
                resource_id=role_name,
                arn=role_arn,
                data={"instance_profile_arn": profile_arn},
            )
        except ClientError as e:
            logger.error(f"Failed to create IAM role: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_instance_role(self, role_name: str) -> ResourceResult:
        try:
            profile_name = f"{role_name}-profile"
            try:
                self.iam.remove_role_from_instance_profile(
                    InstanceProfileName=profile_name,
                    RoleName=role_name,
                )
            except ClientError:
                pass

            try:
                self.iam.delete_instance_profile(InstanceProfileName=profile_name)
            except ClientError:
                pass

            attached = self.iam.list_attached_role_policies(RoleName=role_name)
            for policy in attached.get("AttachedPolicies", []):
                self.iam.detach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy["PolicyArn"],
                )

            inline = self.iam.list_role_policies(RoleName=role_name)
            for policy_name in inline.get("PolicyNames", []):
                self.iam.delete_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                )

            self.iam.delete_role(RoleName=role_name)

            logger.info(f"Deleted IAM role: {role_name}")
            return ResourceResult(success=True, resource_id=role_name)
        except ClientError as e:
            logger.error(f"Failed to delete IAM role: {e}")
            return ResourceResult(success=False, error=str(e))

    def launch_instance(
        self,
        image_id: str,
        instance_type: str,
        subnet_id: str,
        security_group_id: str,
        key_name: Optional[str] = None,
        instance_profile_arn: Optional[str] = None,
        user_data: str = "",
        name: str = "Pockitect Instance",
    ) -> ResourceResult:
        try:
            params = {
                "ImageId": image_id,
                "InstanceType": instance_type,
                "MinCount": 1,
                "MaxCount": 1,
                "SubnetId": subnet_id,
                "SecurityGroupIds": [security_group_id],
                "TagSpecifications": [
                    {
                        "ResourceType": "instance",
                        "Tags": self._build_tags(name),
                    }
                ],
            }

            if key_name:
                params["KeyName"] = key_name

            if instance_profile_arn:
                params["IamInstanceProfile"] = {"Arn": instance_profile_arn}

            if user_data:
                params["UserData"] = user_data

            response = self.ec2.run_instances(**params)
            instance_id = response["Instances"][0]["InstanceId"]

            self._track("ec2_instance", instance_id, name=name, parent_id=subnet_id)

            logger.info(f"Launched instance: {instance_id}")
            return ResourceResult(success=True, resource_id=instance_id)
        except ClientError as e:
            logger.error(f"Failed to launch instance: {e}")
            return ResourceResult(success=False, error=str(e))

    def get_instance_status(self, instance_id: str, retries: int = 5) -> ResourceResult:
        for attempt in range(retries):
            try:
                response = self.ec2.describe_instances(InstanceIds=[instance_id])

                if not response["Reservations"]:
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
                    return ResourceResult(success=False, error="Instance not found")

                instance = response["Reservations"][0]["Instances"][0]

                return ResourceResult(
                    success=True,
                    resource_id=instance_id,
                    data={
                        "state": instance["State"]["Name"],
                        "public_ip": instance.get("PublicIpAddress"),
                        "private_ip": instance.get("PrivateIpAddress"),
                        "public_dns": instance.get("PublicDnsName"),
                    },
                )
            except ClientError as e:
                if "InvalidInstanceID.NotFound" in str(e) and attempt < retries - 1:
                    time.sleep(2)
                    continue
                logger.error(f"Failed to get instance status: {e}")
                return ResourceResult(success=False, error=str(e))

        return ResourceResult(success=False, error="Instance not found after retries")

    def terminate_instance(self, instance_id: str) -> ResourceResult:
        try:
            self.ec2.terminate_instances(InstanceIds=[instance_id])
            self._untrack(instance_id)
            logger.info(f"Terminated instance: {instance_id}")
            return ResourceResult(success=True, resource_id=instance_id)
        except ClientError as e:
            logger.error(f"Failed to terminate instance: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_db_instance(
        self,
        identifier: str,
        engine: str,
        instance_class: str,
        allocated_storage: int,
        master_username: str,
        master_password: str,
        vpc_security_group_id: str,
        subnet_group_name: Optional[str] = None,
    ) -> ResourceResult:
        try:
            params = {
                "DBInstanceIdentifier": identifier,
                "Engine": engine,
                "DBInstanceClass": instance_class,
                "AllocatedStorage": allocated_storage,
                "MasterUsername": master_username,
                "MasterUserPassword": master_password,
                "VpcSecurityGroupIds": [vpc_security_group_id],
                "PubliclyAccessible": False,
                "StorageType": "gp2",
                "Tags": [
                    {"Key": "Name", "Value": identifier},
                    {"Key": "ManagedBy", "Value": "Pockitect"},
                ],
            }

            if subnet_group_name:
                params["DBSubnetGroupName"] = subnet_group_name

            response = self.rds.create_db_instance(**params)
            db_id = response["DBInstance"]["DBInstanceIdentifier"]

            logger.info(f"Creating RDS instance: {db_id}")
            return ResourceResult(success=True, resource_id=db_id)
        except ClientError as e:
            logger.error(f"Failed to create RDS instance: {e}")
            return ResourceResult(success=False, error=str(e))

    def get_db_status(self, identifier: str) -> ResourceResult:
        try:
            response = self.rds.describe_db_instances(DBInstanceIdentifier=identifier)

            if not response["DBInstances"]:
                return ResourceResult(success=False, error="DB instance not found")

            db = response["DBInstances"][0]

            return ResourceResult(
                success=True,
                resource_id=identifier,
                data={
                    "status": db["DBInstanceStatus"],
                    "endpoint": db.get("Endpoint", {}).get("Address"),
                    "port": db.get("Endpoint", {}).get("Port"),
                    "engine": db["Engine"],
                },
            )
        except ClientError as e:
            logger.error(f"Failed to get DB status: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_db_instance(self, identifier: str, skip_snapshot: bool = True) -> ResourceResult:
        try:
            params = {
                "DBInstanceIdentifier": identifier,
                "SkipFinalSnapshot": skip_snapshot,
                "DeleteAutomatedBackups": True,
            }

            self.rds.delete_db_instance(**params)
            logger.info(f"Deleting RDS instance: {identifier}")
            return ResourceResult(success=True, resource_id=identifier)
        except ClientError as e:
            logger.error(f"Failed to delete RDS instance: {e}")
            return ResourceResult(success=False, error=str(e))

    def create_bucket(self, bucket_name: str) -> ResourceResult:
        try:
            if self.region == "us-east-1":
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            self.s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )

            self.s3.put_bucket_tagging(
                Bucket=bucket_name,
                Tagging={"TagSet": self._build_tags(bucket_name)},
            )

            bucket_arn = f"arn:aws:s3:::{bucket_name}"

            self._track("s3_bucket", bucket_name, name=bucket_name, arn=bucket_arn)

            logger.info(f"Created S3 bucket: {bucket_name}")
            return ResourceResult(success=True, resource_id=bucket_name, arn=bucket_arn)
        except ClientError as e:
            logger.error(f"Failed to create S3 bucket: {e}")
            return ResourceResult(success=False, error=str(e))

    def delete_bucket(self, bucket_name: str, force: bool = False) -> ResourceResult:
        try:
            if force:
                s3_resource = boto3.resource("s3", region_name=self.region)
                bucket = s3_resource.Bucket(bucket_name)
                bucket.objects.all().delete()

            self.s3.delete_bucket(Bucket=bucket_name)
            self._untrack(bucket_name)
            logger.info(f"Deleted S3 bucket: {bucket_name}")
            return ResourceResult(success=True, resource_id=bucket_name)
        except ClientError as e:
            logger.error(f"Failed to delete S3 bucket: {e}")
            return ResourceResult(success=False, error=str(e))
