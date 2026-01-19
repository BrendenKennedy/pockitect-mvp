from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.ambiguity_detector import AmbiguityDetector


def test_detects_missing_region_and_scale():
    detector = AmbiguityDetector()
    result = detector.detect_ambiguity("I need a backend for my app")
    assert result["is_ambiguous"] is True
    assert "region" in result["missing"]
    assert "scale" in result["missing"]


def test_detects_scale_hint():
    detector = AmbiguityDetector()
    result = detector.detect_ambiguity("I need a cheap web server")
    assert result["is_ambiguous"] is True
    assert result["suggestions"]["instance_type"] == "t3.micro"


def test_region_present_is_not_missing():
    detector = AmbiguityDetector()
    result = detector.detect_ambiguity("Create a web server in us-east-1")
    assert "region" not in result["missing"]
