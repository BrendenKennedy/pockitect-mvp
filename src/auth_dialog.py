"""
AWS Authentication Login Dialog

A modal dialog that gates access to the entire application.
Shows on startup, validates credentials, and only allows
access to the main app after successful authentication.
"""

import json
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox, QMessageBox,
    QApplication, QGroupBox, QFormLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont

from app.core.config import (
    KEYRING_SERVICE,
    KEYRING_USER_ACCESS_KEY,
    KEYRING_USER_SECRET_KEY,
)
from app.core.aws.credentials_helper import get_session

# Try to import keyring
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

# Try to import pyperclip as fallback
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


# Full IAM policy required for the application (create AND delete)
REQUIRED_IAM_POLICY = {
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
                "ec2:DescribeSecurityGroupRules",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeNatGateways",
                "ec2:DescribeAddresses",
                "ec2:DescribeVolumes",
                "ec2:DescribeRouteTables",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeVpcEndpoints",
                "ec2:DescribeVpcPeeringConnections",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeNetworkAcls",
                "ec2:CreateVpc",
                "ec2:DeleteVpc",
                "ec2:ModifyVpcAttribute",
                "ec2:CreateSubnet",
                "ec2:DeleteSubnet",
                "ec2:ModifySubnetAttribute",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupEgress",
                "ec2:CreateInternetGateway",
                "ec2:DeleteInternetGateway",
                "ec2:AttachInternetGateway",
                "ec2:DetachInternetGateway",
                "ec2:DeleteVpcEndpoints",
                "ec2:DeleteVpcPeeringConnection",
                "ec2:DeleteNetworkInterface",
                "ec2:DetachNetworkInterface",
                "ec2:DeleteNetworkAcl",
                "ec2:ReleaseAddress",
                "ec2:DeleteVolume",
                "ec2:DetachVolume",
                "ec2:CreateRouteTable",
                "ec2:DeleteRouteTable",
                "ec2:CreateRoute",
                "ec2:DeleteRoute",
                "ec2:AssociateRouteTable",
                "ec2:DisassociateRouteTable",
                "ec2:CreateKeyPair",
                "ec2:DeleteKeyPair",
                "ec2:RunInstances",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:TerminateInstances",
                "ec2:CreateTags"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3Permissions",
            "Effect": "Allow",
            "Action": [
                "s3:ListAllMyBuckets",
                "s3:ListBucket",
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:PutBucketPublicAccessBlock",
                "s3:PutBucketTagging",
                "s3:GetBucketTagging",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucketVersions",
                "s3:DeleteObjectVersion"
            ],
            "Resource": "*"
        },
        {
            "Sid": "RDSPermissions",
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds:DescribeDBSubnetGroups",
                "rds:CreateDBInstance",
                "rds:StartDBInstance",
                "rds:StopDBInstance",
                "rds:DeleteDBInstance",
                "rds:CreateDBSubnetGroup",
                "rds:DeleteDBSubnetGroup",
                "rds:AddTagsToResource",
                "rds:ListTagsForResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:ListRoles",
                "iam:ListRoleTags",
                "iam:TagRole",
                "iam:UntagRole",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies",
                "iam:ListInstanceProfilesForRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:CreateInstanceProfile",
                "iam:DeleteInstanceProfile",
                "iam:GetInstanceProfile",
                "iam:TagInstanceProfile",
                "iam:AddRoleToInstanceProfile",
                "iam:RemoveRoleFromInstanceProfile"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CreateServiceLinkedRole",
            "Effect": "Allow",
            "Action": "iam:CreateServiceLinkedRole",
            "Resource": "*",
            "Condition": {
                "StringLike": {
                    "iam:AWSServiceName": [
                        "rds.amazonaws.com",
                        "ec2.amazonaws.com",
                        "elasticloadbalancing.amazonaws.com",
                        "autoscaling.amazonaws.com",
                        "replication.dynamodb.amazonaws.com"
                    ]
                }
            }
        },
        {
            "Sid": "IAMPassRoleToEC2",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": "ec2.amazonaws.com"
                }
            }
        },
        {
            "Sid": "ELBASGPermissions",
            "Effect": "Allow",
            "Action": [
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DeleteLoadBalancer",
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DeleteAutoScalingGroup"
            ],
            "Resource": "*"
        },
        {
            "Sid": "STSPermissions",
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CostExplorerPermissions",
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetDimensionValues",
                "ce:GetTags"
            ],
            "Resource": "*"
        }
    ]
}


