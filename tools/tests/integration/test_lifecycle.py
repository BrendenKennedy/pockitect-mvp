"""
Iterative Integration Test for Pockitect

This script runs a full lifecycle test:
1. Load Blueprint
2. Create Resources (Deployment)
3. Verify Resources
4. Delete Resources (Teardown)
5. Confirm Deletion

Usage:
    python -m tools.tests.integration.test_lifecycle --blueprint tools/tests/data/blueprint_basic.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.deploy import DeploymentOrchestrator, DeploymentStatus
from aws.resources import AWSResourceManager
from aws.scanner import ResourceScanner
from aws.recursive_deleter import RecursiveDeleter
from auth_dialog import get_aws_credentials
import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LifecycleTest")

def setup_moto():
    """Start moto decorators."""
    try:
        from moto import mock_aws
        mock = mock_aws()
        mock.start()
        return mock
    except ImportError:
        logger.error("moto is not installed. Please install it to run in mock mode.")
        sys.exit(1)

def verify_resources(manager: AWSResourceManager, blueprint: dict):
    """Verify that resources in the blueprint actually exist."""
    logger.info("Verifying resources...")
    all_good = True

    # 1. VPC
    vpc_id = blueprint['network'].get('vpc_id')
    if vpc_id:
        try:
            manager.ec2.describe_vpcs(VpcIds=[vpc_id])
            logger.info(f"✓ VPC found: {vpc_id}")
        except Exception as e:
            logger.error(f"✗ VPC not found: {e}")
            all_good = False

    # 2. Subnet
    subnet_id = blueprint['network'].get('subnet_id')
    if subnet_id:
        try:
            manager.ec2.describe_subnets(SubnetIds=[subnet_id])
            logger.info(f"✓ Subnet found: {subnet_id}")
        except Exception as e:
            logger.error(f"✗ Subnet not found: {e}")
            all_good = False

    # 3. Security Group
    sg_id = blueprint['network'].get('security_group_id')
    if sg_id:
        try:
            manager.ec2.describe_security_groups(GroupIds=[sg_id])
            logger.info(f"✓ Security Group found: {sg_id}")
        except Exception as e:
            logger.error(f"✗ Security Group not found: {e}")
            all_good = False

    # 4. Key Pair
    key_id = blueprint['security'].get('key_pair', {}).get('key_pair_id')
    if key_id:
        try:
            manager.ec2.describe_key_pairs(KeyPairIds=[key_id])
            logger.info(f"✓ Key Pair found: {key_id}")
        except Exception as e:
            logger.error(f"✗ Key Pair not found: {e}")
            all_good = False

    # 5. IAM Role
    role_name = blueprint['security'].get('iam_role', {}).get('role_name')
    if role_name:
        try:
            manager.iam.get_role(RoleName=role_name)
            logger.info(f"✓ IAM Role found: {role_name}")
        except Exception as e:
            logger.error(f"✗ IAM Role not found: {e}")
            all_good = False

    # 6. EC2 Instance
    instance_id = blueprint['compute'].get('instance_id')
    if instance_id:
        res = manager.get_instance_status(instance_id)
        if res.success:
             logger.info(f"✓ EC2 Instance found: {instance_id} ({res.data.get('state')})")
        else:
             logger.error(f"✗ EC2 Instance not found: {res.error}")
             all_good = False

    # 7. S3 Bucket
    bucket_name = blueprint['data'].get('s3_bucket', {}).get('name')
    if bucket_name:
        try:
            manager.s3.head_bucket(Bucket=bucket_name)
            logger.info(f"✓ S3 Bucket found: {bucket_name}")
        except Exception as e:
            logger.error(f"✗ S3 Bucket not found: {e}")
            all_good = False
            
    return all_good

def teardown_resources(manager: AWSResourceManager, blueprint: dict):
    """Delete all resources using RecursiveDeleter for robustness."""
    logger.info("Tearing down resources...")
    
    try:
        # Use credentials from env (set in main)
        session = boto3.Session()
        deleter = RecursiveDeleter(session=session)
        region = manager.region
        
        # 1. VPC (Handles subnets, SGs, IGWs, instances inside)
        vpc_id = blueprint['network'].get('vpc_id')
        if vpc_id:
            logger.info(f"Deleting VPC tree: {vpc_id}")
            try:
                deleter.delete_tree(vpc_id, 'vpc', region)
            except Exception as e:
                logger.error(f"Failed to delete VPC tree: {e}")

        # 2. Instance (if not in VPC or skipped)
        instance_id = blueprint['compute'].get('instance_id')
        if instance_id:
            try:
                deleter.delete_tree(instance_id, 'ec2_instance', region)
            except Exception:
                pass # Likely gone

        # 3. RDS
        db_id = blueprint['data'].get('db', {}).get('identifier')
        if db_id:
            try:
                deleter.delete_tree(db_id, 'rds_instance', region)
            except Exception as e:
                logger.error(f"Failed to delete DB: {e}")

        # 4. S3
        bucket_name = blueprint['data'].get('s3_bucket', {}).get('name')
        if bucket_name:
            try:
                deleter.delete_tree(bucket_name, 's3_bucket', region)
            except Exception as e:
                logger.error(f"Failed to delete Bucket: {e}")

        # 5. Key Pair
        key_name = blueprint['security'].get('key_pair', {}).get('name')
        if key_name:
            try:
                deleter.delete_tree(key_name, 'key_pair', region)
                key_file = Path.home() / '.ssh' / f"{key_name}.pem"
                if key_file.exists():
                    key_file.unlink()
            except Exception: pass

        # 6. IAM Role (ResourceDeleter missing IAM support, use manager)
        role_name = blueprint['security'].get('iam_role', {}).get('role_name')
        if role_name:
            manager.delete_instance_role(role_name)

    except Exception as e:
        logger.error(f"Teardown failed: {e}")
        # Fallback to old manager methods if everything explodes?
        # No, RecursiveDeleter is the way forward.

def confirm_deletion(manager: AWSResourceManager, blueprint: dict):
    """Confirm resources are gone."""
    logger.info("Confirming deletion...")
    all_gone = True

    # Check VPC (Root of most things)
    vpc_id = blueprint['network'].get('vpc_id')
    if vpc_id:
        try:
            manager.ec2.describe_vpcs(VpcIds=[vpc_id])
            logger.error(f"✗ VPC still exists: {vpc_id}")
            all_gone = False
        except Exception:
            logger.info(f"✓ VPC gone")

    # Check Key Pair
    key_id = blueprint['security'].get('key_pair', {}).get('key_pair_id')
    if key_id:
        try:
            resp = manager.ec2.describe_key_pairs(KeyPairIds=[key_id])
            if resp.get('KeyPairs'):
                logger.error(f"✗ Key Pair still exists: {key_id}")
                all_gone = False
            else:
                logger.info(f"✓ Key Pair gone")
        except Exception:
            logger.info(f"✓ Key Pair gone")
            
    return all_gone

def scan_for_leaks(scanner: ResourceScanner, region: str, phase_name: str) -> dict:
    """Scan for resources and return them as a dict keyed by ID."""
    logger.info(f"Scanning resources for {phase_name} in {region}...")
    resources = scanner.scan_all_regions(regions=[region])
    logger.info(f"Found {len(resources)} resources.")
    return {r.id: r for r in resources}

def main():
    parser = argparse.ArgumentParser(description="Pockitect Lifecycle Test")
    parser.add_argument("--blueprint", required=True, help="Path to blueprint JSON")
    parser.add_argument("--real-aws", action="store_true", help="Run against real AWS")
    parser.add_argument("--keep-resources", action="store_true", help="Don't delete resources after test")
    parser.add_argument("--iterations", type=int, default=1, help="Number of test iterations")
    
    args = parser.parse_args()
    
    if not args.real_aws:
        logger.info("Running in MOCK mode (moto)")
        mock = setup_moto()
    else:
        # Check credentials
        creds = get_aws_credentials()
        if not creds[0]:
            logger.error("No credentials found in keyring.")
            sys.exit(1)
        
        # Set env vars for boto3/RecursiveDeleter to pick up
        import os
        os.environ['AWS_ACCESS_KEY_ID'] = creds[0]
        os.environ['AWS_SECRET_ACCESS_KEY'] = creds[1]
        
        logger.warning("!!! RUNNING AGAINST REAL AWS !!!")
        logger.warning("This will create resources and incur costs.")
        confirm = input("Type 'yes' to proceed: ")
        if confirm != "yes":
            sys.exit(0)

    # Load Blueprint
    with open(args.blueprint) as f:
        blueprint = json.load(f)

    # Set up Scanner
    if args.real_aws:
        access_key, secret_key = creds
    else:
        access_key, secret_key = "test", "test"

    scanner = ResourceScanner(access_key, secret_key)
    target_region = blueprint.get('project', {}).get('region', 'us-east-1')

    # Run Iterations
    for i in range(args.iterations):
        logger.info(f"\n{'='*40}")
        logger.info(f"ITERATION {i+1}/{args.iterations}")
        logger.info(f"{'='*40}")

        # --- PHASE 0: PRE-TEST SCAN ---
        resources_before = scan_for_leaks(scanner, target_region, "PRE-TEST")

        # Initialize Orchestrator
        orchestrator = DeploymentOrchestrator(blueprint)
        
        # --- PHASE 1: CREATE ---
        logger.info("=== PHASE 1: DEPLOYMENT ===")
        start_time = time.time()
        
        def on_progress(state):
            pass # Quiet output
            
        success = orchestrator.deploy(on_progress=on_progress)
        
        if not success:
            logger.error(f"Deployment failed: {orchestrator.state.error}")
            if not args.keep_resources:
                teardown_resources(orchestrator.manager, orchestrator.blueprint)
            sys.exit(1)
            
        logger.info(f"Deployment completed in {time.time() - start_time:.2f}s")
        
        # --- PHASE 2: VIEW/VERIFY ---
        logger.info("=== PHASE 2: VERIFICATION ===")
        if not verify_resources(orchestrator.manager, orchestrator.blueprint):
            logger.error("Verification failed!")
            if not args.keep_resources:
                teardown_resources(orchestrator.manager, orchestrator.blueprint)
            sys.exit(1)
            
        # --- PHASE 3: DELETE ---
        if not args.keep_resources:
            logger.info("=== PHASE 3: TEARDOWN ===")
            teardown_resources(orchestrator.manager, orchestrator.blueprint)
            
            # --- PHASE 4: CONFIRM ---
            logger.info("=== PHASE 4: CONFIRMATION ===")
            if confirm_deletion(orchestrator.manager, orchestrator.blueprint):
                # --- PHASE 5: LEAK DETECTION ---
                resources_after = scan_for_leaks(scanner, target_region, "POST-TEST")
                
                leaked_ids = set(resources_after.keys()) - set(resources_before.keys())
                
                if leaked_ids:
                    logger.error(f"FAILURE: {len(leaked_ids)} LEAKED RESOURCES DETECTED!")
                    for rid in leaked_ids:
                        r = resources_after[rid]
                        logger.error(f"  - {r.type} {r.id}")
                    sys.exit(1)
                else:
                    logger.info("SUCCESS: Iteration passed with ZERO LEAKS!")
            else:
                logger.error("FAILURE: Some resources were not deleted.")
                sys.exit(1)
        else:
            logger.info("Skipping teardown (--keep-resources set)")
            break # Stop iterations if we keep resources

    if not args.real_aws:
        mock.stop()


if __name__ == "__main__":
    main()
