#!/usr/bin/env python3
"""
AWS Resource Cleanup Script

Scans and cleans up all Pockitect-managed resources in AWS.
Finds resources by both:
1. Pockitect tags (pockitect:managed = true)
2. Naming convention (names containing 'pockitect' or 'test-')

Usage:
    python scripts/cleanup_aws.py scan          # Show what would be deleted
    python scripts/cleanup_aws.py cleanup       # Actually delete resources
    python scripts/cleanup_aws.py status        # Show tracked resources
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from botocore.exceptions import ClientError

# Load credentials from keyring
def setup_credentials():
    """Load AWS credentials from OS keyring."""
    try:
        from auth_dialog import get_aws_credentials
        creds = get_aws_credentials()
        if creds and creds[0] and creds[1]:
            os.environ["AWS_ACCESS_KEY_ID"] = creds[0]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds[1]
            print(f"✓ Loaded credentials from OS keyring (key: {creds[0][:8]}...)")
            return True
        else:
            print("ERROR: No AWS credentials found in OS keyring.")
            print("       Please log in via the Pockitect app first.")
            return False
    except ImportError:
        print("ERROR: Could not import auth_dialog.")
        return False


def scan_region(region: str, dry_run: bool = True) -> dict:
    """Scan a region for Pockitect resources."""
    ec2 = boto3.client('ec2', region_name=region)
    results = {
        "instances": [],
        "vpcs": [],
        "subnets": [],
        "security_groups": [],
        "internet_gateways": [],
    }
    
    # Find instances by tag OR name
    try:
        # By tag
        tagged = ec2.describe_instances(
            Filters=[{"Name": "tag:pockitect:managed", "Values": ["true"]}]
        )
        for res in tagged.get("Reservations", []):
            for inst in res.get("Instances", []):
                if inst["State"]["Name"] not in ["terminated", "shutting-down"]:
                    results["instances"].append({
                        "id": inst["InstanceId"],
                        "state": inst["State"]["Name"],
                        "name": get_tag(inst.get("Tags", []), "Name"),
                        "found_by": "tag"
                    })
        
        # By name
        named = ec2.describe_instances(
            Filters=[{"Name": "tag:Name", "Values": ["*pockitect*", "*test-*"]}]
        )
        existing_ids = {i["id"] for i in results["instances"]}
        for res in named.get("Reservations", []):
            for inst in res.get("Instances", []):
                if inst["InstanceId"] not in existing_ids and inst["State"]["Name"] not in ["terminated", "shutting-down"]:
                    results["instances"].append({
                        "id": inst["InstanceId"],
                        "state": inst["State"]["Name"],
                        "name": get_tag(inst.get("Tags", []), "Name"),
                        "found_by": "name"
                    })
    except ClientError as e:
        print(f"  Warning: Could not scan instances: {e}")
    
    # Find VPCs by tag OR name
    try:
        tagged_vpcs = ec2.describe_vpcs(
            Filters=[{"Name": "tag:pockitect:managed", "Values": ["true"]}]
        )
        for vpc in tagged_vpcs.get("Vpcs", []):
            results["vpcs"].append({
                "id": vpc["VpcId"],
                "name": get_tag(vpc.get("Tags", []), "Name"),
                "found_by": "tag"
            })
        
        # Also check by name
        all_vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["false"]}])
        existing_ids = {v["id"] for v in results["vpcs"]}
        for vpc in all_vpcs.get("Vpcs", []):
            name = get_tag(vpc.get("Tags", []), "Name") or ""
            if vpc["VpcId"] not in existing_ids and ("pockitect" in name.lower() or "test-" in name.lower()):
                results["vpcs"].append({
                    "id": vpc["VpcId"],
                    "name": name,
                    "found_by": "name"
                })
    except ClientError as e:
        print(f"  Warning: Could not scan VPCs: {e}")
    
    # Find Security Groups by tag OR name
    try:
        tagged_sgs = ec2.describe_security_groups(
            Filters=[{"Name": "tag:pockitect:managed", "Values": ["true"]}]
        )
        for sg in tagged_sgs.get("SecurityGroups", []):
            if sg["GroupName"] != "default":
                results["security_groups"].append({
                    "id": sg["GroupId"],
                    "name": sg["GroupName"],
                    "vpc_id": sg.get("VpcId"),
                    "found_by": "tag"
                })
        
        # Also check by name
        all_sgs = ec2.describe_security_groups()
        existing_ids = {s["id"] for s in results["security_groups"]}
        for sg in all_sgs.get("SecurityGroups", []):
            if sg["GroupId"] not in existing_ids and sg["GroupName"] != "default":
                if "pockitect" in sg["GroupName"].lower() or "test-" in sg["GroupName"].lower():
                    results["security_groups"].append({
                        "id": sg["GroupId"],
                        "name": sg["GroupName"],
                        "vpc_id": sg.get("VpcId"),
                        "found_by": "name"
                    })
    except ClientError as e:
        print(f"  Warning: Could not scan security groups: {e}")
    
    # Find Subnets
    try:
        tagged_subs = ec2.describe_subnets(
            Filters=[{"Name": "tag:pockitect:managed", "Values": ["true"]}]
        )
        for sub in tagged_subs.get("Subnets", []):
            results["subnets"].append({
                "id": sub["SubnetId"],
                "name": get_tag(sub.get("Tags", []), "Name"),
                "vpc_id": sub.get("VpcId"),
                "found_by": "tag"
            })
        
        all_subs = ec2.describe_subnets()
        existing_ids = {s["id"] for s in results["subnets"]}
        for sub in all_subs.get("Subnets", []):
            name = get_tag(sub.get("Tags", []), "Name") or ""
            if sub["SubnetId"] not in existing_ids and ("pockitect" in name.lower() or "test-" in name.lower()):
                results["subnets"].append({
                    "id": sub["SubnetId"],
                    "name": name,
                    "vpc_id": sub.get("VpcId"),
                    "found_by": "name"
                })
    except ClientError as e:
        print(f"  Warning: Could not scan subnets: {e}")
    
    # Find Internet Gateways
    try:
        tagged_igws = ec2.describe_internet_gateways(
            Filters=[{"Name": "tag:pockitect:managed", "Values": ["true"]}]
        )
        for igw in tagged_igws.get("InternetGateways", []):
            vpc_id = igw["Attachments"][0]["VpcId"] if igw.get("Attachments") else None
            results["internet_gateways"].append({
                "id": igw["InternetGatewayId"],
                "name": get_tag(igw.get("Tags", []), "Name"),
                "vpc_id": vpc_id,
                "found_by": "tag"
            })
        
        # Check by name
        all_igws = ec2.describe_internet_gateways()
        existing_ids = {i["id"] for i in results["internet_gateways"]}
        for igw in all_igws.get("InternetGateways", []):
            name = get_tag(igw.get("Tags", []), "Name") or ""
            if igw["InternetGatewayId"] not in existing_ids and ("pockitect" in name.lower() or "test-" in name.lower()):
                vpc_id = igw["Attachments"][0]["VpcId"] if igw.get("Attachments") else None
                results["internet_gateways"].append({
                    "id": igw["InternetGatewayId"],
                    "name": name,
                    "vpc_id": vpc_id,
                    "found_by": "name"
                })
    except ClientError as e:
        print(f"  Warning: Could not scan internet gateways: {e}")
    
    return results


def get_tag(tags: list, key: str) -> str:
    """Get tag value from list of tags."""
    for tag in tags:
        if tag.get("Key") == key:
            return tag.get("Value", "")
    return ""


def cleanup_region(region: str, resources: dict) -> dict:
    """Clean up resources in a region."""
    ec2 = boto3.client('ec2', region_name=region)
    results = {"deleted": 0, "errors": []}
    
    # 1. Terminate instances first
    if resources["instances"]:
        instance_ids = [i["id"] for i in resources["instances"]]
        print(f"  Terminating {len(instance_ids)} instances...")
        try:
            ec2.terminate_instances(InstanceIds=instance_ids)
            waiter = ec2.get_waiter("instance_terminated")
            waiter.wait(InstanceIds=instance_ids, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
            results["deleted"] += len(instance_ids)
            print(f"  ✓ Terminated {len(instance_ids)} instances")
            time.sleep(10)  # Extra buffer for dependencies to clear
        except Exception as e:
            results["errors"].append(f"Instance termination: {e}")
    
    # 2. Delete Security Groups
    for sg in resources["security_groups"]:
        try:
            ec2.delete_security_group(GroupId=sg["id"])
            results["deleted"] += 1
            print(f"  ✓ Deleted SG: {sg['id']} ({sg['name']})")
        except ClientError as e:
            results["errors"].append(f"SG {sg['id']}: {e}")
    
    # 3. Delete Subnets
    for sub in resources["subnets"]:
        try:
            ec2.delete_subnet(SubnetId=sub["id"])
            results["deleted"] += 1
            print(f"  ✓ Deleted Subnet: {sub['id']}")
        except ClientError as e:
            results["errors"].append(f"Subnet {sub['id']}: {e}")
    
    # 4. Delete Internet Gateways
    for igw in resources["internet_gateways"]:
        try:
            if igw.get("vpc_id"):
                ec2.detach_internet_gateway(InternetGatewayId=igw["id"], VpcId=igw["vpc_id"])
            ec2.delete_internet_gateway(InternetGatewayId=igw["id"])
            results["deleted"] += 1
            print(f"  ✓ Deleted IGW: {igw['id']}")
        except ClientError as e:
            results["errors"].append(f"IGW {igw['id']}: {e}")
    
    # 5. Delete VPCs
    for vpc in resources["vpcs"]:
        try:
            ec2.delete_vpc(VpcId=vpc["id"])
            results["deleted"] += 1
            print(f"  ✓ Deleted VPC: {vpc['id']} ({vpc['name']})")
        except ClientError as e:
            results["errors"].append(f"VPC {vpc['id']}: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="AWS Resource Cleanup")
    parser.add_argument("command", choices=["scan", "cleanup", "status"],
                       help="Command to run")
    parser.add_argument("--regions", nargs="+", 
                       default=["us-east-1", "eu-west-1", "ap-southeast-1"],
                       help="AWS regions to scan/cleanup")
    args = parser.parse_args()
    
    if args.command == "status":
        # Show resource tracker status
        from aws.resource_tracker import ResourceTracker
        tracker = ResourceTracker()
        tracker.print_status()
        return
    
    if not setup_credentials():
        sys.exit(1)
    
    all_resources = {}
    total = 0
    
    print(f"\n{'='*60}")
    print(f"Scanning {len(args.regions)} regions for Pockitect resources...")
    print(f"{'='*60}\n")
    
    for region in args.regions:
        print(f"=== {region} ===")
        resources = scan_region(region)
        all_resources[region] = resources
        
        count = sum(len(v) for v in resources.values())
        total += count
        
        if count == 0:
            print("  No resources found")
        else:
            if resources["instances"]:
                for i in resources["instances"]:
                    print(f"  🖥️  Instance: {i['id']} ({i['state']}) - {i['name']} [{i['found_by']}]")
            if resources["vpcs"]:
                for v in resources["vpcs"]:
                    print(f"  🌐 VPC: {v['id']} - {v['name']} [{v['found_by']}]")
            if resources["subnets"]:
                for s in resources["subnets"]:
                    print(f"  📦 Subnet: {s['id']} - {s['name']} [{s['found_by']}]")
            if resources["security_groups"]:
                for sg in resources["security_groups"]:
                    print(f"  🔒 SG: {sg['id']} - {sg['name']} [{sg['found_by']}]")
            if resources["internet_gateways"]:
                for igw in resources["internet_gateways"]:
                    print(f"  🌉 IGW: {igw['id']} - {igw['name']} [{igw['found_by']}]")
        print()
    
    print(f"{'='*60}")
    print(f"TOTAL: {total} resources found")
    print(f"{'='*60}")
    
    if args.command == "scan":
        if total > 0:
            print("\nRun 'cleanup' to delete these resources.")
    
    elif args.command == "cleanup":
        if total == 0:
            print("\nNo resources to clean up!")
            return
        
        print("\n⚠️  WARNING: This will permanently delete the above resources!")
        confirm = input("Type 'yes' to confirm: ")
        
        if confirm != "yes":
            print("Cancelled.")
            return
        
        print(f"\n{'='*60}")
        print("Cleaning up resources...")
        print(f"{'='*60}\n")
        
        total_deleted = 0
        all_errors = []
        
        for region, resources in all_resources.items():
            if sum(len(v) for v in resources.values()) == 0:
                continue
            
            print(f"=== {region} ===")
            result = cleanup_region(region, resources)
            total_deleted += result["deleted"]
            all_errors.extend(result["errors"])
            print()
        
        print(f"{'='*60}")
        print(f"SUMMARY: {total_deleted} resources deleted")
        if all_errors:
            print(f"ERRORS: {len(all_errors)}")
            for e in all_errors[:10]:  # Show first 10 errors
                print(f"  - {e}")
            if len(all_errors) > 10:
                print(f"  ... and {len(all_errors) - 10} more")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
