#!/usr/bin/env python3
"""
Create diverse test blueprints for manual testing.

This script creates a variety of blueprint configurations and saves them
to the projects/ directory so they appear in the Pockitect app.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage import save_project, init_storage

# Initialize storage
init_storage()

# Template function to create blueprint structure
def create_blueprint(name, description, region, **kwargs):
    """Create a blueprint dict with common defaults."""
    blueprint = {
        "project": {
            "name": name,
            "description": description,
            "region": region,
            "owner": "tester"
        },
        "network": kwargs.get("network", {
            "vpc_mode": "new",
            "vpc_cidr": "10.0.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}
            ],
            "status": "pending"
        }),
        "compute": kwargs.get("compute", {
            "instance_type": "t3.micro",
            "image_id": "ubuntu-22.04",
            "user_data": "",
            "status": "pending"
        }),
        "data": kwargs.get("data", {
            "db": {"status": "skipped"},
            "s3_bucket": {"status": "skipped"}
        }),
        "security": kwargs.get("security", {
            "key_pair": {
                "mode": "generate",
                "name": f"{name}-key",
                "status": "pending"
            },
            "iam_role": {
                "enabled": True,
                "role_name": f"{name}-role",
                "status": "pending"
            }
        })
    }
    return blueprint


# Define all blueprints
blueprints = [
    # 1. Basic minimal (smallest possible)
    create_blueprint(
        "minimal-test",
        "Minimal EC2 instance with default VPC",
        "us-east-1",
        network={
            "vpc_mode": "default",
            "subnet_type": "public",
            "rules": [{"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}],
            "status": "pending"
        },
        security={
            "key_pair": {"mode": "generate", "name": "minimal-test-key", "status": "pending"},
            "iam_role": {"enabled": False, "status": "pending"}
        }
    ),
    
    # 2. High memory instance
    create_blueprint(
        "high-memory-instance",
        "r5.xlarge instance with 32GB RAM for memory-intensive workloads",
        "us-east-1",
        compute={
            "instance_type": "r5.xlarge",
            "image_id": "ubuntu-22.04",
            "user_data": "",
            "status": "pending"
        }
    ),
    
    # 3. Compute optimized
    create_blueprint(
        "compute-optimized",
        "c5.2xlarge compute-optimized instance for CPU-intensive tasks",
        "us-east-1",
        compute={
            "instance_type": "c5.2xlarge",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\necho 'Compute optimized instance ready'",
            "status": "pending"
        }
    ),
    
    # 4. Multi-port web server
    create_blueprint(
        "web-server-multi-port",
        "Web server with HTTP, HTTPS, and custom ports",
        "us-east-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.1.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
                {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"},
                {"port": 8080, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "Custom HTTP"},
                {"port": 3000, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "Node.js"}
            ],
            "status": "pending"
        },
        compute={
            "instance_type": "t3.medium",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update && apt install -y nginx",
            "status": "pending"
        }
    ),
    
    # 5. Private subnet only
    create_blueprint(
        "private-subnet-only",
        "EC2 instance in private subnet (no direct internet)",
        "us-east-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.2.0.0/16",
            "subnet_type": "private",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "10.0.0.0/8", "description": "SSH (internal only)"}
            ],
            "status": "pending"
        }
    ),
    
    # 6. PostgreSQL database app
    create_blueprint(
        "postgres-app",
        "EC2 + PostgreSQL RDS instance",
        "us-east-1",
        compute={
            "instance_type": "t3.medium",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update && apt install -y postgresql-client",
            "status": "pending"
        },
        data={
            "db": {
                "engine": "postgres",
                "instance_class": "db.t3.small",
                "allocated_storage_gb": 100,
                "username": "admin",
                "status": "pending"
            },
            "s3_bucket": {"status": "skipped"}
        },
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.3.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 5432, "protocol": "tcp", "cidr": "10.0.0.0/8", "description": "PostgreSQL (private)"}
            ],
            "status": "pending"
        }
    ),
    
    # 7. MySQL database app
    create_blueprint(
        "mysql-app",
        "EC2 + MySQL RDS instance",
        "us-east-1",
        compute={
            "instance_type": "t3.medium",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update && apt install -y mysql-client",
            "status": "pending"
        },
        data={
            "db": {
                "engine": "mysql",
                "instance_class": "db.t3.small",
                "allocated_storage_gb": 50,
                "username": "admin",
                "status": "pending"
            },
            "s3_bucket": {"status": "skipped"}
        }
    ),
    
    # 8. S3-only (no database)
    create_blueprint(
        "s3-storage-app",
        "EC2 instance with S3 bucket for file storage",
        "us-east-1",
        compute={
            "instance_type": "t3.small",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update && apt install -y awscli",
            "status": "pending"
        },
        data={
            "db": {"status": "skipped"},
            "s3_bucket": {
                "name": "pockitect-s3-storage-assets",
                "status": "pending"
            }
        }
    ),
    
    # 9. Full stack (EC2 + RDS + S3)
    create_blueprint(
        "full-stack-app",
        "Complete stack: EC2 + PostgreSQL + S3 bucket",
        "us-east-1",
        compute={
            "instance_type": "t3.large",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update && apt install -y nginx postgresql-client awscli",
            "status": "pending"
        },
        data={
            "db": {
                "engine": "postgres",
                "instance_class": "db.t3.medium",
                "allocated_storage_gb": 200,
                "username": "admin",
                "status": "pending"
            },
            "s3_bucket": {
                "name": "pockitect-full-stack-assets",
                "status": "pending"
            }
        },
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.4.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
                {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"}
            ],
            "status": "pending"
        }
    ),
    
    # 10. No IAM role
    create_blueprint(
        "no-iam-role",
        "EC2 instance without IAM role (minimal permissions)",
        "us-east-1",
        security={
            "key_pair": {"mode": "generate", "name": "no-iam-role-key", "status": "pending"},
            "iam_role": {"enabled": False, "status": "pending"}
        }
    ),
    
    # 11. Docker container host
    create_blueprint(
        "docker-host",
        "EC2 instance configured for Docker containers",
        "us-east-1",
        compute={
            "instance_type": "t3.medium",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update\napt install -y docker.io docker-compose\nsystemctl enable docker\nsystemctl start docker\nusermod -aG docker ubuntu",
            "status": "pending"
        },
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.5.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
                {"port": 2376, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "Docker daemon"}
            ],
            "status": "pending"
        }
    ),
    
    # 12. Node.js application server
    create_blueprint(
        "nodejs-server",
        "EC2 instance configured for Node.js application",
        "us-east-1",
        compute={
            "instance_type": "t3.small",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\napt update\ncurl -fsSL https://deb.nodesource.com/setup_18.x | bash -\napt install -y nodejs\nnpm install -g pm2",
            "status": "pending"
        },
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.6.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 3000, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "Node.js"},
                {"port": 8080, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "Custom port"}
            ],
            "status": "pending"
        }
    ),
    
    # 13. EU region deployment
    create_blueprint(
        "eu-west-deployment",
        "Basic EC2 instance in EU West (Ireland) region",
        "eu-west-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.7.0.0/16",
            "subnet_type": "public",
            "rules": [{"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}],
            "status": "pending"
        }
    ),
    
    # 14. Asia Pacific region
    create_blueprint(
        "ap-southeast-deployment",
        "Basic EC2 instance in Asia Pacific (Singapore) region",
        "ap-southeast-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.8.0.0/16",
            "subnet_type": "public",
            "rules": [{"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}],
            "status": "pending"
        }
    ),
    
    # 15. UDP ports (for gaming/media servers)
    create_blueprint(
        "udp-services",
        "EC2 instance with UDP port rules for gaming/media",
        "us-east-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.9.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
                {"port": 25565, "protocol": "udp", "cidr": "0.0.0.0/0", "description": "Minecraft"},
                {"port": 27015, "protocol": "udp", "cidr": "0.0.0.0/0", "description": "Steam"},
                {"port": 7777, "protocol": "udp", "cidr": "0.0.0.0/0", "description": "Ark/Valheim"}
            ],
            "status": "pending"
        },
        compute={
            "instance_type": "t3.large",
            "image_id": "ubuntu-22.04",
            "user_data": "#!/bin/bash\necho 'Game server ready'",
            "status": "pending"
        }
    ),
    
    # 16. Large RDS database
    create_blueprint(
        "large-database",
        "PostgreSQL RDS with large storage (500GB)",
        "us-east-1",
        compute={
            "instance_type": "t3.medium",
            "image_id": "ubuntu-22.04",
            "user_data": "",
            "status": "pending"
        },
        data={
            "db": {
                "engine": "postgres",
                "instance_class": "db.t3.large",
                "allocated_storage_gb": 500,
                "username": "admin",
                "status": "pending"
            },
            "s3_bucket": {"status": "skipped"}
        }
    ),
    
    # 17. Smallest possible (t3.nano)
    create_blueprint(
        "t3-nano-instance",
        "Smallest t3.nano instance for testing",
        "us-east-1",
        compute={
            "instance_type": "t3.nano",
            "image_id": "ubuntu-22.04",
            "user_data": "",
            "status": "pending"
        },
        security={
            "key_pair": {"mode": "generate", "name": "t3-nano-instance-key", "status": "pending"},
            "iam_role": {"enabled": False, "status": "pending"}
        }
    ),
    
    # 18. Large instance (t3.2xlarge)
    create_blueprint(
        "t3-2xlarge-instance",
        "Large t3.2xlarge instance with 8 vCPUs",
        "us-east-1",
        compute={
            "instance_type": "t3.2xlarge",
            "image_id": "ubuntu-22.04",
            "user_data": "",
            "status": "pending"
        }
    ),
    
    # 19. Restricted security (limited SSH access)
    create_blueprint(
        "restricted-access",
        "EC2 with restricted SSH access (only specific IP range)",
        "us-east-1",
        network={
            "vpc_mode": "new",
            "vpc_cidr": "10.10.0.0/16",
            "subnet_type": "public",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "203.0.113.0/24", "description": "SSH (restricted)"}
            ],
            "status": "pending"
        }
    ),
    
    # 20. Multi-AMI (Amazon Linux 2)
    create_blueprint(
        "amazon-linux2",
        "EC2 instance using Amazon Linux 2 AMI",
        "us-east-1",
        compute={
            "instance_type": "t3.micro",
            "image_id": "amazon-linux-2",
            "user_data": "#!/bin/bash\nyum update -y",
            "status": "pending"
        }
    ),
]

# Save all blueprints
print(f"Creating {len(blueprints)} test blueprints...")
for blueprint in blueprints:
    try:
        file_path = save_project(blueprint)
        print(f"✓ Created: {blueprint['project']['name']} -> {file_path.name}")
    except Exception as e:
        print(f"✗ Failed to create {blueprint['project']['name']}: {e}")

print(f"\n✓ Successfully created {len(blueprints)} blueprints in projects/ directory")
print("   These will appear in the Pockitect app's Projects tab!")