class CredentialValidationWorker(QThread):
    """Background worker to validate AWS credentials."""
    
    validation_complete = Signal(bool, str, str)  # success, title, message
    
    def __init__(self, access_key: str, secret_key: str, parent=None):
        super().__init__(parent)
        self.access_key = access_key
        self.secret_key = secret_key
    
    def run(self):
        """Execute credential validation."""
        from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
        
        errors = []
        identity_info = ""
        
        try:
            session = get_session(
                access_key=self.access_key,
                secret_key=self.secret_key,
            )
            
            # Test 1: STS GetCallerIdentity
            try:
                sts = session.client('sts')
                identity = sts.get_caller_identity()
                identity_info = f"Account: {identity['Account']}\nUser: {identity['Arn'].split('/')[-1]}"
            except ClientError as e:
                code = e.response['Error']['Code']
                if code == 'InvalidClientTokenId':
                    self.validation_complete.emit(
                        False, "Invalid Credentials",
                        "The Access Key ID is not valid."
                    )
                    return
                elif code == 'SignatureDoesNotMatch':
                    self.validation_complete.emit(
                        False, "Invalid Credentials",
                        "The Secret Access Key is not valid."
                    )
                    return
                else:
                    errors.append(f"STS: {e.response['Error']['Message']}")
            
            # Test 2: S3 ListBuckets
            try:
                s3 = session.client('s3')
                s3.list_buckets()
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    errors.append("s3:ListAllMyBuckets")
            
            # Test 3: EC2 DescribeInstances (regional service - use us-east-1)
            try:
                ec2 = session.client('ec2', region_name='us-east-1')
                ec2.describe_instances(MaxResults=5)
            except ClientError as e:
                if e.response['Error']['Code'] == 'UnauthorizedOperation':
                    errors.append("ec2:DescribeInstances")
            
            if errors:
                self.validation_complete.emit(
                    False, "Insufficient Permissions",
                    f"Missing permissions:\n• " + "\n• ".join(errors) +
                    "\n\nPlease update your IAM policy."
                )
            else:
                self.validation_complete.emit(
                    True, "Authentication Successful",
                    f"Welcome!\n\n{identity_info}"
                )
                
        except NoCredentialsError:
            self.validation_complete.emit(
                False, "No Credentials",
                "Please enter both Access Key ID and Secret Access Key."
            )
        except EndpointConnectionError:
            self.validation_complete.emit(
                False, "Connection Error",
                "Unable to connect to AWS. Check your internet connection."
            )
        except Exception as e:
            self.validation_complete.emit(
                False, "Error",
                f"Unexpected error: {str(e)}"
            )


