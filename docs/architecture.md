# Pockitect – Architecture & Design Notes

## Overview

Pockitect is a PySide6-based desktop wizard application for deploying AWS infrastructure. This document covers the high-level architecture, security model, and key design decisions.

---

## AWS Authentication Flow

### Security Model

- **Credentials are NEVER stored in plaintext files, environment variables, or source code.**
- The system keyring (`keyring` library) is used for secure, encrypted credential storage.
- Service name: `"PockitectApp"`
- Username keys: `"aws_access_key_id"` and `"aws_secret_access_key"`

### Authentication Page Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      AWSAuthPage Load                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  Check keyring for existing  │
               │       credentials            │
               └──────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌────────────────┐            ┌────────────────┐
     │  Found: Pre-   │            │  Not Found:    │
     │  fill inputs   │            │  Empty inputs  │
     └────────────────┘            └────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  User Reviews/Enters Creds   │
               │  + Copies IAM Policy         │
               └──────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  "Test & Save" Button Click  │
               └──────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  Validate via boto3 calls:   │
               │  - sts.get_caller_identity() │
               │  - s3.list_buckets()         │
               │  - ec2.describe_instances()  │
               └──────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌────────────────┐            ┌────────────────┐
     │  All Pass:     │            │  Any Fail:     │
     │  Save to       │            │  Show error    │
     │  keyring       │            │  message with  │
     │  + proceed     │            │  guidance      │
     └────────────────┘            └────────────────┘
```

### IAM Policy (Least Privilege)

The application requires the following minimal IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2Permissions",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeImages",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:CreateVpc",
        "ec2:CreateSubnet",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:CreateKeyPair",
        "ec2:RunInstances",
        "ec2:CreateTags",
        "ec2:TerminateInstances",
        "ec2:DeleteSecurityGroup",
        "ec2:DeleteKeyPair"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Permissions",
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:CreateBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:DeleteBucket"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSPermissions",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:CreateDBInstance",
        "rds:DeleteDBInstance"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:CreateInstanceProfile",
        "iam:DeleteInstanceProfile",
        "iam:AddRoleToInstanceProfile",
        "iam:RemoveRoleFromInstanceProfile"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMPassRoleToEC2",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/pockitect-*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ec2.amazonaws.com"
        }
      }
    },
    {
      "Sid": "STSPermissions",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Application Structure

### Login Gate

The application requires AWS authentication before any access:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Start                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │    AWSLoginDialog (Modal)    │
               │   - Cannot be dismissed      │
               │   - Gates all app access     │
               └──────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │    MainWindow (Projects)     │
               │   - Only shown after auth    │
               └──────────────────────────────┘
```

### Wizard Page Structure

The wizard uses `QWizard` with `QStackedWidget` for page navigation.

**Page Order**:

1. **ProjectBasicsPage** – Project name, region, description
2. **ComputePage** – EC2 instance configuration
3. **NetworkPage** – VPC, subnet, security group rules
4. **DataPage** – RDS database, S3 bucket (optional)
5. **SecurityPage** – SSH keys, certificates, IAM roles
6. **ReviewPage** – Summary and deploy button

### Signal/Slot Connections

```
AWSLoginDialog
    └── accept() → allows main window to show
    └── reject() → exits application

InfrastructureWizard
    ├── currentIdChanged → updates dependent fields
    ├── customButtonClicked → save draft / deploy
    └── finished → emit blueprint_created

DeploymentDialog
    └── deployment_finished(Signal) → save updated blueprint
```

---

## Class Structure

### Core Classes

- `InfrastructureWizard(QWizard)` – Main wizard orchestrator
- `StyledWizardPage(QWizardPage)` – Base class with styling helpers
- `AWSAuthPage(StyledWizardPage)` – Authentication and credential validation
- `DeploymentOrchestrator` – Async deployment execution
- `AWSResourceManager` – boto3 wrapper for all AWS operations

### Storage Classes

- `keyring` module – Secure credential storage
- `storage.py` – Project JSON file management

---

## Error Handling Strategy

### Credential Validation Errors

| Error Type | User Message |
|------------|--------------|
| Invalid credentials | "The provided AWS credentials are invalid. Please check your Access Key ID and Secret Access Key." |
| Access denied (S3) | "Missing permission: s3:ListAllMyBuckets. Please update your IAM policy." |
| Access denied (EC2) | "Missing permission: ec2:DescribeInstances. Please update your IAM policy." |
| Network error | "Unable to connect to AWS. Please check your internet connection." |

### Deployment Errors

- Step-by-step error tracking with rollback guidance
- Resource IDs saved even on partial failure for cleanup

---

## Security Considerations

1. **No plaintext credentials** – All AWS keys stored in system keyring
2. **No credentials in logs** – Secret keys masked in all output
3. **Private keys secured** – SSH keys saved with 600 permissions to ~/.ssh/
4. **Password handling** – DB passwords entered at deploy time, never persisted
5. **Policy principle** – Least privilege IAM policy documented and enforced

---

*Last updated: 2026-01-16*
