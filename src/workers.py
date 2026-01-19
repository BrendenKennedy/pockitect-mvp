import logging
import uuid
from typing import List

from PySide6.QtCore import Signal

from app.core.aws.scanner import ScannedResource
from app.core.aws.resource_tracker import ResourceTracker
from app.core.base_worker import BaseCommandWorker

logger = logging.getLogger(__name__)

class PowerWorker(BaseCommandWorker):
    """
    Shared background worker for start/stop actions.
    Uses sorting and grouping for efficient execution.
    """
    finished = Signal(bool, str)

    def __init__(self, project_name: str, action: str, parent=None, monitor_resources=None):
        super().__init__(parent)
        self.project_name = project_name
        self.action = action
        self.monitor_resources = monitor_resources

    def run(self):
        try:
            logger.info(f"Power worker started: {self.action} on {self.project_name}")
            ec2_resource_ids = []
            rds_resource_ids = []
            
            # Logic to find resources
            if self.monitor_resources:
                for res in self.monitor_resources:
                    if hasattr(res, 'tags') and res.tags.get('pockitect:project') == self.project_name:
                        if res.type == 'ec2_instance':
                            ec2_resource_ids.append((res.id, res.region))
                        elif res.type == 'rds_instance':
                            rds_resource_ids.append((res.id, res.region))
                    elif res.name and res.name.startswith(self.project_name):
                        if res.type == 'ec2_instance':
                            ec2_resource_ids.append((res.id, res.region))
                        elif res.type == 'rds_instance':
                            rds_resource_ids.append((res.id, res.region))
            else:
                tracker = ResourceTracker()
                ec2_res = tracker.get_active_resources(project=self.project_name, resource_type="ec2_instance")
                rds_res = tracker.get_active_resources(project=self.project_name, resource_type="rds_instance")
                ec2_resource_ids = [(r.resource_id, r.region) for r in ec2_res]
                rds_resource_ids = [(r.resource_id, r.region) for r in rds_res]
            
            if not ec2_resource_ids and not rds_resource_ids:
                logger.info("No resources found to control.")
                self.finished.emit(True, "No resources found to control.")
                return

            request_id = uuid.uuid4().hex
            payload = []
            for instance_id, region in ec2_resource_ids:
                payload.append({"id": instance_id, "type": "ec2_instance", "region": region})
            for db_id, region in rds_resource_ids:
                payload.append({"id": db_id, "type": "rds_instance", "region": region})

            self.redis.publish_status(
                "power_requested",
                data={"action": self.action, "project": self.project_name, "resources": payload},
                request_id=request_id,
                status="queued",
            )
            self.redis.publish_command(
                "power",
                {"action": self.action, "project": self.project_name, "resources": payload},
                request_id=request_id,
            )

            for data in self.iter_status_events(
                request_id, {"power", "power_confirmed", "power_confirm_error"}
            ):
                event_type = data.get("type")
                if event_type == "power":
                    status = data.get("status")
                    if status == "error":
                        error = data.get("data", {}).get("error", "Power action failed.")
                        self.finished.emit(False, error)
                        break
                    if status == "success":
                        continue
                if event_type == "power_confirmed":
                    message = data.get("data", {}).get("message", "Power action confirmed.")
                    self.finished.emit(True, message)
                    break
                if event_type == "power_confirm_error":
                    error = data.get("data", {}).get("error", "Power confirmation failed.")
                    self.finished.emit(False, error)
                    break
            
        except Exception as e:
            logger.error(f"Power worker failed: {e}")
            self.finished.emit(False, str(e))

class DeleteWorker(BaseCommandWorker):
    """
    Background worker for deleting resources with dependency handling.
    Publishes delete intent and waits for status updates.
    """
    progress = Signal(str)
    finished = Signal(list, list) # success_ids, errors

    def __init__(self, resources: List[ScannedResource], parent=None, project_name: str = None):
        super().__init__(parent)
        self.resources = resources
        self.project_name = project_name

    def run(self):
        try:
            request_id = uuid.uuid4().hex
            payload = [
                {
                    "id": r.id,
                    "type": r.type,
                    "region": r.region,
                    "tags": r.tags,
                    "details": r.details,
                }
                for r in self.resources
            ]

            self.redis.publish_status(
                "terminate_requested",
                data={"resources": payload, "project": self.project_name},
                request_id=request_id,
                status="queued",
            )
            self.redis.publish_command(
                "terminate",
                {"resources": payload, "project": self.project_name},
                request_id=request_id,
            )

            success_ids: List[str] = []
            errors: List[str] = []
            confirmed_ids: List[str] = []
            shared_ids: List[str] = []
            for data in self.iter_status_events(
                request_id,
                {
                    "terminate_progress",
                    "terminate_error",
                    "terminate_confirmed",
                    "terminate_confirm_error",
                },
            ):
                event_type = data.get("type")
                if event_type == "terminate_progress":
                    res_id = data.get("data", {}).get("resource_id")
                    if res_id:
                        success_ids.append(res_id)
                elif event_type == "terminate_error":
                    res_id = data.get("data", {}).get("resource_id")
                    error = data.get("data", {}).get("error", "Unknown error")
                    errors.append(f"{res_id}: {error}")
                elif event_type == "terminate_confirmed":
                    payload = data.get("data", {}) or {}
                    confirmed_ids = payload.get("confirmed_ids") or []
                    shared_ids = payload.get("shared_ids") or []
                    self.finished.emit(confirmed_ids + shared_ids, errors)
                    break
                elif event_type == "terminate_confirm_error":
                    payload = data.get("data", {}) or {}
                    confirmed_ids = payload.get("confirmed_ids") or []
                    shared_ids = payload.get("shared_ids") or []
                    failed_ids = payload.get("failed_ids") or []
                    confirm_errors = payload.get("errors") or []
                    for res_id in failed_ids:
                        if res_id not in [e.split(":", 1)[0] for e in errors]:
                            errors.append(f"{res_id}: confirmation failed")
                    errors.extend([str(err) for err in confirm_errors])
                    self.finished.emit(confirmed_ids + shared_ids, errors)
                    break

            if self.isInterruptionRequested():
                self.finished.emit(success_ids, errors)

        except Exception as e:
            logger.exception("DeleteWorker failed")
            self.finished.emit([], [str(e)])
