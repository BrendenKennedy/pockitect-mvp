import boto3
import logging
from botocore.exceptions import ClientError

from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)


class ResourceDeleter:
    """Helper to delete arbitrary AWS resources by ID and region."""

    def __init__(
        self,
        access_key: str = None,
        secret_key: str = None,
        session: boto3.Session = None,
    ):
        if session:
            self._session = session
        elif access_key and secret_key:
            self._session = get_session(
                access_key=access_key,
                secret_key=secret_key,
            )
        else:
            self._session = get_session()

    def delete_resource(self, resource_id: str, resource_type: str, region: str) -> bool:
        """
        Delete a resource.
        Returns True if successful. Raises ClientError on failure.
        """
        try:
            if resource_type == "ec2_instance":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.terminate_instances(InstanceIds=[resource_id])
                logger.info(f"Terminating EC2 instance {resource_id} in {region}")
                try:
                    waiter = ec2.get_waiter("instance_terminated")
                    waiter.wait(InstanceIds=[resource_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60})
                    logger.info(f"Instance {resource_id} successfully terminated")
                except Exception as e:
                    # Verify actual state before giving up
                    try:
                        resp = ec2.describe_instances(InstanceIds=[resource_id])
                        if resp.get("Reservations"):
                            inst = resp["Reservations"][0]["Instances"][0]
                            state = inst.get("State", {}).get("Name")
                            if state == "terminated":
                                logger.info(f"Instance {resource_id} is terminated (verified after waiter timeout)")
                                return True
                            else:
                                logger.warning(f"Instance {resource_id} waiter timeout, current state: {state}")
                                raise ClientError(
                                    {"Error": {"Code": "InstanceNotTerminated"}},
                                    f"Instance {resource_id} termination incomplete, current state: {state}"
                                )
                        else:
                            # Instance not found - assume terminated
                            logger.info(f"Instance {resource_id} not found, assuming terminated")
                            return True
                    except ClientError:
                        raise
                    except Exception as verify_error:
                        logger.error(f"Failed to verify instance state after waiter timeout: {verify_error}")
                        raise ClientError(
                            {"Error": {"Code": "TerminationTimeout"}},
                            f"Instance {resource_id} termination timeout, verification failed: {e}"
                        )
                return True

            if resource_type == "vpc":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_vpc(VpcId=resource_id)
                logger.info(f"Deleting VPC {resource_id} in {region}")
                return True

            if resource_type == "rds_instance":
                rds = self._session.client("rds", region_name=region)
                rds.delete_db_instance(
                    DBInstanceIdentifier=resource_id,
                    SkipFinalSnapshot=True,
                )
                logger.info(f"Deleting RDS instance {resource_id} in {region}")
                try:
                    waiter = rds.get_waiter("db_instance_deleted")
                    waiter.wait(DBInstanceIdentifier=resource_id)
                except Exception:
                    pass
                return True

            if resource_type == "s3_bucket":
                s3 = self._session.resource("s3")
                bucket = s3.Bucket(resource_id)
                try:
                    bucket.objects.all().delete()
                    bucket.object_versions.all().delete()
                except Exception:
                    pass
                bucket.delete()
                logger.info(f"Deleting S3 bucket {resource_id}")
                return True

            if resource_type == "subnet":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_subnet(SubnetId=resource_id)
                return True

            if resource_type == "security_group":
                ec2 = self._session.client("ec2", region_name=region)
                try:
                    try:
                        sg_info = ec2.describe_security_groups(GroupIds=[resource_id])[
                            "SecurityGroups"
                        ][0]
                        
                        # First, revoke rules from the security group itself
                        if sg_info.get("IpPermissions"):
                            ec2.revoke_security_group_ingress(
                                GroupId=resource_id,
                                IpPermissions=sg_info["IpPermissions"],
                            )
                            logger.info(f"Revoked ingress rules from security group {resource_id}")
                        if sg_info.get("IpPermissionsEgress"):
                            ec2.revoke_security_group_egress(
                                GroupId=resource_id,
                                IpPermissions=sg_info["IpPermissionsEgress"],
                            )
                            logger.info(f"Revoked egress rules from security group {resource_id}")
                        
                        # Second, find and revoke rules in OTHER security groups that reference this one
                        # This is critical: AWS won't let you delete a security group if another SG references it
                        try:
                            # Get VPC ID to limit search scope
                            vpc_id = sg_info.get("VpcId")
                            all_sgs = ec2.describe_security_groups(
                                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}] if vpc_id else []
                            )["SecurityGroups"]
                            
                            for other_sg in all_sgs:
                                other_sg_id = other_sg["GroupId"]
                                if other_sg_id == resource_id:
                                    continue
                                
                                # Check ingress rules for references to our security group
                                ingress_to_revoke = []
                                for perm in other_sg.get("IpPermissions", []):
                                    for user_id_group_pair in perm.get("UserIdGroupPairs", []):
                                        if user_id_group_pair.get("GroupId") == resource_id:
                                            # Found a reference - create a permission entry to revoke
                                            ingress_to_revoke.append({
                                                "IpProtocol": perm.get("IpProtocol", "-1"),
                                                "FromPort": perm.get("FromPort"),
                                                "ToPort": perm.get("ToPort"),
                                                "IpRanges": perm.get("IpRanges", []),
                                                "Ipv6Ranges": perm.get("Ipv6Ranges", []),
                                                "UserIdGroupPairs": [user_id_group_pair]
                                            })
                                
                                if ingress_to_revoke:
                                    try:
                                        ec2.revoke_security_group_ingress(
                                            GroupId=other_sg_id,
                                            IpPermissions=ingress_to_revoke,
                                        )
                                        logger.info(f"Revoked ingress rules from security group {other_sg_id} that referenced {resource_id}")
                                    except ClientError as e:
                                        if "InvalidPermission.NotFound" not in str(e):
                                            logger.warning(f"Failed to revoke ingress rules from {other_sg_id}: {e}")
                                
                                # Check egress rules for references to our security group
                                egress_to_revoke = []
                                for perm in other_sg.get("IpPermissionsEgress", []):
                                    for user_id_group_pair in perm.get("UserIdGroupPairs", []):
                                        if user_id_group_pair.get("GroupId") == resource_id:
                                            # Found a reference - create a permission entry to revoke
                                            egress_to_revoke.append({
                                                "IpProtocol": perm.get("IpProtocol", "-1"),
                                                "FromPort": perm.get("FromPort"),
                                                "ToPort": perm.get("ToPort"),
                                                "IpRanges": perm.get("IpRanges", []),
                                                "Ipv6Ranges": perm.get("Ipv6Ranges", []),
                                                "UserIdGroupPairs": [user_id_group_pair]
                                            })
                                
                                if egress_to_revoke:
                                    try:
                                        ec2.revoke_security_group_egress(
                                            GroupId=other_sg_id,
                                            IpPermissions=egress_to_revoke,
                                        )
                                        logger.info(f"Revoked egress rules from security group {other_sg_id} that referenced {resource_id}")
                                    except ClientError as e:
                                        if "InvalidPermission.NotFound" not in str(e):
                                            logger.warning(f"Failed to revoke egress rules from {other_sg_id}: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to revoke cross-references for security group {resource_id}: {e}")
                        
                    except ClientError as e:
                        if "UnauthorizedOperation" in str(e):
                            logger.warning(
                                f"Permission denied clearing SG rules for {resource_id}. Proceeding with deletion."
                            )
                        else:
                            logger.warning(f"Failed to clear SG rules for {resource_id}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to clear SG rules for {resource_id}: {e}")

                    # Now try to delete the security group
                    ec2.delete_security_group(GroupId=resource_id)
                    logger.info(f"Successfully deleted security group {resource_id}")
                except ClientError as e:
                    if "CannotDelete" in str(e) and "default" in str(e):
                        logger.info(
                            f"Skipping default security group {resource_id} (will be deleted with VPC)"
                        )
                        return True
                    # If still failing, check if it's because of network interfaces or instances
                    if "CannotDelete" in str(e) or "DependencyViolation" in str(e):
                        error_msg = str(e)
                        if "network interface" in error_msg.lower() or "instance" in error_msg.lower():
                            logger.warning(
                                f"Security group {resource_id} still referenced by network interfaces or instances. "
                                "This may be cleaned up in a later layer."
                            )
                            # Don't raise - let dependency graph handle it
                            return False
                    raise
                return True

            if resource_type == "network_interface":
                ec2 = self._session.client("ec2", region_name=region)
                import time
                last_error = None
                for attempt in range(10):
                    try:
                        eni = ec2.describe_network_interfaces(
                            NetworkInterfaceIds=[resource_id]
                        )["NetworkInterfaces"][0]
                        
                        # Skip primary ENI (device index 0) - it's deleted automatically with the instance
                        attachment = eni.get("Attachment")
                        if attachment:
                            device_index = attachment.get("DeviceIndex")
                            if device_index == 0:
                                logger.info(f"Skipping primary network interface {resource_id} (deleted automatically with instance)")
                                return True
                            
                            if attachment.get("AttachmentId"):
                                try:
                                    ec2.detach_network_interface(
                                        AttachmentId=attachment["AttachmentId"],
                                        Force=True,
                                    )
                                    # Wait for detachment
                                    time.sleep(2)
                                except ClientError as e:
                                    if "OperationNotPermitted" in str(e) and "device index 0" in str(e).lower():
                                        logger.info(f"Skipping primary network interface {resource_id} (deleted automatically with instance)")
                                        return True
                                    if "InvalidAttachment.NotFound" not in str(e):
                                        raise
                        else:
                            ec2.delete_network_interface(NetworkInterfaceId=resource_id)
                            return True
                    except ClientError as e:
                        last_error = e
                        if "InvalidNetworkInterface.NotFound" in str(e):
                            return True
                        if "OperationNotPermitted" in str(e) and "device index 0" in str(e).lower():
                            logger.info(f"Skipping primary network interface {resource_id} (deleted automatically with instance)")
                            return True
                    except Exception as e:
                        last_error = e
                    if attempt < 9:
                        time.sleep(3)
                if last_error:
                    raise last_error
                return True

            if resource_type == "internet_gateway":
                ec2 = self._session.client("ec2", region_name=region)
                try:
                    igw = ec2.describe_internet_gateways(
                        InternetGatewayIds=[resource_id]
                    )["InternetGateways"][0]
                    for attachment in igw.get("Attachments", []):
                        ec2.detach_internet_gateway(
                            InternetGatewayId=resource_id,
                            VpcId=attachment["VpcId"],
                        )
                except Exception:
                    pass

                ec2.delete_internet_gateway(InternetGatewayId=resource_id)
                return True

            if resource_type == "vpc_endpoint":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_vpc_endpoints(VpcEndpointIds=[resource_id])
                return True

            if resource_type == "vpc_peering_connection":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_vpc_peering_connection(VpcPeeringConnectionId=resource_id)
                return True

            if resource_type == "nat_gateway":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_nat_gateway(NatGatewayId=resource_id)
                try:
                    waiter = ec2.get_waiter("nat_gateway_deleted")
                    waiter.wait(NatGatewayIds=[resource_id])
                except Exception:
                    pass
                return True

            if resource_type == "elastic_ip":
                ec2 = self._session.client("ec2", region_name=region)
                allocation_id = None
                try:
                    resp = ec2.describe_addresses(PublicIps=[resource_id])
                    if resp["Addresses"]:
                        allocation_id = resp["Addresses"][0].get("AllocationId")
                except ClientError:
                    pass

                if allocation_id:
                    ec2.release_address(AllocationId=allocation_id)
                else:
                    ec2.release_address(PublicIp=resource_id)
                return True

            if resource_type == "ebs_volume":
                ec2 = self._session.client("ec2", region_name=region)
                try:
                    vols = ec2.describe_volumes(VolumeIds=[resource_id])
                    if not vols["Volumes"]:
                        logger.info(f"Volume {resource_id} already deleted")
                        return True

                    vol = vols["Volumes"][0]
                    state = vol["State"]

                    if state == "in-use":
                        attachments = vol.get("Attachments", [])
                        for att in attachments:
                            instance_id = att.get("InstanceId")
                            if instance_id and att["State"] in ["attached", "attaching"]:
                                # Check if instance still exists/is terminating
                                instance_terminated = False
                                try:
                                    inst_resp = ec2.describe_instances(InstanceIds=[instance_id])
                                    if inst_resp.get("Reservations"):
                                        inst = inst_resp["Reservations"][0]["Instances"][0]
                                        inst_state = inst.get("State", {}).get("Name")
                                        if inst_state in ["running", "stopping", "stopped"]:
                                            # Instance still active - can't delete volume yet
                                            logger.info(f"Volume {resource_id} attached to active instance {instance_id}. Waiting for instance termination...")
                                            # Try to terminate it first (idempotent if already terminating)
                                            try:
                                                ec2.terminate_instances(InstanceIds=[instance_id])
                                                logger.info(f"Terminated instance {instance_id} for volume deletion")
                                            except ClientError as te:
                                                if "InvalidInstanceID.NotFound" not in str(te) and "IncorrectState" not in str(te):
                                                    logger.warning(f"Could not terminate instance {instance_id}: {te}")
                                            # Wait for termination
                                            try:
                                                waiter = ec2.get_waiter("instance_terminated")
                                                waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60})
                                                instance_terminated = True
                                                logger.info(f"Instance {instance_id} terminated, proceeding with volume {resource_id}")
                                            except Exception as we:
                                                logger.warning(f"Timeout waiting for instance {instance_id} termination: {we}")
                                        elif inst_state in ["terminated", "terminating"]:
                                            # Instance is terminating - wait for it
                                            logger.info(f"Waiting for instance {instance_id} to terminate before detaching volume {resource_id}")
                                            try:
                                                waiter = ec2.get_waiter("instance_terminated")
                                                waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60})
                                                instance_terminated = True
                                                logger.info(f"Instance {instance_id} terminated, proceeding with volume {resource_id}")
                                            except Exception as we:
                                                logger.warning(f"Timeout waiting for instance {instance_id} termination: {we}")
                                        else:
                                            instance_terminated = True  # Unknown state, assume it's safe
                                except ClientError as e:
                                    if "InvalidInstanceID.NotFound" in str(e):
                                        # Instance already gone - safe to proceed
                                        instance_terminated = True
                                        logger.info(f"Instance {instance_id} not found (already deleted), proceeding with volume {resource_id}")
                                    else:
                                        raise
                                
                                if not instance_terminated:
                                    # Instance still exists and we couldn't wait for it - skip for now
                                    raise ClientError(
                                        {"Error": {"Code": "VolumeInUse"}},
                                        f"Volume {resource_id} attached to instance {instance_id} which must be terminated first",
                                    )
                                
                                # Now try to detach
                                try:
                                    ec2.detach_volume(
                                        VolumeId=resource_id,
                                        InstanceId=instance_id,
                                        Force=True,
                                    )
                                    logger.info(
                                        f"Detaching volume {resource_id} from {instance_id}"
                                    )
                                except ClientError as e:
                                    if "InvalidVolume.NotFound" in str(e) or "InvalidAttachment.NotFound" in str(e):
                                        # Already detached or deleted
                                        pass
                                    elif "VolumeInUse" in str(e):
                                        # Still in use - wait for instance termination
                                        logger.warning(f"Volume {resource_id} still in use, waiting...")
                                    else:
                                        raise

                        # Wait for volume to become available
                        try:
                            waiter = ec2.get_waiter("volume_available")
                            waiter.wait(
                                VolumeIds=[resource_id],
                                WaiterConfig={"Delay": 2, "MaxAttempts": 60},
                            )
                        except Exception:
                            # Check if volume is actually available now
                            vols = ec2.describe_volumes(VolumeIds=[resource_id])
                            if vols.get("Volumes"):
                                if vols["Volumes"][0]["State"] == "available":
                                    pass  # Good to go
                                else:
                                    logger.warning(f"Volume {resource_id} still in state: {vols['Volumes'][0]['State']}")

                    ec2.delete_volume(VolumeId=resource_id)
                    logger.info(f"Deleted EBS volume {resource_id} in {region}")
                    return True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "InvalidVolume.NotFound":
                        logger.info(f"Volume {resource_id} already deleted")
                        return True
                    raise

            if resource_type == "route_table":
                ec2 = self._session.client("ec2", region_name=region)
                try:
                    rt = ec2.describe_route_tables(RouteTableIds=[resource_id])[
                        "RouteTables"
                    ][0]
                    for assoc in rt.get("Associations", []):
                        if not assoc.get("Main"):
                            ec2.disassociate_route_table(
                                AssociationId=assoc["RouteTableAssociationId"]
                            )
                except Exception:
                    pass
                ec2.delete_route_table(RouteTableId=resource_id)
                return True

            if resource_type == "key_pair":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_key_pair(KeyName=resource_id)
                return True

            if resource_type == "network_acl":
                ec2 = self._session.client("ec2", region_name=region)
                ec2.delete_network_acl(NetworkAclId=resource_id)
                return True

            if resource_type == "load_balancer_v1":
                elb = self._session.client("elb", region_name=region)
                elb.delete_load_balancer(LoadBalancerName=resource_id)
                return True

            if resource_type == "load_balancer_v2":
                elbv2 = self._session.client("elbv2", region_name=region)
                elbv2.delete_load_balancer(LoadBalancerArn=resource_id)
                try:
                    waiter = elbv2.get_waiter("load_balancers_deleted")
                    waiter.wait(LoadBalancerArns=[resource_id])
                except Exception:
                    pass
                return True

            if resource_type == "autoscaling_group":
                asg = self._session.client("autoscaling", region_name=region)
                asg.delete_auto_scaling_group(
                    AutoScalingGroupName=resource_id, ForceDelete=True
                )
                return True

            if resource_type == "iam_role":
                if resource_id.startswith("AWSServiceRoleFor") or "/aws-service-role/" in resource_id:
                    logger.info(f"Skipping protected AWS Service Role: {resource_id}")
                    return True

                iam = self._session.client("iam")
                profile_name = f"{resource_id}-profile"

                try:
                    iam.remove_role_from_instance_profile(
                        InstanceProfileName=profile_name,
                        RoleName=resource_id,
                    )
                except ClientError as e:
                    if "NoSuchEntity" not in str(e):
                        pass

                try:
                    iam.delete_instance_profile(InstanceProfileName=profile_name)
                except ClientError as e:
                    if "NoSuchEntity" not in str(e):
                        pass

                try:
                    attached = iam.list_attached_role_policies(RoleName=resource_id)
                    for policy in attached.get("AttachedPolicies", []):
                        iam.detach_role_policy(
                            RoleName=resource_id,
                            PolicyArn=policy["PolicyArn"],
                        )
                except ClientError:
                    pass

                try:
                    inline = iam.list_role_policies(RoleName=resource_id)
                    for policy_name in inline.get("PolicyNames", []):
                        iam.delete_role_policy(
                            RoleName=resource_id,
                            PolicyName=policy_name,
                        )
                except ClientError:
                    pass

                iam.delete_role(RoleName=resource_id)
                logger.info(f"Deleted IAM role: {resource_id}")
                return True

            logger.warning(f"Unsupported resource type for deletion: {resource_type}")
            return False

        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if (
                "NotFound" in code
                or "Does not exist" in str(e)
                or "InvalidGroup.NotFound" in code
                or "NoSuchEntity" in code
            ):
                logger.info(f"Resource {resource_id} already deleted ({code})")
                return True
            logger.error(f"Failed to delete {resource_type} {resource_id}: {e}")
            raise
