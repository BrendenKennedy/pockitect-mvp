from __future__ import annotations

from typing import Any, Dict, Iterable, List


def extract_regions_from_resources(resources: Iterable[Dict[str, Any]]) -> List[str]:
    """Extract unique sorted regions from a resource list."""
    return sorted({r.get("region") for r in resources if r.get("region")})
