# Pockitect MVP – Refined Architecture & Implementation Plan
*Version: 2026-01 – Wizard-first, filesystem-persisted, boto3-driven, local-AI training oriented*

## Core Philosophy & Constraints (MVP)

- Desktop-first, local-first application (PyQt6 + embedded React or plain Qt if simpler)
- **No PostgreSQL / external database** for MVP – everything lives as JSON files on disk
- One big wizard → one JSON blueprint per project
- Goal = produce clean, consistent JSON → train small local LLM on (natural language → template) pairs
- Minimal tabs: **Projects** (list + open wizard) + **AI Chat** (future natural-language interface)
- AWS only (for MVP); focus = EC2 + VPC/SG + optional RDS + optional S3 + key pair + basic IAM
- Deployment order enforced in backend logic (not wizard UI order)

## High-Level File / Data Flow

```
user → wizard (React / Qt forms)
       ↓
in-memory blueprint object (Python dict)
       ↓ (on "Deploy")
backend re-orders sections → boto3 sequence
       ↓
JSON written to disk: ./projects/<project-slug>.json
       ↓ (background poll)
periodic describe_* calls → update status fields in same JSON
       ↓
UI watches file / folder → refreshes status
```

## Project JSON Structure (API / deploy target shape)

This is the **canonical shape** the deployment engine expects.

```json
{
  "project": {
    "name": "brendens-blog",
    "description": "Personal static site + small Postgres backend",
    "region": "us-east-2",
    "created_at": "2026-01-16T13:54:00Z",
    "owner": "brenden"
  },

  "network": {
    "vpc_id": null,
    "subnet_id": null,
    "security_group_id": null,
    "rules": [
      { "port": 80,  "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"  },
      { "port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS" }
    ],
    "status": "pending"
  },

  "compute": {
    "instance_type": "t3.micro",
    "image_id": "ami-0abcdef1234567890",
    "user_data": "#!/bin/bash\napt update && apt install -y nginx",
    "instance_id": null,
    "status": "pending"
  },

  "data": {
    "db": {
      "engine": "postgres",
      "instance_class": "db.t3.micro",
      "allocated_storage_gb": 20,
      "username": "admin",
      "password": null,
      "endpoint": null,
      "status": "pending"
    },
    "s3_bucket": {
      "name": "brendens-blog-static-us-east-2",
      "arn": null,
      "status": "pending"
    }
  },

  "security": {
    "key_pair": {
      "name": "brendens-blog-key-20260116",
      "key_pair_id": null,
      "private_key_pem": null,
      "status": "pending"
    },
    "certificate": {
      "domain": null,
      "cert_arn": null,
      "status": "skipped"
    },
    "iam_role": {
      "role_name": "pockitect-blog-instance-role",
      "policy_document": {},
      "arn": null,
      "instance_profile_arn": null,
      "status": "pending"
    }
  }
}
```

## Wizard Screen Sequence (User Mental Model)

1. **Project Basics**  
   - Project name (slug auto-generated)  
   - Short description  
   - Region (dropdown – fetched once at app start)

2. **Compute**  
   - Instance type (filtered by region quota)  
   - OS image / AMI (filtered list for region)  
   - User data script (textarea, optional)

3. **Network**  
   - VPC: default or new (if new → CIDR input)  
   - Subnet: public (default)  
   - Firewall rules: simple presets + custom port/protocol/CIDR

4. **Data (optional toggle)**  
   - Database: yes/no  
     - If yes: engine, size, username, password (twice)  
   - S3 Bucket: yes/no  
     - If yes: bucket name suggestion (auto-append region)

5. **Security**  
   - SSH Key: generate new (default) / use existing  
   - Certificate: skip / ACM (domain) / bring your own (PEM paste)  
   - IAM Role: auto-generate (review summary shown)

6. **Review & Deploy**  
   - Read-only summary of all choices  
   - "Deploy" button → triggers boto3 sequence

## Deployment Execution Order (Backend)

1. Create / ensure VPC & subnet → fill vpc_id, subnet_id
2. Create security group + rules → fill security_group_id
3. Create key pair (if requested) → save PEM locally → fill key_pair_id
4. Generate IAM role & instance profile (least privilege scan) → fill arns
5. Launch EC2 → fill instance_id
6. Create RDS (if requested) → fill endpoint
7. Create S3 bucket (if requested) → fill arn
8. Poll loop (every 30–60 s): describe_* → update status fields

## Quota Pre-fetch (App Startup / Background)

- On launch (or hourly):  
  - `describe_account_attributes()`  
  - `describe_instance_types()` (filter running / available)  
  - `describe_reserved_instances()` (if relevant)  
- Cache in memory → filter dropdowns / disable sections  
  - Example: no p3/p4 GPU quota → hide GPU instance types  
  - No DB instances left → disable "Add Database" toggle

## Future AI Training Data Pipeline

1. Every successful deploy → copy final JSON
2. Manually / semi-automatically write natural-language prompt that would have led to this blueprint
3. Save pair:  
   ```
   ./training/
     001-blog-postgres.json
     001-blog-postgres.prompt.txt
   ```
4. Later: fine-tune small model (Mistral-7B / Phi-3 / Llama-3.1-8B) on these pairs
5. Separate lightweight agent (NIST/security-tuned) → rewrites user prompt with best practices → feeds template generator

## Next Implementation Steps (Suggested Order)

1. Filesystem project store (`./projects/`, `./training/`)
2. Wizard skeleton (collect all fields → in-memory dict)
3. Quota pre-fetch service (startup task)
4. Boto3 wrapper – create/read functions per resource type
5. Deployment orchestrator (ordered sequence + status update loop)
6. Key/cert local save logic (~/.ssh/ or app-specific folder)
7. UI refresh from filesystem watcher
8. First 5–10 manual prompt → JSON pairs (bootstrap training set)

Good luck with the implementation.
