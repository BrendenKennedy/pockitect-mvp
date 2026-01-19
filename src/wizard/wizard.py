"""
Main wizard class that orchestrates all wizard pages.
"""

from datetime import datetime
from PySide6.QtWidgets import QWizard, QMessageBox
from PySide6.QtCore import Signal

from .pages import (
    ProjectBasicsPage,
    ComputePage,
    NetworkPage,
    DataPage,
    SecurityPage,
    ReviewPage,
)
from .deploy_dialog import DeploymentDialog


class InfrastructureWizard(QWizard):
    """
    Main wizard for creating AWS infrastructure blueprints.
    
    Signals:
        blueprint_created: Emitted when a blueprint is finalized
        deploy_requested: Emitted when user clicks deploy
    """
    
    blueprint_created = Signal(dict)
    deploy_requested = Signal(dict)
    
    # Page IDs
    PAGE_PROJECT = 0
    PAGE_COMPUTE = 1
    PAGE_NETWORK = 2
    PAGE_DATA = 3
    PAGE_SECURITY = 4
    PAGE_REVIEW = 5
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Pockitect - New Infrastructure Project")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(800, 600)
        
        # Set up options
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.setOption(QWizard.WizardOption.HaveCustomButton2, True)
        self.setButtonText(QWizard.WizardButton.CustomButton1, "Save Draft")
        self.setButtonText(QWizard.WizardButton.CustomButton2, "🚀 Deploy Now")
        
        # Create pages
        self._create_pages()
        
        # Connect signals
        self.currentIdChanged.connect(self._on_page_changed)
        self.customButtonClicked.connect(self._on_custom_button)
        self.finished.connect(self._on_finished)
        
        # Track deployment state
        self._deployed = False
    
    def _create_pages(self):
        """Create and add all wizard pages."""
        self.project_page = ProjectBasicsPage(self)
        self.compute_page = ComputePage(self)
        self.network_page = NetworkPage(self)
        self.data_page = DataPage(self)
        self.security_page = SecurityPage(self)
        self.review_page = ReviewPage(self)
        
        self.setPage(self.PAGE_PROJECT, self.project_page)
        self.setPage(self.PAGE_COMPUTE, self.compute_page)
        self.setPage(self.PAGE_NETWORK, self.network_page)
        self.setPage(self.PAGE_DATA, self.data_page)
        self.setPage(self.PAGE_SECURITY, self.security_page)
        self.setPage(self.PAGE_REVIEW, self.review_page)
    
    def _on_page_changed(self, page_id: int):
        """Handle page changes to update dependent fields."""
        if page_id == self.PAGE_DATA:
            # Update S3 region suffix based on selected region
            project_data = self.project_page.get_data()
            self.data_page.update_region(project_data.get("region", "us-east-1"))
        
        elif page_id == self.PAGE_SECURITY:
            # Update security page with project name and data selections
            project_data = self.project_page.get_data()
            self.security_page.update_project_name(project_data.get("name", ""))
            
            data_data = self.data_page.get_data()
            self.security_page.update_from_data_page(
                s3_enabled=data_data.get("s3_bucket", {}).get("enabled", False),
                rds_enabled=data_data.get("db", {}).get("enabled", False)
            )
        
        elif page_id == self.PAGE_REVIEW:
            # Update review page with complete blueprint
            blueprint = self._build_blueprint()
            self.review_page.update_summary(blueprint)
            # Show deploy button only on review page
            self.button(QWizard.WizardButton.CustomButton2).setVisible(True)
        else:
            # Hide deploy button on other pages
            self.button(QWizard.WizardButton.CustomButton2).setVisible(False)
    
    def _on_custom_button(self, button: int):
        """Handle custom button clicks (Save Draft, Deploy)."""
        if button == QWizard.WizardButton.CustomButton1:
            self._save_draft()
        elif button == QWizard.WizardButton.CustomButton2:
            self._start_deployment()
    
    def _on_finished(self, result: int):
        """Handle wizard completion."""
        if result == QWizard.DialogCode.Accepted:
            blueprint = self._build_blueprint()
            self.blueprint_created.emit(blueprint)
    
    def _save_draft(self):
        """Save current state as a draft."""
        from storage import save_project
        
        blueprint = self._build_blueprint()
        
        # Mark as draft
        blueprint["project"]["status"] = "draft"
        
        try:
            path = save_project(blueprint)
            QMessageBox.information(
                self,
                "Draft Saved",
                f"Draft saved to:\n{path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Failed to save draft:\n{e}"
            )
    
    def _start_deployment(self):
        """Start the deployment process."""
        blueprint = self._build_blueprint()
        
        # Get database password if needed
        db_password = None
        if blueprint.get("data", {}).get("db", {}).get("status") != "skipped":
            db_password = self.data_page.get_db_password()
            if not db_password:
                QMessageBox.warning(
                    self,
                    "Missing Password",
                    "Please go back to the Data page and enter the database password."
                )
                return
        
        # Confirm deployment
        reply = QMessageBox.question(
            self,
            "Confirm Deployment",
            "Are you ready to deploy this infrastructure to AWS?\n\n"
            "This will create real AWS resources that may incur charges.\n"
            "Make sure you have reviewed all settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Show deployment dialog
        dialog = DeploymentDialog(blueprint, db_password=db_password, parent=self)
        dialog.deployment_finished.connect(self._on_deployment_finished)
        dialog.start_deployment()
        dialog.exec()
    
    def _on_deployment_finished(self, success: bool, updated_blueprint: dict):
        """Handle deployment completion."""
        if success:
            self._deployed = True
            # Save the updated blueprint
            from storage import save_project
            try:
                save_project(updated_blueprint)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Save Error",
                    f"Deployment succeeded but failed to save blueprint:\n{e}"
                )
            
            # Emit signal with updated blueprint
            self.deploy_requested.emit(updated_blueprint)
    
    def _build_blueprint(self) -> dict:
        """
        Build the complete blueprint from all page data.
        
        Returns:
            Complete project blueprint dictionary
        """
        project_data = self.project_page.get_data()
        compute_data = self.compute_page.get_data()
        network_data = self.network_page.get_data()
        data_data = self.data_page.get_data()
        security_data = self.security_page.get_data()
        
        # Build the canonical blueprint structure
        blueprint = {
            "project": {
                "name": project_data.get("name", ""),
                "description": project_data.get("description", ""),
                "region": project_data.get("region", "us-east-1"),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "owner": project_data.get("owner", ""),
                "cost": project_data.get("cost"),
            },
            "network": {
                "vpc_id": None,
                "subnet_id": None,
                "security_group_id": None,
                "vpc_env": network_data.get("vpc_env", "dev"),
                "subnet_type": network_data.get("subnet_type", "public"),
                "rules": network_data.get("rules", []),
                "status": "pending",
            },
            "compute": {
                "instance_type": compute_data.get("instance_type", "t3.micro"),
                "image_id": compute_data.get("image_id"),
                "image_name": compute_data.get("image_name"),
                "user_data": compute_data.get("user_data", ""),
                "instance_id": None,
                "status": "pending",
            },
            "data": {
                "db": {
                    "engine": data_data.get("db", {}).get("engine"),
                    "instance_class": data_data.get("db", {}).get("instance_class"),
                    "allocated_storage_gb": data_data.get("db", {}).get("allocated_storage_gb"),
                    "username": data_data.get("db", {}).get("username"),
                    "password": None,  # Never stored
                    "endpoint": None,
                    "status": "pending" if data_data.get("db", {}).get("enabled") else "skipped",
                },
                "s3_bucket": {
                    "name": data_data.get("s3_bucket", {}).get("name"),
                    "arn": None,
                    "status": "pending" if data_data.get("s3_bucket", {}).get("enabled") else "skipped",
                },
            },
            "security": {
                "key_pair": {
                    "name": security_data.get("key_pair", {}).get("name"),
                    "mode": security_data.get("key_pair", {}).get("mode", "generate"),
                    "key_pair_id": None,
                    "private_key_pem": None,
                    "status": "pending" if security_data.get("key_pair", {}).get("mode") != "none" else "skipped",
                },
                "certificate": {
                    "domain": security_data.get("certificate", {}).get("domain"),
                    "mode": security_data.get("certificate", {}).get("mode", "skip"),
                    "cert_arn": None,
                    "status": "pending" if security_data.get("certificate", {}).get("mode") != "skip" else "skipped",
                },
                "iam_role": {
                    "role_name": security_data.get("iam_role", {}).get("role_name"),
                    "policy_document": {},
                    "arn": None,
                    "instance_profile_arn": None,
                    "status": "pending" if security_data.get("iam_role", {}).get("enabled") else "skipped",
                },
            },
        }
        
        return blueprint
    
    def load_draft(self, blueprint: dict):
        """
        Load a draft blueprint into the wizard.
        
        Args:
            blueprint: A previously saved blueprint dictionary
        """
        # Load project data
        if "project" in blueprint:
            self.project_page.set_data(blueprint["project"])
        
        # Load compute data
        if "compute" in blueprint:
            self.compute_page.set_data(blueprint["compute"])
        
        # Load network data
        if "network" in blueprint:
            self.network_page.set_data(blueprint["network"])
        
        # Load data page
        if "data" in blueprint:
            data = blueprint["data"]
            # Convert to the page's expected format
            page_data = {
                "db": {
                    "enabled": data.get("db", {}).get("status") != "skipped",
                    **data.get("db", {}),
                },
                "s3_bucket": {
                    "enabled": data.get("s3_bucket", {}).get("status") != "skipped",
                    **data.get("s3_bucket", {}),
                },
            }
            self.data_page.set_data(page_data)
        
        # Load security data
        if "security" in blueprint:
            self.security_page.set_data(blueprint["security"])
