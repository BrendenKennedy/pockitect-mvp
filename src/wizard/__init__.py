# Pockitect MVP - Wizard Package
"""
PySide6-based wizard for creating AWS infrastructure blueprints.

Screens:
    1. Project Basics - Name, description, region
    2. Compute - Instance type, AMI, user data
    3. Network - VPC, subnet, security group rules
    4. Data - Optional RDS and S3 configuration
    5. Security - Key pair, certificate, IAM role
    6. Review & Deploy - Summary and deploy button
"""

from .wizard import InfrastructureWizard

__all__ = ["InfrastructureWizard"]
