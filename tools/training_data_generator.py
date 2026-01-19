#!/usr/bin/env python3
"""
Shared training data generator utilities for Pockitect.

Provides two generators:
- template-based local generation (deterministic prompt parsing)
- vague/ambiguous prompt generation with defaults and tool simulation
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from storage import create_empty_blueprint, slugify  # type: ignore

try:
    from wizard.pages.project_basics import AWS_REGIONS  # type: ignore
except Exception:
    AWS_REGIONS = [
        ("us-east-1", "US East (N. Virginia)"),
        ("us-east-2", "US East (Ohio)"),
        ("us-west-1", "US West (N. California)"),
        ("us-west-2", "US West (Oregon)"),
        ("eu-west-1", "EU (Ireland)"),
        ("eu-central-1", "EU (Frankfurt)"),
        ("ap-northeast-1", "Asia Pacific (Tokyo)"),
        ("ap-southeast-1", "Asia Pacific (Singapore)"),
    ]

REGION_IDS = [rid for rid, _ in AWS_REGIONS]
DEFAULT_REGION = "us-east-1"


SCENARIO_TEMPLATES = [
    {
        "name": "blog",
        "variations": [
            "Create a simple blog backend with a small EC2 instance running WordPress",
            "Set up a blog infrastructure with Ubuntu server and MySQL database",
            "I need a blog hosting setup with t3.micro instance and PostgreSQL",
            "Deploy a blog platform with EC2, RDS database, and proper security groups",
            "Build a blog backend: small instance, database, and open web ports",
        ],
    },
    {
        "name": "api-server",
        "variations": [
            "I need an API server setup with Node.js and MySQL database",
            "Set up a REST API server with medium instance and database backend",
            "Create an API infrastructure with t3.medium, Node.js, and PostgreSQL",
            "Deploy an API server with Docker support and MySQL database",
            "Build a backend API with EC2 instance and RDS database",
        ],
    },
    {
        "name": "static-website",
        "variations": [
            "Host a static website with nginx on a small EC2 instance",
            "Set up static site hosting with S3 bucket and EC2 for processing",
            "Create a static website infrastructure with nginx and S3 storage",
            "Deploy a static site with t3.micro, nginx, and asset storage",
            "I need static website hosting with EC2 and S3 bucket",
        ],
    },
    {
        "name": "database-backend",
        "variations": [
            "Set up a database server with PostgreSQL and backup storage",
            "Create a dedicated database backend with RDS and EC2 access",
            "Deploy a database infrastructure with MySQL and monitoring",
            "Build a database server with PostgreSQL, 50GB storage, and secure access",
            "I need a database backend with RDS and EC2 instance for management",
        ],
    },
    {
        "name": "docker-host",
        "variations": [
            "Set up a Docker host with container runtime and S3 storage",
            "Create a Docker infrastructure with large instance and container support",
            "Deploy a Docker host with custom VPC and container registry access",
            "Build a Docker server with t3.large, Docker CE, and persistent storage",
            "I need a Docker host with EC2, custom networking, and S3 for images",
        ],
    },
    {
        "name": "full-stack",
        "variations": [
            "Deploy a full-stack application with frontend, backend, and database",
            "Create a complete stack: web server, API, and database infrastructure",
            "Set up full-stack infrastructure with EC2, RDS, and S3",
            "Build a full application stack with multiple services and database",
            "I need a full-stack setup with compute, database, and storage",
        ],
    },
    {
        "name": "microservice",
        "variations": [
            "Set up a microservices architecture with multiple small instances",
            "Create a microservice infrastructure with container support",
            "Deploy microservices with EC2 instances and shared database",
            "Build a microservice platform with Docker and service mesh",
            "I need microservices infrastructure with multiple compute nodes",
        ],
    },
    {
        "name": "data-pipeline",
        "variations": [
            "Create a data processing pipeline with EC2 and S3 storage",
            "Set up a data pipeline infrastructure with compute and storage",
            "Deploy a data processing setup with large instance and S3",
            "Build a data pipeline with EC2, S3, and database for results",
            "I need a data pipeline infrastructure with processing and storage",
        ],
    },
    {
        "name": "game-server",
        "variations": [
            "Set up a game server with high-performance instance and low latency",
            "Create a game server infrastructure with t3.large and custom ports",
            "Deploy a gaming server with optimized instance and network setup",
            "Build a game server with EC2, custom security groups, and monitoring",
            "I need a game server with high-performance compute and networking",
        ],
    },
    {
        "name": "monitoring-stack",
        "variations": [
            "Set up a monitoring infrastructure with Prometheus and Grafana",
            "Create a monitoring stack with EC2, database, and alerting",
            "Deploy monitoring services with multiple instances and storage",
            "Build a monitoring platform with EC2, RDS, and S3 for logs",
            "I need a monitoring infrastructure with compute and database",
        ],
    },
    {
        "name": "caching-layer",
        "variations": [
            "Create a caching infrastructure with Redis and EC2 instances",
            "Set up a caching layer with compute nodes and storage",
            "Deploy a cache infrastructure with EC2 and database backend",
            "Build a caching system with multiple instances and shared storage",
            "I need a caching infrastructure with EC2 and S3 for persistence",
        ],
    },
    {
        "name": "queue-worker",
        "variations": [
            "Set up a queue worker infrastructure with EC2 and message queue",
            "Create a worker infrastructure with compute nodes and database",
            "Deploy queue workers with EC2 instances and shared storage",
            "Build a worker infrastructure with multiple nodes and database",
            "I need queue workers with EC2, database, and S3 for job storage",
        ],
    },
    {
        "name": "e-commerce-backend",
        "variations": [
            "Create an e-commerce backend with EC2, RDS, and S3 for assets",
            "Set up an e-commerce infrastructure with database and storage",
            "Deploy an e-commerce platform with compute, database, and CDN",
            "Build an e-commerce backend with EC2, PostgreSQL, and S3",
            "I need an e-commerce infrastructure with full stack components",
        ],
    },
    {
        "name": "ml-training-server",
        "variations": [
            "Set up a machine learning training server with GPU support simulation",
            "Create an ML training infrastructure with large instance and storage",
            "Deploy an ML server with EC2, S3 for datasets, and database for results",
            "Build an ML training setup with compute, storage, and monitoring",
            "I need an ML training infrastructure with high-memory instance and S3",
        ],
    },
    {
        "name": "file-storage-service",
        "variations": [
            "Create a file storage service with EC2 and S3 backend",
            "Set up a file storage infrastructure with compute and S3",
            "Deploy a storage service with EC2, S3, and database for metadata",
            "Build a file storage system with EC2 and S3 buckets",
            "I need a file storage infrastructure with compute and object storage",
        ],
    },
    {
        "name": "websocket-server",
        "variations": [
            "Set up a WebSocket server with persistent connections and database",
            "Create a WebSocket infrastructure with EC2 and RDS backend",
            "Deploy a WebSocket server with compute, database, and load balancing",
            "Build a WebSocket infrastructure with EC2 and PostgreSQL",
            "I need a WebSocket server with compute and database for state",
        ],
    },
    {
        "name": "batch-processing",
        "variations": [
            "Create a batch processing infrastructure with EC2 and S3",
            "Set up batch jobs infrastructure with compute and storage",
            "Deploy batch processing with EC2, S3 for input/output, and database",
            "Build a batch processing system with EC2 and object storage",
            "I need batch processing infrastructure with compute and S3",
        ],
    },
    {
        "name": "ci-cd-runner",
        "variations": [
            "Set up a CI/CD runner infrastructure with EC2 and S3 for artifacts",
            "Create a CI/CD infrastructure with compute nodes and storage",
            "Deploy CI/CD runners with EC2, S3, and database for job tracking",
            "Build a CI/CD infrastructure with EC2 and artifact storage",
            "I need CI/CD runners with compute and S3 for build artifacts",
        ],
    },
]


INSTANCE_TIERS = {
    "cheap": "t3.micro",
    "small": "t3.small",
    "medium": "t3.medium",
    "bigger": "t3.large",
    "large": "t3.large",
    "powerful": "m5.large",
    "performance": "c5.large",
    "memory": "r5.large",
}


def _pick_region(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return DEFAULT_REGION


def _pick_instance(scale_hint: Optional[str]) -> str:
    if not scale_hint:
        return "t3.micro"
    return INSTANCE_TIERS.get(scale_hint, "t3.micro")


def _ports_for(kind: str) -> List[Dict[str, object]]:
    rules = []
    if kind in ("web", "blog", "api", "app"):
        rules.extend(
            [
                {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
                {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"},
            ]
        )
    rules.insert(
        0, {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}
    )
    return rules


def _apply_overrides(base: Dict[str, object], overrides: Dict[str, object]) -> Dict[str, object]:
    def merge(dst: Dict[str, object], src: Dict[str, object]) -> Dict[str, object]:
        for key, value in src.items():
            if isinstance(value, dict) and isinstance(dst.get(key), dict):
                merge(dst[key], value)  # type: ignore[index]
            else:
                dst[key] = value
        return dst

    return merge(base, overrides)


def _build_blueprint(
    name: str,
    description: str,
    region: str,
    instance_type: str,
    ports: List[Dict[str, object]],
    db: Optional[Dict[str, object]] = None,
    s3_bucket: Optional[Dict[str, object]] = None,
    user_data: str = "",
    image_id: str = "ubuntu-22.04",
    image_name: str = "Ubuntu 22.04",
) -> Dict[str, object]:
    base = create_empty_blueprint(name, description, region, owner="developer")
    overrides: Dict[str, object] = {
        "network": {
            "vpc_env": "dev",
            "subnet_type": "public",
            "rules": ports,
            "status": "pending",
        },
        "compute": {
            "instance_type": instance_type,
            "image_id": image_id,
            "image_name": image_name,
            "user_data": user_data,
            "status": "pending",
        },
        "data": {
            "db": db,
            "s3_bucket": s3_bucket,
        },
        "security": {
            "key_pair": {
                "name": f"{slugify(name)}-key",
                "mode": "generate",
                "status": "pending",
            },
            "certificate": {
                "mode": "skip",
                "status": "skipped",
            },
            "iam_role": {
                "enabled": True,
                "role_name": f"{slugify(name)}-role",
                "status": "pending",
            },
        },
    }
    return _apply_overrides(base, overrides)


def _tool_simulation_block(prompt: str) -> str:
    return "\n".join(
        [
            "[tool_simulation]",
            "ContextProvider.get_projects_summary -> No projects found.",
            "ContextProvider.get_aws_specs -> using defaults for region/instance.",
            f'User prompt: "{prompt}"',
            "[/tool_simulation]",
            "",
            prompt,
        ]
    )


def _scenario_pool() -> List[Tuple[str, str, Dict[str, object]]]:
    return [
        (
            "portfolio-website",
            "I want to host my portfolio website, keep it cheap.",
            {"kind": "web", "scale": "cheap", "db": None, "s3": {"name": "portfolio-assets"}},
        ),
        (
            "small-blog",
            "I need a blog with a database but nothing too powerful.",
            {"kind": "blog", "scale": "small", "db": {"engine": "postgres", "size": 20}, "s3": None},
        ),
        (
            "api-backend",
            "Need an API backend with Node, not sure what size.",
            {"kind": "api", "scale": "medium", "db": {"engine": "mysql", "size": 30}, "s3": None},
        ),
        (
            "containers",
            "Something for running containers, keep it simple.",
            {"kind": "app", "scale": "medium", "db": None, "s3": {"name": "container-artifacts"}},
        ),
        (
            "mobile-backend",
            "A backend for my mobile app with a small database.",
            {"kind": "api", "scale": "small", "db": {"engine": "postgres", "size": 20}, "s3": None},
        ),
        (
            "ml-experiments",
            "I want something for ML experiments, nothing massive.",
            {"kind": "app", "scale": "performance", "db": {"engine": "postgres", "size": 50}, "s3": {"name": "ml-datasets"}},
        ),
        (
            "analytics",
            "Need a light analytics server, probably with storage.",
            {"kind": "app", "scale": "medium", "db": {"engine": "postgres", "size": 50}, "s3": {"name": "analytics-storage"}},
        ),
        (
            "internal-tool",
            "Set up a small internal tool server. Defaults are fine.",
            {"kind": "web", "scale": "small", "db": None, "s3": None},
        ),
    ]


def _build_db(engine: Optional[str], size: int) -> Dict[str, object]:
    if not engine:
        return {
            "engine": None,
            "instance_class": None,
            "allocated_storage_gb": None,
            "username": None,
            "password": None,
            "endpoint": None,
            "status": "skipped",
        }
    return {
        "engine": engine,
        "instance_class": "db.t3.micro" if size <= 20 else "db.t3.small",
        "allocated_storage_gb": size,
        "username": "admin",
        "password": None,
        "endpoint": None,
        "status": "pending",
    }


def _build_s3(name: Optional[str]) -> Dict[str, object]:
    if not name:
        return {"name": None, "arn": None, "status": "skipped"}
    return {"name": name, "arn": None, "status": "pending"}


def generate_yaml_from_prompt(prompt: str, scenario_name: str) -> Dict[str, object]:
    prompt_lower = prompt.lower()

    project_name = scenario_name.replace("-", "_")
    region = "us-east-1"
    instance_type = "t3.micro"
    has_database = False
    db_engine = None
    db_storage = 20
    db_class = "db.t3.micro"
    has_s3 = False
    s3_name = None
    ports: List[Dict[str, object]] = []
    user_data = ""

    region_keywords = {
        "us-east-1": ["us east", "virginia", "n. virginia"],
        "us-east-2": ["us east ohio", "ohio"],
        "us-west-1": ["us west", "california", "n. california"],
        "us-west-2": ["oregon", "us west oregon"],
        "eu-west-1": ["ireland", "eu ireland", "europe ireland"],
        "eu-central-1": ["frankfurt", "eu frankfurt", "germany"],
        "ap-southeast-1": ["singapore", "asia singapore"],
        "ap-northeast-1": ["tokyo", "japan"],
        "ap-south-1": ["mumbai", "india"],
    }
    for reg, keywords in region_keywords.items():
        if any(kw in prompt_lower for kw in keywords):
            region = reg
            break

    if "t3.large" in prompt_lower or ("large" in prompt_lower and "instance" in prompt_lower):
        instance_type = "t3.large"
    elif "t3.medium" in prompt_lower or ("medium" in prompt_lower and "instance" in prompt_lower):
        instance_type = "t3.medium"
    elif "t3.small" in prompt_lower or ("small" in prompt_lower and "instance" in prompt_lower):
        instance_type = "t3.small"
    else:
        instance_type = "t3.micro"

    if any(word in prompt_lower for word in ["database", "db", "mysql", "postgres", "postgresql", "rds"]):
        has_database = True
        if "mysql" in prompt_lower:
            db_engine = "mysql"
        elif "postgres" in prompt_lower:
            db_engine = "postgres"
        else:
            db_engine = "postgres"

        if "50" in prompt or "50gb" in prompt_lower:
            db_storage = 50
            db_class = "db.t3.small"
        elif "100" in prompt or "100gb" in prompt_lower:
            db_storage = 100
            db_class = "db.t3.medium"
        else:
            db_storage = 20
            db_class = "db.t3.micro"

    if "s3" in prompt_lower or "bucket" in prompt_lower or ("storage" in prompt_lower and "object" in prompt_lower):
        has_s3 = True
        s3_name = f"{scenario_name}-storage"

    if "ssh" in prompt_lower or "22" in prompt:
        ports.append({"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"})

    if "http" in prompt_lower or "80" in prompt:
        ports.append({"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"})

    if "https" in prompt_lower or "443" in prompt:
        ports.append({"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"})

    if not ports:
        ports.append({"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"})
        ports.append({"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"})

    if "docker" in prompt_lower:
        user_data = (
            "#!/bin/bash\napt update\napt install -y apt-transport-https ca-certificates curl "
            "software-properties-common\ncurl -fsSL https://download.docker.com/linux/ubuntu/gpg | "
            "apt-key add -\nadd-apt-repository \"deb [arch=amd64] https://download.docker.com/linux/ubuntu "
            "$(lsb_release -cs) stable\"\napt update\napt install -y docker-ce docker-ce-cli "
            "containerd.io\nsystemctl enable docker\nsystemctl start docker"
        )
    elif "nginx" in prompt_lower:
        user_data = "#!/bin/bash\napt update\napt install -y nginx\nsystemctl enable nginx\nsystemctl start nginx"
    elif "node" in prompt_lower or "nodejs" in prompt_lower:
        user_data = "#!/bin/bash\ncurl -fsSL https://deb.nodesource.com/setup_20.x | bash -\napt install -y nodejs\nnpm install -g pm2"

    yaml_data: Dict[str, object] = {
        "project": {
            "name": project_name,
            "description": f"{scenario_name.replace('-', ' ').title()} infrastructure",
            "region": region,
            "owner": "developer",
        },
        "network": {
            "vpc_mode": "default",
            "vpc_cidr": None,
            "subnet_type": "public",
            "rules": ports,
        },
        "compute": {
            "instance_type": instance_type,
            "image_id": None,
            "image_name": "ubuntu-22.04",
            "user_data": user_data,
        },
        "data": {
            "db": {
                "engine": db_engine,
                "instance_class": db_class,
                "allocated_storage_gb": db_storage,
                "username": f"{project_name}_admin",
            } if has_database else None,
            "s3_bucket": {
                "name": s3_name,
            } if has_s3 else None,
        },
        "security": {
            "key_pair": {
                "mode": "generate",
                "name": f"{project_name}-key",
            },
            "certificate": {
                "mode": "skip",
            },
            "iam_role": {
                "enabled": True,
                "role_name": f"{project_name}-role",
            },
        },
    }

    return yaml_data


def generate_template_examples(
    count: int,
    output_dir: Path,
    scenario: Optional[str] = None,
) -> List[Dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_files = list(output_dir.glob("*.json"))
    start_num = len(existing_files) + 1

    generated: List[Dict[str, object]] = []

    if scenario:
        templates = [t for t in SCENARIO_TEMPLATES if t["name"] == scenario]
        if not templates:
            templates = SCENARIO_TEMPLATES
    else:
        templates = SCENARIO_TEMPLATES

    for i in range(count):
        template = templates[i % len(templates)]
        scenario_name = template["name"]
        variation_idx = (i // len(templates)) % len(template["variations"])
        prompt = template["variations"][variation_idx]

        yaml_data = generate_yaml_from_prompt(prompt, scenario_name)

        num = start_num + i
        name = f"{num:03d}-{scenario_name}"
        prompt_file = output_dir / f"{name}.prompt.txt"
        json_file = output_dir / f"{name}.json"

        prompt_file.write_text(prompt, encoding="utf-8")
        json_file.write_text(json.dumps(yaml_data, indent=2), encoding="utf-8")

        generated.append({"prompt": prompt, "yaml": yaml_data, "name": name})

    return generated


def generate_vague_examples(
    count: int,
    output_dir: Path,
    tool_simulation_ratio: float = 0.2,
    seed: int = 42,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(seed)

    existing = list(output_dir.glob("*.json"))
    numbers = []
    for path in existing:
        match = re.match(r"^(\d+)-", path.stem)
        if match:
            numbers.append(int(match.group(1)))
    start_num = max(numbers) + 1 if numbers else 1

    scenarios = _scenario_pool()
    created = 0

    for i in range(count):
        name, prompt, attrs = scenarios[i % len(scenarios)]
        region = _pick_region(attrs.get("region"))  # type: ignore[arg-type]
        instance_type = _pick_instance(attrs.get("scale"))  # type: ignore[arg-type]
        ports = _ports_for(attrs.get("kind", "web"))  # type: ignore[arg-type]
        db = _build_db(attrs.get("db", {}).get("engine"), attrs.get("db", {}).get("size", 20)) if attrs.get("db") else _build_db(None, 0)
        s3 = _build_s3(attrs.get("s3", {}).get("name")) if attrs.get("s3") else _build_s3(None)

        description = f"{name.replace('-', ' ').title()} infrastructure"
        blueprint = _build_blueprint(
            name=name,
            description=description,
            region=region,
            instance_type=instance_type,
            ports=ports,
            db=db,
            s3_bucket=s3,
        )

        prompt_text = prompt
        if random.random() < tool_simulation_ratio:
            prompt_text = _tool_simulation_block(prompt)

        num = start_num + i
        filename = f"{num:03d}-{name}"
        prompt_file = output_dir / f"{filename}.prompt.txt"
        json_file = output_dir / f"{filename}.json"

        prompt_file.write_text(prompt_text, encoding="utf-8")
        json_file.write_text(json.dumps(blueprint, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        created += 1

    return created
