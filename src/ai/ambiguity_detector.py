"""Detect and resolve ambiguous user inputs."""

from __future__ import annotations

from typing import Any, Dict, List


class AmbiguityDetector:
    SCALE_HINTS = {
        "cheap": "t3.micro",
        "tiny": "t3.micro",
        "small": "t3.small",
        "medium": "t3.medium",
        "bigger": "t3.large",
        "large": "t3.large",
        "powerful": "m5.large",
        "performance": "c5.large",
        "memory": "r5.large",
    }

    def detect_ambiguity(self, user_input: str) -> Dict[str, Any]:
        lowered = user_input.lower()
        missing: List[str] = []
        suggestions: Dict[str, Any] = {}

        if not self._has_region(lowered):
            missing.append("region")

        scale_hint = self._extract_scale_hint(lowered)
        if scale_hint:
            suggestions["instance_type"] = self.SCALE_HINTS.get(scale_hint)
        else:
            missing.append("scale")

        if self._needs_database(lowered) and not self._mentions_database(lowered):
            missing.append("database")
            suggestions["db_engine"] = "postgres"

        return {
            "is_ambiguous": bool(missing),
            "missing": missing,
            "suggestions": suggestions,
        }

    def resolve_with_context(self, ambiguity: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        if "region" in ambiguity.get("missing", []):
            regions = context.get("aws_specs", {}).get("regions") or []
            resolved["region"] = regions[0] if regions else "us-east-1"

        instance_type = ambiguity.get("suggestions", {}).get("instance_type")
        if instance_type:
            resolved["instance_type"] = instance_type

        if "database" in ambiguity.get("missing", []):
            resolved["db_engine"] = ambiguity.get("suggestions", {}).get("db_engine", "postgres")

        return resolved

    def _has_region(self, text: str) -> bool:
        return any(token in text for token in ["us-east-", "us-west-", "eu-", "ap-", "sa-", "ca-"])

    def _extract_scale_hint(self, text: str) -> str | None:
        for hint in self.SCALE_HINTS.keys():
            if hint in text:
                return hint
        return None

    def _mentions_database(self, text: str) -> bool:
        return any(token in text for token in ["database", "db", "postgres", "mysql", "rds"])

    def _needs_database(self, text: str) -> bool:
        return any(token in text for token in ["api", "backend", "blog", "e-commerce", "cms"])
