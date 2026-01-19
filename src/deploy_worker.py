import logging
import os
import uuid
from typing import Optional

from PySide6.QtCore import Signal

from app.core.base_worker import BaseCommandWorker

logger = logging.getLogger(__name__)


class ProjectDeployWorker(BaseCommandWorker):
    """Background worker to deploy a project using Redis command events."""

    progress = Signal(str, int, int)  # message, step, total
    finished = Signal(bool, str)

    def __init__(self, blueprint: dict, db_password: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.blueprint = blueprint
        self.db_password = db_password
        self.request_id = uuid.uuid4().hex

    def run(self):
        try:
            logger.info(
                "Starting deployment for project: %s",
                self.blueprint.get("project", {}).get("name"),
            )
            import tempfile
            import yaml

            deploy_payload = self._map_blueprint_to_deployer_format(self.blueprint)
            expected_types = self._get_expected_resource_types(deploy_payload)
            project_name = self.blueprint.get("project", {}).get("name")
            region = self.blueprint.get("project", {}).get("region")
            logger.debug("Generated deployment payload: %s", deploy_payload)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                yaml.dump(deploy_payload, tmp)
                tmp_path = tmp.name

            self.redis.publish_status(
                "deploy_requested",
                {
                    "project": project_name,
                    "region": region,
                    "expected_resource_types": expected_types,
                },
                request_id=self.request_id,
                status="queued",
            )
            self.redis.publish_command(
                "deploy",
                {
                    "template_path": tmp_path,
                    "project": project_name,
                    "region": region,
                    "expected_resource_types": expected_types,
                },
                request_id=self.request_id,
            )
            self.progress.emit("Deployment command queued...", -1, -1)

            for data in self.iter_status_events(
                self.request_id, {"deploy", "deploy_confirmed", "deploy_confirm_error"}
            ):
                payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
                logger.debug("Received deployment update: %s", data)

                if data.get("type") == "deploy":
                    status = data.get("status")
                    if status == "in_progress":
                        step = payload.get("step", data.get("step"))
                        total = payload.get("total", data.get("total"))
                        step_value = int(step) if isinstance(step, int) else -1
                        total_value = int(total) if isinstance(total, int) else -1
                        self.progress.emit(
                            f"Deploying: {payload.get('message', data.get('message'))}",
                            step_value,
                            total_value,
                        )
                    elif status == "success":
                        continue
                    elif status == "error":
                        error = payload.get("error", data.get("error"))
                        self.finished.emit(False, f"Deployment failed: {error}")
                        logger.error("Deployment failed: %s", error)
                        break
                elif data.get("type") == "deploy_confirmed":
                    self.finished.emit(True, payload.get("message", "Deployment confirmed!"))
                    logger.info("Deployment confirmed successfully.")
                    break
                elif data.get("type") == "deploy_confirm_error":
                    error = payload.get("error", "Deployment confirmation failed.")
                    self.finished.emit(False, f"Deployment confirmation failed: {error}")
                    logger.error("Deployment confirmation failed: %s", error)
                    break

            if self.isInterruptionRequested():
                logger.warning("Deployment cancelled by user.")
            os.unlink(tmp_path)

        except Exception as e:
            logger.exception("Unexpected error in ProjectDeployWorker")
            self.finished.emit(False, str(e))

    def _map_blueprint_to_deployer_format(self, blueprint: dict) -> dict:
        """Map the wizard's JSON structure to the YAML format expected by the new deployer."""
        output = {"project": blueprint.get("project", {}), "resources": {}}
        resources = output["resources"]

        net = blueprint.get("network", {})
        vpc_id = net.get("vpc_id")
        if not vpc_id:
            from app.core.aws.managed_vpc_service import ManagedVpcService

            mapping = ManagedVpcService().load_mapping()
            region = (blueprint.get("project") or {}).get("region")
            env = net.get("vpc_env") or "dev"
            vpc_id = (mapping.get(region) or {}).get(env)
            if not vpc_id:
                raise ValueError(f"Managed VPC not configured for {region}:{env}")

        from app.core.aws.managed_vpc_service import ManagedVpcService
        region = (blueprint.get("project") or {}).get("region")
        managed_service = ManagedVpcService()
        vpc_cidr = managed_service.get_vpc_cidr(region, vpc_id) if region else None
        subnet_cidr = (
            managed_service.pick_available_subnet_cidr(region, vpc_id, vpc_cidr)
            if (region and vpc_cidr)
            else None
        )
        if not subnet_cidr:
            subnet_cidr = managed_service.pick_subnet_cidr(vpc_cidr) if vpc_cidr else None
        if not subnet_cidr:
            subnet_cidr = "10.0.1.0/24"

        resources["main_subnet"] = {
            "type": "subnet",
            "properties": {"cidr_block": subnet_cidr, "vpc_id": vpc_id},
        }
        project_name = (blueprint.get("project") or {}).get("name") or "project"
        sg_name = f"web_sg_{project_name}".replace(" ", "_")[:255]
        resources["web_sg"] = {
            "type": "security_group",
            "properties": {
                "description": "Generated by Pockitect",
                "name": sg_name,
                "vpc_id": vpc_id,
                "ingress": [
                    {
                        "protocol": "tcp",
                        "from_port": 80,
                        "to_port": 80,
                        "cidr": "0.0.0.0/0",
                    },
                    {
                        "protocol": "tcp",
                        "from_port": 22,
                        "to_port": 22,
                        "cidr": "0.0.0.0/0",
                    },
                ],
            },
        }

        comp = blueprint.get("compute", {})
        if comp.get("instance_type"):
            resources["app_server"] = {
                "type": "ec2_instance",
                "properties": {
                    "instance_type": comp.get("instance_type"),
                    "image_id": comp.get("image_id") or comp.get("ami_id"),
                },
            }

        data = blueprint.get("data", {})
        if data.get("s3_bucket", {}).get("name"):
            resources["app_bucket"] = {
                "type": "s3_bucket",
                "properties": {"name": data["s3_bucket"]["name"]},
            }

        return output

    def _get_expected_resource_types(self, deploy_payload: dict) -> list[str]:
        resources = deploy_payload.get("resources", {})
        types = {config.get("type") for config in resources.values() if config.get("type")}
        return sorted(types)
