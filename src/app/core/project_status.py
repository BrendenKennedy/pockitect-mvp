from __future__ import annotations

from typing import Dict, Iterable, List


class ProjectStatusCalculator:
    @staticmethod
    def calculate_status_from_blueprint(blueprint: dict) -> str:
        """
        Determine overall status from a project blueprint's resource statuses.
        """
        statuses: List[str] = []
        if "network" in blueprint:
            statuses.append(blueprint["network"].get("status", "unknown"))
        if "compute" in blueprint:
            statuses.append(blueprint["compute"].get("status", "unknown"))

        # Check if resources have actually been created (have IDs)
        network = blueprint.get("network", {})
        compute = blueprint.get("compute", {})
        has_created_resources = bool(
            network.get("vpc_id") or network.get("security_group_id") or
            compute.get("instance_id")
        )

        if statuses and all(status == "running" for status in statuses):
            return "running"
        if any(status == "failed" for status in statuses):
            return "failed"
        # If status is "pending" but no resources have been created yet, treat as "draft"
        if any(status == "pending" for status in statuses):
            return "draft" if not has_created_resources else "pending"
        if statuses and all(status == "skipped" for status in statuses):
            return "skipped"
        return "unknown"

    @staticmethod
    def calculate_statuses_from_resources(
        resources: Iterable, project_names: Iterable[str]
    ) -> Dict[str, str]:
        """
        Determine per-project status based on scanned resources.
        """
        by_project = {name: [] for name in project_names}

        for res in resources:
            tags = getattr(res, "tags", None) or {}
            project = tags.get("pockitect:project")
            if project in by_project:
                by_project[project].append(res)

        statuses: Dict[str, str] = {}
        for project_name, items in by_project.items():
            if not items:
                statuses[project_name] = "draft"
                continue

            ec2_states = [r.state for r in items if r.type == "ec2_instance"]
            rds_states = [r.state for r in items if r.type == "rds_instance"]
            if ec2_states or rds_states:
                if all(state == "stopped" for state in ec2_states) and all(
                    state in ("stopped", "stopped-") for state in rds_states
                ):
                    statuses[project_name] = "stopped"
                    continue

            statuses[project_name] = "running"

        return statuses
