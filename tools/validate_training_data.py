#!/usr/bin/env python3
"""
Validate training data quality for Pockitect.

Checks:
- Required fields are present
- JSON is valid
- Schema matches expected structure
- Prompts are non-empty
- YAML data can be merged with defaults

Usage:
    python tools/validate_training_data.py
    python tools/validate_training_data.py --fix
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from storage import create_empty_blueprint


class TrainingDataValidator:
    def __init__(self, training_dir: Path):
        self.training_dir = training_dir
        self.errors = []
        self.warnings = []
        self.valid_count = 0
    
    def validate_file_pair(
        self,
        prompt_file: Path,
        json_file: Path,
        prompt_text: str | None = None,
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate a single prompt/json file pair."""
        errors = []
        warnings = []
        
        # Check prompt file
        try:
            prompt = prompt_text if prompt_text is not None else prompt_file.read_text(encoding="utf-8").strip()
            prompt = prompt.strip()
            if not prompt:
                errors.append(f"Prompt file is empty")
            elif len(prompt) < 20:
                warnings.append(f"Prompt is very short ({len(prompt)} chars)")
        except Exception as e:
            errors.append(f"Failed to read prompt file: {e}")
            return False, errors, warnings
        
        # Check JSON file
        try:
            yaml_data = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            return False, errors, warnings
        except Exception as e:
            errors.append(f"Failed to read JSON file: {e}")
            return False, errors, warnings
        
        # Validate structure
        required_sections = ["project", "network", "compute", "data", "security"]
        for section in required_sections:
            if section not in yaml_data:
                errors.append(f"Missing required section: {section}")
        
        # Validate project section
        if "project" in yaml_data:
            project = yaml_data["project"]
            if "name" not in project or not project["name"]:
                errors.append("project.name is required and cannot be empty")
            if "region" not in project:
                warnings.append("project.region is missing (will use default)")
            elif project["region"]:
                # Validate region format (basic check)
                if not isinstance(project["region"], str) or len(project["region"]) < 6:
                    warnings.append(f"project.region looks invalid: {project['region']}")
        
        # Validate network section
        if "network" in yaml_data:
            network = yaml_data["network"]
            if "rules" in network and isinstance(network["rules"], list):
                for i, rule in enumerate(network["rules"]):
                    if not isinstance(rule, dict):
                        errors.append(f"network.rules[{i}] is not a dict")
                    else:
                        if "port" not in rule:
                            errors.append(f"network.rules[{i}] missing 'port'")
                        if "protocol" not in rule:
                            errors.append(f"network.rules[{i}] missing 'protocol'")
                        if "cidr" not in rule:
                            errors.append(f"network.rules[{i}] missing 'cidr'")
        
        # Validate compute section
        if "compute" in yaml_data:
            compute = yaml_data["compute"]
            if "instance_type" not in compute:
                warnings.append("compute.instance_type is missing (will use default)")
            elif compute.get("instance_type"):
                # Check if it looks like a valid instance type
                if not compute["instance_type"].startswith(("t", "m", "c", "r", "g")):
                    warnings.append(f"compute.instance_type looks unusual: {compute['instance_type']}")
        
        # Validate data section
        if "data" in yaml_data:
            data = yaml_data["data"]
            if "db" in data and data["db"] is not None:
                db = data["db"]
                if "engine" not in db:
                    errors.append("data.db.engine is required when db is not null")
                if "instance_class" not in db:
                    warnings.append("data.db.instance_class is missing")
        
        # Validate security section
        if "security" in yaml_data:
            security = yaml_data["security"]
            if "key_pair" in security:
                key_pair = security["key_pair"]
                if "mode" not in key_pair:
                    warnings.append("security.key_pair.mode is missing")
                if "name" not in key_pair:
                    warnings.append("security.key_pair.name is missing")
        
        # Try to merge with defaults (catches schema issues)
        try:
            project_name = yaml_data.get("project", {}).get("name", "test-validation")
            base = create_empty_blueprint(project_name)
            
            # Try a simple merge
            def safe_merge(dst: Dict, src: Dict) -> Dict:
                for key, value in src.items():
                    if isinstance(value, dict) and key in dst and isinstance(dst[key], dict):
                        safe_merge(dst[key], value)
                    else:
                        dst[key] = value
                return dst
            
            merged = safe_merge(base.copy(), yaml_data)
            
        except Exception as e:
            warnings.append(f"Could not merge with defaults: {e}")
        
        return len(errors) == 0, errors, warnings

    def _check_prompt_diversity(self, prompts: List[str]) -> List[str]:
        warnings = []
        if not prompts:
            return warnings

        normalized = [p.strip().lower() for p in prompts if p.strip()]
        duplicate_count = len(normalized) - len(set(normalized))
        if duplicate_count > 0:
            warnings.append(f"{duplicate_count} duplicate prompts detected")

        lengths = [len(p) for p in normalized]
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        short_ratio = sum(1 for length in lengths if length < 40) / len(lengths)

        if avg_len < 60:
            warnings.append(f"Average prompt length is low ({avg_len:.1f} chars)")
        if short_ratio > 0.4:
            warnings.append(f"High ratio of short prompts ({short_ratio:.0%})")

        return warnings
    
    def validate_all(self) -> Dict:
        """Validate all training data files."""
        prompt_files = sorted(self.training_dir.glob("*.prompt.txt"))
        
        if not prompt_files:
            print(f"⚠️  No training files found in {self.training_dir}")
            return {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "errors": [],
                "warnings": []
            }
        
        results = {
            "total": len(prompt_files),
            "valid": 0,
            "invalid": 0,
            "errors": [],
            "warnings": []
        }
        
        print(f"🔍 Validating {len(prompt_files)} training examples...\n")
        
        prompts_for_stats: List[str] = []

        for prompt_file in prompt_files:
            json_file = prompt_file.parent / (prompt_file.stem.replace(".prompt", "") + ".json")
            
            if not json_file.exists():
                results["errors"].append(f"{prompt_file.name}: Missing corresponding .json file")
                results["invalid"] += 1
                continue
            
            name = prompt_file.stem.replace(".prompt", "")
            try:
                prompt_text = prompt_file.read_text(encoding="utf-8").strip()
            except Exception:
                prompt_text = ""
            if prompt_text:
                prompts_for_stats.append(prompt_text)

            is_valid, errors, warnings = self.validate_file_pair(
                prompt_file, json_file, prompt_text=prompt_text
            )
            
            if is_valid:
                results["valid"] += 1
                if warnings:
                    print(f"  ⚠️  {name}: {len(warnings)} warning(s)")
                    for warning in warnings:
                        results["warnings"].append(f"{name}: {warning}")
            else:
                results["invalid"] += 1
                print(f"  ✗ {name}: {len(errors)} error(s), {len(warnings)} warning(s)")
                for error in errors:
                    results["errors"].append(f"{name}: {error}")
                    print(f"      - {error}")
                for warning in warnings:
                    results["warnings"].append(f"{name}: {warning}")
        
        diversity_warnings = self._check_prompt_diversity(prompts_for_stats)
        for warning in diversity_warnings:
            results["warnings"].append(f"dataset: {warning}")

        return results
    
    def print_summary(self, results: Dict):
        """Print validation summary."""
        print(f"\n{'='*60}")
        print(f"Validation Summary")
        print(f"{'='*60}")
        print(f"Total files:     {results['total']}")
        print(f"Valid:           {results['valid']} ✓")
        print(f"Invalid:         {results['invalid']} ✗")
        print(f"Warnings:        {len(results['warnings'])} ⚠️")
        print(f"Errors:          {len(results['errors'])}")
        
        if results['errors']:
            print(f"\n❌ Errors found:")
            for error in results['errors'][:10]:  # Show first 10
                print(f"  - {error}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more")
        
        if results['warnings'] and len(results['warnings']) <= 20:
            print(f"\n⚠️  Warnings:")
            for warning in results['warnings']:
                print(f"  - {warning}")
        elif results['warnings']:
            print(f"\n⚠️  {len(results['warnings'])} warnings (too many to display)")
        
        if results['invalid'] == 0:
            print(f"\n✅ All training files are valid!")
        else:
            print(f"\n⚠️  {results['invalid']} file(s) have errors that should be fixed.")


def main():
    parser = argparse.ArgumentParser(
        description="Validate Pockitect training data"
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("data/training"),
        help="Training data directory (default: data/training)"
    )
    
    args = parser.parse_args()
    
    if not args.training_dir.exists():
        print(f"❌ Training directory does not exist: {args.training_dir}")
        sys.exit(1)
    
    validator = TrainingDataValidator(args.training_dir)
    results = validator.validate_all()
    validator.print_summary(results)
    
    # Exit with error code if there are validation errors
    if results['invalid'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
