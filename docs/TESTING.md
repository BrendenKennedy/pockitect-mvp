# Testing Guide

This project includes a robust iterative testing suite for verifying the AWS deployment lifecycle.

## Prerequisites

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install moto  # Required for mock testing
   ```

2. **AWS Credentials** (for Real AWS testing only)
   Ensure your AWS credentials are configured via `~/.aws/credentials` or environment variables.

## Test Scripts

### Single Blueprint Test
Run a specific blueprint through the full lifecycle (Create → Verify → Delete → Confirm):

```bash
# Mock mode (safe, free, recommended for development)
python -m tools.tests.integration.test_lifecycle --blueprint tools/tests/data/blueprint_basic.json

# Real AWS mode (creates actual resources, costs money!)
python -m tools.tests.integration.test_lifecycle --blueprint tools/tests/data/blueprint_basic.json --real-aws

# Keep resources after test (for debugging)
python -m tools.tests.integration.test_lifecycle --blueprint tools/tests/data/blueprint_basic.json --keep-resources
```

### Batch Test Runner
Run ALL blueprint templates at once:

```bash
# Mock mode - tests all 22 blueprints
python -m tools.tests.integration.test_all_blueprints

# Filter by name pattern
python -m tools.tests.integration.test_all_blueprints --filter postgres

# Real AWS mode (EXPENSIVE - use with caution!)
python -m tools.tests.integration.test_all_blueprints --real-aws
```

## Test Blueprint Templates

Located in `tools/tests/data/`. Each template covers different configuration combinations:

### Basic Templates
| File | Description |
|------|-------------|
| `blueprint_minimal.json` | Minimal EC2 - no IAM, no key, default VPC |
| `blueprint_basic.json` | Basic EC2 with IAM and key pair |
| `blueprint_full.json` | EC2 + S3 bucket |

### Web Server Templates
| File | Description |
|------|-------------|
| `blueprint_webserver.json` | Nginx web server with HTTP/HTTPS |
| `blueprint_docker.json` | Docker host with container support |
| `blueprint_nodejs.json` | Node.js application server |

### Database Templates
| File | Description |
|------|-------------|
| `blueprint_postgres_app.json` | Web app with PostgreSQL |
| `blueprint_mysql_app.json` | LAMP stack with MySQL |
| `blueprint_mariadb_app.json` | App with MariaDB (skipped in mock mode) |
| `blueprint_large_db.json` | Large PostgreSQL (500GB, db.m5.large) |
| `blueprint_full_stack.json` | EC2 + PostgreSQL + S3 (complete stack) |

### Instance Type Templates
| File | Description |
|------|-------------|
| `blueprint_compute_optimized.json` | c5.large for CPU workloads |
| `blueprint_memory_optimized.json` | r5.large for memory workloads |
| `blueprint_large_instance.json` | m5.xlarge general purpose |

### Network Templates
| File | Description |
|------|-------------|
| `blueprint_private_subnet.json` | Private subnet (no public IP) |
| `blueprint_custom_ports.json` | Multiple custom application ports |
| `blueprint_udp_ports.json` | UDP ports (DNS, VOIP, gaming) |

### Security Templates
| File | Description |
|------|-------------|
| `blueprint_no_iam.json` | EC2 without IAM role |
| `blueprint_existing_keypair.json` | Uses existing key (skipped in mock) |
| `blueprint_s3_only.json` | EC2 with S3 storage only |

### Region Templates
| File | Description |
|------|-------------|
| `blueprint_eu_region.json` | eu-west-1 (Ireland) deployment |
| `blueprint_ap_region.json` | ap-southeast-1 (Singapore) deployment |

## Test Coverage Matrix

| Feature | Templates Covering It |
|---------|----------------------|
| Default VPC | basic, minimal, webserver, nodejs, s3_only, no_iam |
| New VPC | docker, postgres_app, mysql_app, full_stack, private_subnet, large_db |
| Public Subnet | Most templates |
| Private Subnet | private_subnet |
| t3.micro | minimal, basic, s3_only, existing_keypair, ap_region |
| t3.small | webserver, nodejs, mariadb_app, eu_region |
| t3.medium | docker, custom_ports, udp_ports |
| t3.large | custom_ports |
| m5.large | large_db |
| m5.xlarge | large_instance |
| c5.large | compute_optimized |
| r5.large | memory_optimized |
| PostgreSQL | postgres_app, full_stack, large_db |
| MySQL | mysql_app |
| MariaDB | mariadb_app |
| S3 Bucket | full, docker, full_stack, s3_only, eu_region |
| Generate Key | Most templates |
| Existing Key | existing_keypair |
| No Key | minimal |
| IAM Role | Most templates |
| No IAM Role | minimal, no_iam, ap_region |
| User Data Scripts | webserver, docker, nodejs, mysql_app |
| UDP Protocols | udp_ports |
| Multiple Regions | eu_region, ap_region |

## Mock Mode Limitations

Some features cannot be tested in mock mode (moto):
- **MariaDB engine** - Not supported by moto (use MySQL instead)
- **Existing key pairs** - Requires pre-created key in AWS
- **VPC cleanup** - May show dependency errors (safe to ignore)

## Cleanup Verification

After each test run, the script verifies:
1. EC2 instances terminated
2. RDS databases deleted
3. S3 buckets emptied and deleted
4. IAM roles and instance profiles removed
5. Key pairs deleted (both AWS and local ~/.ssh files)
6. Security groups deleted
7. Subnets deleted
8. VPCs deleted

## Running in CI/CD

For automated testing in CI pipelines:

```bash
# Run in mock mode (no AWS credentials needed)
python -m tools.tests.integration.test_all_blueprints

# Exit code 0 = all passed, 1 = failures
```
