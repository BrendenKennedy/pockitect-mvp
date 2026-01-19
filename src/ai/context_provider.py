"""Builds structured context for the AI agent."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any, Dict, Optional

from app.core.redis_client import RedisClient
from app.core.config import WORKSPACE_ROOT
from app.core.aws.cost_service import get_cost_service, CostService, KEY_COST_LAST_REFRESH

from storage import list_projects

from wizard.pages.compute import INSTANCE_TYPES, COMMON_AMIS
from wizard.pages.project_basics import AWS_REGIONS
from wizard.pages.data import DB_ENGINES, DB_INSTANCE_CLASSES

logger = logging.getLogger(__name__)


class ContextProvider:
    def __init__(
        self,
        monitor_tab=None,
        cache_ttl_seconds: int = 60,
        reference_dir: Optional[Path] = None,
    ):
        self.monitor_tab = monitor_tab
        self.cache_ttl_seconds = cache_ttl_seconds
        self.reference_dir = reference_dir or (WORKSPACE_ROOT / "docs" / "ai_refs")
        self._redis = RedisClient()
        self._cost_service: Optional[CostService] = None
        self._cache_keys = {
            "resources": "pockitect:ai:resources_summary",
            "projects": "pockitect:ai:projects_summary",
            "budget": "pockitect:ai:budget_summary",
            "last_resource_scan": "pockitect:ai:last_resource_scan",
            "references": "pockitect:ai:reference_notes",
        }

    def _get_cached(self, key: str) -> Optional[str]:
        try:
            conn = self._redis.get_connection()
            return conn.get(key)
        except Exception:
            return None

    def _set_cached(self, key: str, value: str) -> None:
        try:
            conn = self._redis.get_connection()
            conn.setex(key, self.cache_ttl_seconds, value)
        except Exception:
            return

    def get_resources_summary(self) -> str:
        cached = self._get_cached(self._cache_keys["resources"])
        if cached:
            return cached
        if not self.monitor_tab or not getattr(self.monitor_tab, "resources", None):
            return "No resources scanned yet."

        resources = self.monitor_tab.resources
        by_region = defaultdict(Counter)
        by_project = Counter()

        for res in resources:
            by_region[res.region][res.type] += 1
            project_tag = res.tags.get("pockitect:project")
            if project_tag:
                by_project[project_tag] += 1

        lines = ["Resource counts by region:"]
        for region in sorted(by_region.keys()):
            counts = by_region[region]
            summary = ", ".join(f"{rtype}: {count}" for rtype, count in counts.items())
            lines.append(f"- {region}: {summary}")

        if by_project:
            lines.append("Resources tagged by project:")
            for project, count in by_project.most_common(10):
                lines.append(f"- {project}: {count}")

        summary = "\n".join(lines)
        self._set_cached(self._cache_keys["resources"], summary)
        return summary

    def get_resources_age_seconds(self) -> Optional[int]:
        timestamp = self._get_cached(self._cache_keys["last_resource_scan"])
        return self._age_seconds(timestamp)

    def get_projects_summary(self) -> str:
        cached = self._get_cached(self._cache_keys["projects"])
        if cached:
            return cached
        projects = list_projects()
        if not projects:
            return "No projects found."

        lines = ["Existing projects:"]
        for project in projects:
            name = project.get("name") or project.get("slug") or "unknown"
            region = project.get("region") or "unknown"
            status = project.get("status") or "draft"
            lines.append(f"- {name} ({region}) status={status}")
        summary = "\n".join(lines)
        self._set_cached(self._cache_keys["projects"], summary)
        return summary

    def get_budget_age_seconds(self) -> Optional[int]:
        try:
            conn = self._redis.get_connection()
            timestamp = conn.get(KEY_COST_LAST_REFRESH)
        except Exception:
            timestamp = None
        return self._age_seconds(timestamp)

    def get_aws_specs(self) -> Dict[str, Any]:
        return {
            "regions": [rid for rid, _ in AWS_REGIONS],
            "instance_types": [iid for iid, _ in INSTANCE_TYPES],
            "amis": [ami_id for ami_id, _, _ in COMMON_AMIS],
            "db_engines": [engine for engine, _ in DB_ENGINES],
            "db_instance_classes": [cls for cls, _ in DB_INSTANCE_CLASSES],
        }

    def get_comprehensive_context(self) -> Dict[str, Any]:
        return {
            "resources_summary": self.get_resources_summary(),
            "resources_age_seconds": self.get_resources_age_seconds(),
            "projects_summary": self.get_projects_summary(),
            "aws_specs": self.get_aws_specs(),
            "budget_summary": self.get_budget_summary(),
            "budget_age_seconds": self.get_budget_age_seconds(),
            "context_freshness": self.get_context_freshness_report(),
            "reference_notes": self.get_reference_notes(),
        }
    
    @property
    def cost_service(self) -> CostService:
        """Lazy-load cost service."""
        if self._cost_service is None:
            self._cost_service = get_cost_service()
        return self._cost_service
    
    def get_budget_summary(self, force_refresh: bool = False) -> str:
        """
        Get budget and cost summary for AI context.
        
        Returns:
            Human-readable string with budget status and cost breakdown
        """
        if not force_refresh:
            cached = self._get_cached(self._cache_keys["budget"])
            if cached:
                return cached
        
        try:
            budget_status = self.cost_service.get_budget_status(force_refresh=force_refresh)
            cost_summary = self.cost_service.get_cost_summary(force_refresh=False)  # Already fetched
            
            lines = []
            
            # Budget status
            if budget_status:
                lines.append(self.cost_service.format_budget_status_for_ai(budget_status))
            else:
                lines.append("Budget status: Unable to fetch (Cost Explorer access may be required)")
            
            # Cost breakdown
            if cost_summary:
                lines.append("")
                lines.append(self.cost_service.format_cost_breakdown_for_ai(cost_summary))
            
            summary = "\n".join(lines)
            self._set_cached(self._cache_keys["budget"], summary)
            return summary
            
        except Exception as e:
            logger.warning(f"Failed to get budget summary: {e}")
            return "Cost data unavailable. Ensure AWS Cost Explorer access is configured."
    
    def get_budget_status_quick(self) -> Dict[str, Any]:
        """
        Get a quick budget status dict for AI to make decisions.
        
        Returns:
            Dict with key budget metrics
        """
        try:
            status = self.cost_service.get_budget_status()
            if status:
                return {
                    "budget": status.monthly_budget,
                    "spent": status.current_spend,
                    "remaining": status.remaining,
                    "percentage_used": status.percentage_used,
                    "days_remaining": status.days_remaining,
                    "forecast": status.forecast_end_of_month,
                    "over_budget": status.is_over_budget,
                    "forecast_over_budget": status.is_forecast_over_budget,
                }
        except Exception as e:
            logger.debug(f"Quick budget status failed: {e}")
        return {}
    
    def set_monthly_budget(self, budget: float) -> bool:
        """Set the monthly budget."""
        return self.cost_service.set_monthly_budget(budget)

    def get_context_freshness_report(self) -> str:
        resources_age = self.get_resources_age_seconds()
        budget_age = self.get_budget_age_seconds()
        resources_desc = self._format_age("Resources", resources_age)
        budget_desc = self._format_age("Costs", budget_age)
        return f"{resources_desc}; {budget_desc}"

    def get_reference_notes(self) -> str:
        cached = self._get_cached(self._cache_keys["references"])
        if cached:
            return cached
        notes = self._load_reference_notes()
        self._set_cached(self._cache_keys["references"], notes)
        return notes

    def _load_reference_notes(self) -> str:
        if not self.reference_dir.exists():
            return "No reference notes available."
        lines = ["Reference Notes:"]
        for path in sorted(self.reference_dir.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                lines.append(f"- {path.stem}")
                lines.append(content)
                lines.append("")
            except Exception:
                continue
        return "\n".join(lines).strip() if len(lines) > 1 else "No reference notes available."

    def _format_age(self, label: str, age_seconds: Optional[int]) -> str:
        if age_seconds is None:
            return f"{label}: unknown"
        if age_seconds < 60:
            return f"{label}: fresh ({age_seconds}s ago)"
        minutes = age_seconds // 60
        if minutes < 60:
            return f"{label}: fresh ({minutes}m ago)"
        hours = minutes // 60
        return f"{label}: stale ({hours}h ago)"

    def _age_seconds(self, timestamp: Optional[str]) -> Optional[int]:
        if not timestamp:
            return None
        try:
            parsed = self._parse_iso(timestamp)
            now = datetime.now(timezone.utc)
            return max(0, int((now - parsed).total_seconds()))
        except Exception:
            return None

    def _parse_iso(self, value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