class AWSLoginDialog(QDialog):
    """
    Login dialog that gates access to the application.
    
    Must be shown before the main window. Only accepts/closes
    when credentials are validated successfully.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._validation_worker: Optional[CredentialValidationWorker] = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        self.setWindowTitle("Pockitect - AWS Authentication")
        self.setFixedSize(600, 700)
        self.setModal(True)
        
        # Remove close button, force authentication
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.CustomizeWindowHint
        )
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("🔐 AWS Authentication Required")
        header.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #cdd6f4;
            padding-bottom: 8px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        subtitle = QLabel(
            "Enter your AWS credentials to access Pockitect.\n"
            "Credentials are stored securely in your system keyring."
        )
        subtitle.setStyleSheet("color: #a6adc8; font-size: 12px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #45475a;")
        layout.addWidget(sep)
        
        # Policy section
        policy_group = QGroupBox("Required IAM Policy")
        policy_layout = QVBoxLayout(policy_group)
        
        policy_info = QLabel(
            "Create an IAM user with programmatic access and attach this policy:"
        )
        policy_info.setStyleSheet("color: #a6adc8; font-size: 11px;")
        policy_info.setWordWrap(True)
        policy_layout.addWidget(policy_info)
        
        self.policy_text = QTextEdit()
        self.policy_text.setReadOnly(True)
        self.policy_text.setFont(QFont("Consolas, Monaco, monospace", 9))
        self.policy_text.setPlainText(json.dumps(REQUIRED_IAM_POLICY, indent=2))
        self.policy_text.setMaximumHeight(160)
        self.policy_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #a6e3a1;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        policy_layout.addWidget(self.policy_text)
        
        self.copy_btn = QPushButton("📋 Copy Policy to Clipboard")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        policy_layout.addWidget(self.copy_btn)
        
        layout.addWidget(policy_group)
        
        # Credentials section
        creds_group = QGroupBox("AWS Credentials")
        creds_layout = QFormLayout(creds_group)
        creds_layout.setSpacing(12)
        
        self.access_key_edit = QLineEdit()
        self.access_key_edit.setPlaceholderText("AKIAIOSFODNN7EXAMPLE")
        self.access_key_edit.setMinimumHeight(38)
        creds_layout.addRow("Access Key ID:", self.access_key_edit)
        
        secret_widget = QHBoxLayout()
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setPlaceholderText("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        self.secret_key_edit.setMinimumHeight(38)
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        secret_widget.addWidget(self.secret_key_edit)
        
        self.show_secret_check = QCheckBox("Show")
        self.show_secret_check.setCursor(Qt.CursorShape.PointingHandCursor)
        secret_widget.addWidget(self.show_secret_check)
        
        creds_layout.addRow("Secret Access Key:", secret_widget)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(20)
        creds_layout.addRow("", self.status_label)
        
        layout.addWidget(creds_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.quit_btn = QPushButton("Quit")
        self.quit_btn.setMinimumHeight(40)
        self.quit_btn.setMinimumWidth(100)
        button_layout.addWidget(self.quit_btn)
        
        button_layout.addStretch()
        
        self.login_btn = QPushButton("🔐 Login")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.setMinimumWidth(150)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:pressed {
                background-color: #74c7ec;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #6c7086;
            }
        """)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(self.login_btn)
        
        layout.addLayout(button_layout)
        
        # Keyring warning
        if not KEYRING_AVAILABLE:
            warning = QLabel(
                "⚠️ 'keyring' library not installed. Credentials won't persist."
            )
            warning.setStyleSheet("color: #fab387; font-size: 11px;")
            layout.addWidget(warning)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.copy_btn.clicked.connect(self._copy_policy)
        self.show_secret_check.toggled.connect(self._toggle_secret)
        self.login_btn.clicked.connect(self._validate_credentials)
        self.quit_btn.clicked.connect(self._quit_app)
        
        # Enter key triggers login
        self.access_key_edit.returnPressed.connect(self._validate_credentials)
        self.secret_key_edit.returnPressed.connect(self._validate_credentials)
    
    def try_auto_login(self) -> bool:
        """
        Try to auto-login with stored credentials.
        
        Returns:
            True if auto-login succeeded, False otherwise
        """
        if not KEYRING_AVAILABLE:
            return False
        
        try:
            access_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ACCESS_KEY)
            secret_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_SECRET_KEY)
            
            if access_key and secret_key:
                self.access_key_edit.setText(access_key)
                self.secret_key_edit.setText(secret_key)
                self._set_status("Validating stored credentials...", "info")
                
                # Validate synchronously for auto-login
                from botocore.exceptions import ClientError
                
                try:
                    session = get_session(
                        access_key=access_key,
                        secret_key=secret_key,
                    )
                    sts = session.client('sts')
                    sts.get_caller_identity()
                    
                    # Quick permission check
                    s3 = session.client('s3')
                    s3.list_buckets()
                    
                    return True  # Auto-login successful
                except ClientError:
                    self._set_status("Stored credentials invalid. Please re-enter.", "error")
                    return False
        except Exception:
            pass
        
        return False
    
    def _copy_policy(self):
        """Copy IAM policy to clipboard."""
        policy_json = json.dumps(REQUIRED_IAM_POLICY, indent=2)
        
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(policy_json)
            self._show_copy_feedback()
            return
        
        if PYPERCLIP_AVAILABLE:
            try:
                pyperclip.copy(policy_json)
                self._show_copy_feedback()
                return
            except Exception:
                pass
        
        QMessageBox.information(
            self, "Copy Policy",
            "Please select and copy the policy text manually."
        )
    
    def _show_copy_feedback(self):
        """Show copy success feedback."""
        original = self.copy_btn.text()
        self.copy_btn.setText("✓ Copied!")
        self.copy_btn.setEnabled(False)
        QTimer.singleShot(2000, lambda: self._reset_copy_btn(original))
    
    def _reset_copy_btn(self, text: str):
        """Reset copy button."""
        self.copy_btn.setText(text)
        self.copy_btn.setEnabled(True)
    
    def _toggle_secret(self, checked: bool):
        """Toggle secret key visibility."""
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.secret_key_edit.setEchoMode(mode)
    
    def _validate_credentials(self):
        """Validate entered credentials."""
        access_key = self.access_key_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not access_key or not secret_key:
            self._set_status("Please enter both credentials.", "error")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Validating...")
        self._set_status("Connecting to AWS...", "info")
        
        self._validation_worker = CredentialValidationWorker(
            access_key, secret_key, self
        )
        self._validation_worker.validation_complete.connect(self._on_validation_complete)
        self._validation_worker.start()
    
    def _on_validation_complete(self, success: bool, title: str, message: str):
        """Handle validation result."""
        self.login_btn.setEnabled(True)
        self.login_btn.setText("🔐 Login")
        
        if success:
            # Save to keyring
            if KEYRING_AVAILABLE:
                try:
                    keyring.set_password(
                        KEYRING_SERVICE,
                        KEYRING_USER_ACCESS_KEY,
                        self.access_key_edit.text().strip()
                    )
                    keyring.set_password(
                        KEYRING_SERVICE,
                        KEYRING_USER_SECRET_KEY,
                        self.secret_key_edit.text().strip()
                    )
                except Exception as e:
                    QMessageBox.warning(
                        self, "Keyring Error",
                        f"Could not save credentials: {e}"
                    )
            
            self._set_status("✓ " + title, "success")
            QMessageBox.information(self, title, message)
            self.accept()  # Close dialog with success
        else:
            self._set_status("✗ " + title, "error")
            QMessageBox.warning(self, title, message)
    
    def _set_status(self, message: str, status_type: str):
        """Update status label."""
        colors = {
            "info": "#89b4fa",
            "success": "#a6e3a1",
            "error": "#f38ba8",
        }
        color = colors.get(status_type, "#cdd6f4")
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)
    
    def _quit_app(self):
        """Quit the application."""
        reply = QMessageBox.question(
            self,
            "Quit Pockitect",
            "AWS credentials are required to use Pockitect.\n\nAre you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.reject()  # Close dialog with failure
    
    def closeEvent(self, event):
        """Prevent closing without authentication."""
        # Only allow close via accept() or reject()
        event.ignore()


def get_aws_credentials() -> tuple[str, str]:
    """
    Get AWS credentials from keyring.
    
    Returns:
        Tuple of (access_key_id, secret_access_key)
    """
    if not KEYRING_AVAILABLE:
        return ("", "")
    
    try:
        access_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ACCESS_KEY) or ""
        secret_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_SECRET_KEY) or ""
        return (access_key, secret_key)
    except Exception:
        return ("", "")


def clear_aws_credentials():
    """Clear stored AWS credentials from keyring."""
    if not KEYRING_AVAILABLE:
        return
    
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER_ACCESS_KEY)
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER_SECRET_KEY)
    except Exception:
        pass
