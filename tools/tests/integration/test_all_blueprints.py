"""
Batch Test Runner for All Blueprint Templates

Runs the lifecycle test against every blueprint in tools/tests/data/.
Reports pass/fail status for each.

Usage:
    python -m tools.tests.integration.test_all_blueprints
    python -m tools.tests.integration.test_all_blueprints --real-aws  # WARNING: costs money!
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

pytest.importorskip("aws.deploy")
pytest.importorskip("aws.resources")

from aws.deploy import DeploymentOrchestrator, DeploymentStatus
from aws.resources import AWSResourceManager
from auth_dialog import get_aws_credentials, KEYRING_AVAILABLE

logging.basicConfig(
    level=logging.WARNING,  # Less verbose for batch run
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BatchTest")


def setup_moto():
    """Start moto mock."""
    try:
        from moto import mock_aws
        mock = mock_aws()
        mock.start()
        return mock
    except ImportError:
        logger.error("moto is not installed.")
        sys.exit(1)


def setup_aws_credentials_from_keyring() -> bool:
    """
    Load AWS credentials from OS keyring (stored by Pockitect app).
    Sets them as environment variables for boto3 to use.
    
    Returns:
        True if credentials were loaded successfully.
    """
    if not KEYRING_AVAILABLE:
        print("ERROR: keyring library not available.")
        return False
    
    access_key, secret_key = get_aws_credentials()
    
    if not access_key or not secret_key:
        print("ERROR: No AWS credentials found in OS keyring.")
        print("       Please log in via the Pockitect app first.")
        return False
    
    # Set as environment variables for boto3
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    
    # Set default region if not already set
    if 'AWS_DEFAULT_REGION' not in os.environ:
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    
    print(f"✓ Loaded credentials from OS keyring (key: {access_key[:8]}...)")
    return True


def teardown_resources(manager: AWSResourceManager, blueprint: dict):
    """Delete all resources in the correct order with proper waits."""
    from botocore.exceptions import ClientError
    
    vpc_id = blueprint['network'].get('vpc_id')
    
    # 1. EC2 Instance - terminate and WAIT for full termination
    instance_id = blueprint['compute'].get('instance_id')
    if instance_id:
        logger.info(f"Terminating instance {instance_id}...")
        manager.terminate_instance(instance_id)
        try:
            waiter = manager.ec2.get_waiter('instance_terminated')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 60}  # Up to 5 minutes
            )
            logger.info(f"Instance {instance_id} terminated")
        except Exception as e:
            logger.warning(f"Instance termination wait failed: {e}")
        # Extra buffer for AWS to release dependencies
        time.sleep(5)

    # 2. S3 Bucket
    bucket_name = blueprint['data'].get('s3_bucket', {}).get('name')
    if bucket_name:
        manager.delete_bucket(bucket_name, force=True)

    # 3. IAM Role (must be done before instance profile can be cleaned)
    role_name = blueprint['security'].get('iam_role', {}).get('role_name')
    if role_name:
        manager.delete_instance_role(role_name)

    # 4. Key Pair
    key_name = blueprint['security'].get('key_pair', {}).get('name')
    key_mode = blueprint['security'].get('key_pair', {}).get('mode')
    if key_name and key_mode != 'existing':
        manager.delete_key_pair(key_name)
        key_file = Path.home() / '.ssh' / f"{key_name}.pem"
        if key_file.exists():
            key_file.unlink()

    # 5. Delete any ENIs in the VPC (can block SG/subnet deletion)
    if vpc_id:
        try:
            enis = manager.ec2.describe_network_interfaces(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for eni in enis.get('NetworkInterfaces', []):
                eni_id = eni['NetworkInterfaceId']
                # Detach if attached
                if eni.get('Attachment') and eni['Attachment'].get('AttachmentId'):
                    try:
                        manager.ec2.detach_network_interface(
                            AttachmentId=eni['Attachment']['AttachmentId'],
                            Force=True
                        )
                        time.sleep(2)
                    except ClientError:
                        pass
                # Delete ENI
                try:
                    manager.ec2.delete_network_interface(NetworkInterfaceId=eni_id)
                    logger.info(f"Deleted ENI: {eni_id}")
                except ClientError as e:
                    logger.warning(f"Could not delete ENI {eni_id}: {e}")
        except ClientError as e:
            # Permission might not be available, continue anyway
            logger.debug(f"ENI cleanup skipped: {e}")

    # 6. Security Group - with extended retries
    sg_id = blueprint['network'].get('security_group_id')
    if sg_id:
        for attempt in range(15):  # Up to 30 seconds of retries
            res = manager.delete_security_group(sg_id)
            if res.success:
                logger.info(f"Deleted security group: {sg_id}")
                break
            time.sleep(2)
        else:
            logger.warning(f"Could not delete security group {sg_id} after 15 attempts")

    # 7. Subnet - with retries
    subnet_id = blueprint['network'].get('subnet_id')
    if subnet_id:
        for attempt in range(10):
            res = manager.delete_subnet(subnet_id)
            if res.success:
                logger.info(f"Deleted subnet: {subnet_id}")
                break
            time.sleep(2)
        else:
            logger.warning(f"Could not delete subnet {subnet_id} after 10 attempts")

    # 8. VPC - detach/delete internet gateway first, then route tables
    if vpc_id:
        # Clean up Internet Gateways
        try:
            igws = manager.ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            for igw in igws.get('InternetGateways', []):
                igw_id = igw['InternetGatewayId']
                try:
                    manager.ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                    manager.ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                    logger.info(f"Deleted IGW: {igw_id}")
                except ClientError as e:
                    logger.warning(f"Could not delete IGW {igw_id}: {e}")
        except ClientError:
            pass
        
        # Clean up non-main route tables
        try:
            rts = manager.ec2.describe_route_tables(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for rt in rts.get('RouteTables', []):
                is_main = any(a.get('Main', False) for a in rt.get('Associations', []))
                if not is_main:
                    try:
                        # Disassociate first
                        for assoc in rt.get('Associations', []):
                            if not assoc.get('Main') and assoc.get('RouteTableAssociationId'):
                                manager.ec2.disassociate_route_table(
                                    AssociationId=assoc['RouteTableAssociationId']
                                )
                        manager.ec2.delete_route_table(RouteTableId=rt['RouteTableId'])
                        logger.info(f"Deleted route table: {rt['RouteTableId']}")
                    except ClientError as e:
                        logger.warning(f"Could not delete RT {rt['RouteTableId']}: {e}")
        except ClientError:
            pass
        
        # Finally delete VPC
        for attempt in range(5):
            res = manager.delete_vpc(vpc_id)
            if res.success:
                logger.info(f"Deleted VPC: {vpc_id}")
                break
            time.sleep(2)
        else:
            logger.warning(f"Could not delete VPC {vpc_id} after 5 attempts")


def run_single_test(blueprint_path: Path, use_real_aws: bool = False) -> tuple[bool, str]:
    """
    Run a single blueprint test.
    
    Returns:
        (success, error_message)
    """
    mock = None
    if not use_real_aws:
        mock = setup_moto()
    
    try:
        with open(blueprint_path) as f:
            blueprint = json.load(f)
        
        # Check if this blueprint uses an existing keypair (can't test in mock)
        key_mode = blueprint.get('security', {}).get('key_pair', {}).get('mode')
        if key_mode == 'existing' and not use_real_aws:
            return True, "(skipped - existing keypair requires real AWS)"
        
        # Check if using unsupported DB engine in moto (mariadb not supported)
        db_engine = blueprint.get('data', {}).get('db', {}).get('engine')
        if db_engine == 'mariadb' and not use_real_aws:
            return True, "(skipped - mariadb not supported in moto mock)"
        
        # Provide mock password for database-enabled blueprints
        db_password = None
        db_config = blueprint.get('data', {}).get('db', {})
        if db_config.get('engine') or db_config.get('status') not in ['skipped', None]:
            db_password = "MockTestPassword123!"
        
        # Initialize and deploy
        orchestrator = DeploymentOrchestrator(blueprint, db_password=db_password)
        success = orchestrator.deploy()
        
        if not success:
            teardown_resources(orchestrator.manager, orchestrator.blueprint)
            return False, f"Deploy failed: {orchestrator.state.error}"
        
        # Teardown
        teardown_resources(orchestrator.manager, orchestrator.blueprint)
        
        return True, ""
        
    except Exception as e:
        return False, str(e)
    finally:
        if mock:
            mock.stop()


def main():
    parser = argparse.ArgumentParser(description="Batch Blueprint Test Runner")
    parser.add_argument("--real-aws", action="store_true", help="Run against real AWS (costs $$$)")
    parser.add_argument("--filter", type=str, help="Only run blueprints matching this pattern")
    args = parser.parse_args()
    
    if args.real_aws:
        print("!!! WARNING: Running against REAL AWS !!!")
        print("This will create resources and incur charges.")
        confirm = input("Type 'yes' to proceed: ")
        if confirm != "yes":
            sys.exit(0)
        
        # Load credentials from OS keyring (stored by Pockitect app)
        if not setup_aws_credentials_from_keyring():
            sys.exit(1)
    
    # Find all blueprints
    data_dir = Path(__file__).parent.parent / "data"
    blueprints = sorted(data_dir.glob("blueprint_*.json"))
    
    if args.filter:
        blueprints = [b for b in blueprints if args.filter in b.name]
    
    print(f"\n{'='*60}")
    print(f"Running {len(blueprints)} blueprint tests")
    print(f"Mode: {'REAL AWS' if args.real_aws else 'MOCK (moto)'}")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, bp_path in enumerate(blueprints, 1):
        name = bp_path.stem.replace("blueprint_", "")
        print(f"[{i}/{len(blueprints)}] Testing {name}...", end=" ", flush=True)
        
        start = time.time()
        success, error = run_single_test(bp_path, args.real_aws)
        duration = time.time() - start
        
        if success:
            print(f"✓ PASS ({duration:.1f}s)")
        else:
            print(f"✗ FAIL ({duration:.1f}s)")
            print(f"        Error: {error[:80]}...")
        
        results.append({
            "name": name,
            "success": success,
            "error": error,
            "duration": duration
        })
    
    # Summary
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    total_time = sum(r["duration"] for r in results)
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(results)} total")
    print(f"Total time: {total_time:.1f}s")
    print(f"{'='*60}")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['name']}: {r['error'][:60]}...")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
