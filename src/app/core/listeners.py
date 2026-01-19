import asyncio
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.core.config import CHANNEL_COMMANDS, CHANNEL_STATUS, WORKSPACE_ROOT
from app.core.redis_client import RedisClient, PubSubManager
from app.core.aws.credentials_helper import get_session
from app.core.aws.scanner import ResourceScanner, ALL_REGIONS
from app.core.aws.deployer import ResourceDeployer
from app.core.aws.deleter import ResourceDeleter
from app.core.aws.recursive_deleter import ChildFinder, ResourceNode
from app.core.aws.resource_tracker import ResourceTracker
from app.core.task_manager import get_executor

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@dataclass(frozen=True)
class GraphNode:
    resource_id: str
    resource_type: str
    region: str


class CommandListener:
    def __init__(self):
        self.redis = RedisClient()
        self.executor = get_executor()
        self.pubsub_manager: Optional[PubSubManager] = None
        self._cache_dir = WORKSPACE_ROOT / "data" / "cache"
        self._scan_inflight: Set[str] = set()

    def start(self):
        if self.pubsub_manager:
            return
        self.pubsub_manager = PubSubManager([CHANNEL_COMMANDS], self._handle_message)
        self.pubsub_manager.start()
        logger.info("CommandListener started.")

    def stop(self):
        if self.pubsub_manager:
            self.pubsub_manager.stop()
            self.pubsub_manager = None

    def _handle_message(self, channel: str, data: Any):
        if channel != CHANNEL_COMMANDS:
            return
        if not isinstance(data, dict):
            logger.warning("Ignoring non-dict command payload: %s", data)
            return
        self.executor.submit(self._dispatch, data)

    def _dispatch(self, payload: Dict[str, Any]):
        event_type = payload.get("type")
        request_id = payload.get("request_id")
        data = payload.get("data") or {}
        try:
            if event_type == "scan_all_regions":
                self._handle_scan_all(data, request_id)
            elif event_type == "terminate":
                self._handle_terminate(data, request_id)
            elif event_type == "deploy":
                self._handle_deploy(data, request_id)
            elif event_type == "power":
                self._handle_power(data, request_id)
            elif event_type == "project_updated":
                self._handle_project_refresh(data, request_id)
            else:
                logger.warning("Unknown command type: %s", event_type)
        except Exception as exc:
            logger.exception("Command handler failed: %s", event_type)
            self.redis.publish_status(
                "error",
                data={"message": str(exc), "command": event_type},
                request_id=request_id,
                status="error",
            )

    def _handle_scan_all(self, data: Dict[str, Any], request_id: Optional[str]):
        regions = data.get("regions")
        if regions is None or (isinstance(regions, list) and len(regions) == 0):
            regions = ALL_REGIONS
        scanner = ResourceScanner()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            for file_path in self._cache_dir.glob("*.json"):
                try:
                    file_path.unlink()
                except Exception:
                    pass

            global_resources = scanner._scan_global_sync()
            global_path = self._cache_dir / "global.json"
            with open(global_path, "w", encoding="utf-8") as f:
                json.dump(global_resources, f, indent=2)
            self.redis.publish_status(
                "scan_chunk",
                data={"region": "global", "file": str(global_path), "count": len(global_resources)},
                request_id=request_id,
                status="in_progress",
            )

            prioritized = data.get("priority_regions") or []
            remaining = [r for r in regions if r not in prioritized]
            ordered_regions = list(prioritized) + remaining

            futures = []
            for region in ordered_regions:
                if region in self._scan_inflight:
                    continue
                self._scan_inflight.add(region)
                futures.append(
                    self.executor.submit(
                        self._scan_region_and_publish,
                        scanner,
                        region,
                        request_id,
                    )
                )
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    logger.error("Region scan failed: %s", exc)
        except Exception as exc:
            self.redis.publish_status(
                "scan_chunk",
                data={"error": str(exc), "region": "global"},
                request_id=request_id,
                status="error",
            )
        finally:
            try:
                conn = self.redis.get_connection()
                conn.set("pockitect:ai:last_resource_scan", datetime.utcnow().isoformat() + "Z")
            except Exception:
                logger.debug("Failed to record last resource scan timestamp.")

    def _scan_region_and_publish(self, scanner: ResourceScanner, region: str, request_id: Optional[str]):
        try:
            resources = scanner._scan_region_sync(region)
            region_path = self._cache_dir / f"{region}.json"
            with open(region_path, "w", encoding="utf-8") as f:
                json.dump(resources, f, indent=2)
            self.redis.publish_status(
                "scan_chunk",
                data={"region": region, "file": str(region_path), "count": len(resources)},
                request_id=request_id,
                status="in_progress",
            )
        except Exception as exc:
            self.redis.publish_status(
                "scan_chunk",
                data={"region": region, "error": str(exc)},
                request_id=request_id,
                status="error",
            )
        finally:
            self._scan_inflight.discard(region)

    def _handle_deploy(self, data: Dict[str, Any], request_id: Optional[str]):
        template_path = data.get("template_path")
        project = data.get("project")
        region = data.get("region")
        expected_types = data.get("expected_resource_types") or []
        if not template_path:
            self.redis.publish_status(
                "deploy",
                data={
                    "error": "Missing template_path",
                    "project": project,
                    "region": region,
                    "expected_resource_types": expected_types,
                },
                request_id=request_id,
                status="error",
            )
            return

        deployer = ResourceDeployer()

        def on_progress(msg, step=None, total=None):
            self.redis.publish_status(
                "deploy",
                data={"message": msg, "step": step, "total": total},
                request_id=request_id,
                status="in_progress",
            )

        try:
            _run_async(deployer.deploy(template_path, progress_callback=on_progress))
            self.redis.publish_status(
                "deploy",
                data={
                    "message": "Deployment completed successfully.",
                    "project": project,
                    "region": region,
                    "expected_resource_types": expected_types,
                },
                request_id=request_id,
                status="success",
            )
        except Exception as exc:
            self.redis.publish_status(
                "deploy",
                data={
                    "error": str(exc),
                    "project": project,
                    "region": region,
                    "expected_resource_types": expected_types,
                },
                request_id=request_id,
                status="error",
            )

    def _handle_power(self, data: Dict[str, Any], request_id: Optional[str]):
        action = data.get("action")
        project = data.get("project")
        resources = data.get("resources") or []
        if action not in ("start", "stop"):
            self.redis.publish_status(
                "power",
                data={
                    "error": "Invalid power action",
                    "action": action,
                    "project": project,
                    "resources": resources,
                },
                request_id=request_id,
                status="error",
            )
            return

        if not resources and project:
            tracker = ResourceTracker()
            resources = tracker.get_active_resources(project=project, resource_type="ec2_instance")
            resources = [
                {"id": r.resource_id, "type": "ec2_instance", "region": r.region}
                for r in resources
            ] + [
                {"id": r.resource_id, "type": "rds_instance", "region": r.region}
                for r in tracker.get_active_resources(project=project, resource_type="rds_instance")
            ]

        if not resources:
            self.redis.publish_status(
                "power",
                data={
                    "message": "No resources found to control.",
                    "action": action,
                    "project": project,
                    "resources": resources,
                },
                request_id=request_id,
                status="success",
            )
            return

        count = 0
        errors = []
        for res in resources:
            res_id = res.get("id")
            res_type = res.get("type")
            region = res.get("region")
            session = get_session(region_name=region)
            try:
                if res_type == "ec2_instance":
                    ec2 = session.client("ec2", region_name=region)
                    if action == "start":
                        resp = ec2.start_instances(InstanceIds=[res_id])
                        # Verify the request was accepted
                        if resp.get("StartingInstances"):
                            logger.info(f"Started EC2 instance {res_id} in {region}")
                        else:
                            raise RuntimeError("Start instances returned no StartingInstances")
                    else:
                        resp = ec2.stop_instances(InstanceIds=[res_id])
                        # Verify the request was accepted
                        if resp.get("StoppingInstances"):
                            logger.info(f"Stopped EC2 instance {res_id} in {region}")
                        else:
                            raise RuntimeError("Stop instances returned no StoppingInstances")
                    count += 1
                elif res_type == "rds_instance":
                    rds = session.client("rds", region_name=region)
                    if action == "start":
                        resp = rds.start_db_instance(DBInstanceIdentifier=res_id)
                        logger.info(f"Started RDS instance {res_id} in {region}")
                    else:
                        resp = rds.stop_db_instance(DBInstanceIdentifier=res_id)
                        logger.info(f"Stopped RDS instance {res_id} in {region}")
                    count += 1
            except Exception as exc:
                error_msg = str(exc)
                errors.append(f"{res_id} ({res_type}): {error_msg}")
                logger.error(f"Failed to {action} {res_type} {res_id}: {exc}")
                self.redis.publish_status(
                    "power",
                    data={
                        "error": error_msg,
                        "resource": res_id,
                        "type": res_type,
                        "action": action,
                        "project": project,
                        "resources": resources,
                    },
                    request_id=request_id,
                    status="error",
                )

        if errors:
            # Some resources failed
            error_msg = f"Failed to {action} {len(errors)} resource(s): " + "; ".join(errors[:3])
            if len(errors) > 3:
                error_msg += f" and {len(errors) - 3} more"
            self.redis.publish_status(
                "power",
                data={
                    "message": error_msg,
                    "action": action,
                    "project": project,
                    "resources": resources,
                    "count": count,
                    "errors": errors,
                },
                request_id=request_id,
                status="error" if count == 0 else "partial",
            )
        else:
            # All resources succeeded
            self.redis.publish_status(
                "power",
                data={
                    "message": f"{action.capitalize()} command sent to {count} resource(s). Waiting for confirmation...",
                    "action": action,
                    "project": project,
                    "resources": resources,
                    "count": count,
                },
                request_id=request_id,
                status="success",
            )

    def _handle_project_refresh(self, data: Dict[str, Any], request_id: Optional[str]):
        from storage import get_project_path
        import yaml
        from app.core.aws.resources import AWSResourceManager

        slug = data.get("project")
        if not slug:
            return
        path = get_project_path(slug)
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                blueprint = yaml.safe_load(f)
        except Exception as exc:
            logger.error("Failed reading project for refresh: %s", exc)
            return

        region = blueprint.get("project", {}).get("region", "us-east-1")
        manager = AWSResourceManager(region)
        updated = False

        compute = blueprint.get("compute", {})
        instance_id = compute.get("instance_id")
        if instance_id:
            result = manager.get_instance_status(instance_id)
            if result.success:
                new_status = result.data.get("state", "unknown")
                if compute.get("status") != new_status:
                    compute["status"] = new_status
                    compute["public_ip"] = result.data.get("public_ip")
                    compute["private_ip"] = result.data.get("private_ip")
                    updated = True

        data_section = blueprint.get("data", {})
        db = data_section.get("db", {})
        db_id = db.get("identifier")
        if db_id and db.get("status") not in ["skipped", None]:
            result = manager.get_db_status(db_id)
            if result.success:
                new_status = result.data.get("status", "unknown")
                if db.get("status") != new_status:
                    db["status"] = new_status
                    db["endpoint"] = result.data.get("endpoint")
                    updated = True

        if updated:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(blueprint, f, default_flow_style=False, sort_keys=False)

        self.redis.publish_status(
            "project_refresh_complete",
            data={"project": slug, "updated": updated},
            request_id=request_id,
            status="success",
        )

    def _handle_terminate(self, data: Dict[str, Any], request_id: Optional[str]):
        resources = data.get("resources") or []
        project = data.get("project")
        if not resources:
            self.redis.publish_status(
                "terminate_complete",
                data={"message": "No resources provided.", "resources": [], "project": project},
                request_id=request_id,
                status="success",
            )
            return

        allowed_projects = set()
        for res in resources:
            tags = res.get("tags") or {}
            project_value = tags.get("pockitect:project")
            if project_value:
                allowed_projects.update(self._split_project_tags(project_value))

        filtered_resources = []
        for res in resources:
            if self._has_foreign_project_tags(res, allowed_projects):
                self.redis.publish_status(
                    "terminate_skipped",
                    data={
                        "resource_id": res.get("id"),
                        "resource_type": res.get("type"),
                        "region": res.get("region"),
                        "reason": "resource tagged with another project",
                    },
                    request_id=request_id,
                    status="skipped",
                )
                continue
            filtered_resources.append(res)

        resources = filtered_resources
        if not resources:
            self.redis.publish_status(
                "terminate_complete",
                data={
                    "message": "All resources skipped due to project tags.",
                    "resources": [],
                    "project": project,
                },
                request_id=request_id,
                status="success",
            )
            return

        graph = self._build_dependency_graph(resources)
        if not graph:
            self.redis.publish_status(
                "terminate_complete",
                data={
                    "message": "No valid resources provided.",
                    "resources": [],
                    "project": project,
                },
                request_id=request_id,
                status="success",
            )
            return
        delete_layers = list(reversed(self._topological_layers(graph)))
        deleter = ResourceDeleter()

        total = sum(len(layer) for layer in delete_layers)
        step = 0
        for layer_idx, layer in enumerate(delete_layers):
            logger.info(f"Processing deletion layer {layer_idx + 1}/{len(delete_layers)} with {len(layer)} resources")
            layer_errors = []
            
            # Process all resources in this layer
            for node in layer:
                step += 1
                try:
                    success = deleter.delete_resource(node.resource_id, node.resource_type, node.region)
                    if not success:
                        raise RuntimeError("Unsupported resource type")
                    self.redis.publish_status(
                        "terminate_progress",
                        data={
                            "resource_id": node.resource_id,
                            "resource_type": node.resource_type,
                            "region": node.region,
                            "step": step,
                            "total": total,
                            "layer": layer_idx + 1,
                            "project": project,
                        },
                        request_id=request_id,
                        status="in_progress",
                    )
                except Exception as exc:
                    error_msg = str(exc)
                    layer_errors.append((node, error_msg))
                    self.redis.publish_status(
                        "terminate_error",
                        data={
                            "resource_id": node.resource_id,
                            "resource_type": node.resource_type,
                            "region": node.region,
                            "error": error_msg,
                            "project": project,
                        },
                        request_id=request_id,
                        status="error",
                    )
            
            # Wait for layer to settle before moving to next (especially important for instances terminating)
            if layer_errors:
                logger.warning(f"Layer {layer_idx + 1} completed with {len(layer_errors)} errors: {[e[1] for e in layer_errors[:3]]}")
            
            # Small delay between layers to let AWS state propagate
            import time
            time.sleep(2)

        self.redis.publish_status(
            "terminate_complete",
            data={"total": total, "resources": resources, "project": project},
            request_id=request_id,
            status="success",
        )

    def _build_dependency_graph(self, resources: Iterable[Dict[str, Any]]) -> Dict[GraphNode, Set[GraphNode]]:
        graph: Dict[GraphNode, Set[GraphNode]] = {}
        queue: List[GraphNode] = []
        resource_index: Dict[str, GraphNode] = {}

        for res in resources:
            res_id = res.get("id")
            res_type = res.get("type")
            region = res.get("region")
            if not res_id or not res_type or not region:
                continue
            node = GraphNode(res_id, res_type, region)
            queue.append(node)
            resource_index[res_id] = node
            graph.setdefault(node, set())

        visited: Set[GraphNode] = set()
        
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            children = self._discover_children(node)
            for child in children:
                # Check if this child already exists in the graph (from initial resources)
                # If so, use the existing node to maintain graph consistency
                existing_child = resource_index.get(child.resource_id)
                if existing_child and existing_child.resource_type == child.resource_type and existing_child.region == child.region:
                    # Use the existing node instead of the discovered one
                    child = existing_child
                
                # Always set up the dependency edge (parent -> child means child depends on parent)
                graph.setdefault(node, set()).add(child)
                graph.setdefault(child, set())
                
                # If child wasn't in initial resources, add it to index
                if child.resource_id not in resource_index:
                    resource_index[child.resource_id] = child
                    
                if child not in visited:
                    queue.append(child)

        # Apply explicit dependencies from tags/details
        for res in resources:
            node = resource_index.get(res.get("id"))
            if not node:
                continue
            depends_on = []
            tags = res.get("tags") or {}
            details = res.get("details") or {}
            if tags.get("depends_on"):
                depends_on.extend([x.strip() for x in tags["depends_on"].split(",") if x.strip()])
            if isinstance(details.get("depends_on"), list):
                depends_on.extend([str(x) for x in details["depends_on"]])
            for dep_id in depends_on:
                dep_node = resource_index.get(dep_id)
                if dep_node:
                    graph.setdefault(dep_node, set()).add(node)

        return graph

    def _discover_children(self, node: GraphNode) -> List[GraphNode]:
        children: List[GraphNode] = []
        session = get_session(region_name=node.region)
        finder = ChildFinder(session)

        for child in finder.find_children(node.resource_id, node.resource_type, node.region):
            children.append(GraphNode(child.id, child.type, child.region))

        if node.resource_type == "ec2_instance":
            try:
                ec2 = session.client("ec2", region_name=node.region)
                resp = ec2.describe_instances(InstanceIds=[node.resource_id])
                for reservation in resp.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        for mapping in inst.get("BlockDeviceMappings", []):
                            ebs = mapping.get("Ebs", {})
                            vol_id = ebs.get("VolumeId")
                            if vol_id:
                                children.append(GraphNode(vol_id, "ebs_volume", node.region))
                        for eni in inst.get("NetworkInterfaces", []):
                            eni_id = eni.get("NetworkInterfaceId")
                            attachment = eni.get("Attachment", {})
                            device_index = attachment.get("DeviceIndex")
                            # Skip primary ENI (device index 0) - it's deleted automatically with the instance
                            if eni_id and device_index != 0:
                                children.append(GraphNode(eni_id, "network_interface", node.region))
                        # Discover security groups attached to the instance
                        for sg in inst.get("SecurityGroups", []):
                            sg_id = sg.get("GroupId")
                            if sg_id:
                                children.append(GraphNode(sg_id, "security_group", node.region))
                        public_ip = inst.get("PublicIpAddress")
                        if public_ip:
                            children.append(GraphNode(public_ip, "elastic_ip", node.region))
            except Exception:
                pass
        
        if node.resource_type == "network_interface":
            try:
                ec2 = session.client("ec2", region_name=node.region)
                resp = ec2.describe_network_interfaces(NetworkInterfaceIds=[node.resource_id])
                for eni in resp.get("NetworkInterfaces", []):
                    # Discover security groups attached to the network interface
                    for sg in eni.get("Groups", []):
                        sg_id = sg.get("GroupId")
                        if sg_id:
                            children.append(GraphNode(sg_id, "security_group", node.region))
            except Exception:
                pass

        return children

    def _topological_sort(self, graph: Dict[GraphNode, Set[GraphNode]]) -> List[GraphNode]:
        indegree: Dict[GraphNode, int] = {}
        for node in graph:
            indegree.setdefault(node, 0)
            for child in graph[node]:
                indegree[child] = indegree.get(child, 0) + 1

        queue = [node for node, degree in indegree.items() if degree == 0]
        order: List[GraphNode] = []
        while queue:
            node = queue.pop()
            order.append(node)
            for child in graph.get(node, set()):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(order) != len(indegree):
            # Cycle detected, append remaining nodes deterministically
            for node in indegree:
                if node not in order:
                    order.append(node)
        return order

    def _topological_layers(self, graph: Dict[GraphNode, Set[GraphNode]]) -> List[List[GraphNode]]:
        indegree: Dict[GraphNode, int] = {}
        for node in graph:
            indegree.setdefault(node, 0)
            for child in graph[node]:
                indegree[child] = indegree.get(child, 0) + 1

        def _node_key(node: GraphNode) -> Tuple[str, str, str]:
            return (node.resource_type, node.resource_id, node.region)

        queue = sorted([node for node, degree in indegree.items() if degree == 0], key=_node_key)
        layers: List[List[GraphNode]] = []
        while queue:
            layer = list(queue)
            layers.append(layer)
            next_queue: List[GraphNode] = []
            for node in layer:
                for child in graph.get(node, set()):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        next_queue.append(child)
            queue = sorted(next_queue, key=_node_key)

        if sum(len(layer) for layer in layers) != len(indegree):
            remaining = [node for node in indegree if all(node not in layer for layer in layers)]
            if remaining:
                layers.append(sorted(remaining, key=_node_key))
        return layers

    def _split_project_tags(self, value: str) -> Set[str]:
        return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}

    def _has_foreign_project_tags(self, resource: Dict[str, Any], allowed_projects: Set[str]) -> bool:
        if not allowed_projects:
            return False
        tags = resource.get("tags") or {}
        project_value = tags.get("pockitect:project")
        if not project_value:
            return False
        projects = self._split_project_tags(project_value)
        if len(projects) > 1:
            return True
        return projects.isdisjoint(allowed_projects)
