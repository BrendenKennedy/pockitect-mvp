"""
Command Executor - Executes project control commands via Redis.
"""

import logging
import uuid
import tempfile
import yaml
from typing import Optional, Dict, Any, Callable

from app.core.redis_client import RedisClient
from storage import load_project
from deploy_worker import ProjectDeployWorker
from workers import PowerWorker, DeleteWorker
from monitor_service import ResourceMonitoringService

logger = logging.getLogger(__name__)


class CommandExecutor:
    """
    Executes commands by publishing to Redis command channel.
    Handles deploy, power, terminate, and scan commands.
    """
    
    def __init__(self):
        self.redis = RedisClient()
    
    def deploy_project(self, project_name: str, on_progress: Optional[Callable] = None, 
                       on_finished: Optional[Callable] = None) -> ProjectDeployWorker:
        """
        Deploy a project.
        
        Args:
            project_name: Name of the project to deploy
            on_progress: Optional callback for progress updates (message, step, total)
            on_finished: Optional callback for completion (success: bool, message: str)
            
        Returns:
            ProjectDeployWorker instance (already started)
        """
        from storage import get_project_path, slugify
        
        slug = slugify(project_name)
        blueprint = load_project(slug)
        
        if not blueprint:
            raise ValueError(f"Project '{project_name}' not found")
        
        worker = ProjectDeployWorker(blueprint, parent=None)
        
        if on_progress:
            worker.progress.connect(on_progress)
        if on_finished:
            worker.finished.connect(on_finished)
        
        worker.start()
        return worker
    
    def power_project(self, project_name: str, action: str, monitor_resources=None,
                     on_finished: Optional[Callable] = None) -> PowerWorker:
        """
        Start or stop a project's resources.
        
        Args:
            project_name: Name of the project
            action: "start" or "stop"
            monitor_resources: Optional list of ScannedResource objects
            on_finished: Optional callback (success: bool, message: str)
            
        Returns:
            PowerWorker instance (already started)
        """
        if action not in ("start", "stop"):
            raise ValueError(f"Invalid power action: {action}")
        
        worker = PowerWorker(project_name, action, parent=None, monitor_resources=monitor_resources)
        
        if on_finished:
            worker.finished.connect(on_finished)
        
        worker.start()
        return worker
    
    def terminate_project(self, project_name: str, monitor_resources=None,
                         on_progress: Optional[Callable] = None,
                         on_finished: Optional[Callable] = None) -> DeleteWorker:
        """
        Terminate all resources for a project.
        
        Args:
            project_name: Name of the project
            monitor_resources: Optional list of ScannedResource objects
            on_progress: Optional callback for progress (message: str)
            on_finished: Optional callback (success_ids: list, errors: list)
            
        Returns:
            DeleteWorker instance (already started)
        """
        from app.core.aws.resource_tracker import ResourceTracker
        
        # Get resources for the project
        if monitor_resources:
            resources = [r for r in monitor_resources 
                        if r.tags.get('pockitect:project') == project_name]
        else:
            tracker = ResourceTracker()
            all_resources = []
            for res_type in ["ec2_instance", "rds_instance", "s3_bucket", "security_group"]:
                res_list = tracker.get_active_resources(project=project_name, resource_type=res_type)
                all_resources.extend(res_list)
            
            # Convert to ScannedResource-like format
            from app.core.aws.scanner import ScannedResource
            resources = [
                ScannedResource(
                    id=r.resource_id,
                    type=r.resource_type,
                    region=r.region,
                    name="",
                    state="",
                    tags={"pockitect:project": project_name},
                    details={}
                )
                for r in all_resources
            ]
        
        if not resources:
            raise ValueError(f"No resources found for project '{project_name}'")
        
        worker = DeleteWorker(resources, parent=None, project_name=project_name)
        
        if on_progress:
            worker.progress.connect(on_progress)
        if on_finished:
            worker.finished.connect(on_finished)
        
        worker.start()
        return worker
    
    def scan_regions(self, regions: Optional[list[str]] = None, 
                    monitor_service: Optional[ResourceMonitoringService] = None):
        """
        Trigger a scan of AWS regions.
        
        Args:
            regions: List of regions to scan, or None for all regions
            monitor_service: Optional ResourceMonitoringService to use
        """
        if monitor_service:
            monitor_service.request_scan(regions=regions)
        else:
            # Fallback: publish command directly
            request_id = uuid.uuid4().hex
            self.redis.publish_command(
                "scan_all_regions",
                {"regions": regions} if regions else {},
                request_id=request_id
            )
