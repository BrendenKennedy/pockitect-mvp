#!/usr/bin/env python3
"""
Run all Pockitect tests.
"""

import sys
import subprocess
from pathlib import Path


def run_test_file(test_file: Path) -> bool:
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file.name}")
    print('='*60)
    
    result = subprocess.run(
        [sys.executable, str(test_file)],
        cwd=test_file.parent.parent
    )
    
    return result.returncode == 0


def main():
    """Run all test files."""
    tests_dir = Path(__file__).parent
    
    test_files = [
        tests_dir / "test_storage.py",
        tests_dir / "test_aws_quota.py",
        tests_dir / "test_aws_resources.py",
        tests_dir / "test_aws_deploy.py",
        tests_dir / "test_aws_credentials.py",
    ]
    
    results = {}
    
    print("\n" + "#"*60)
    print("#  POCKITECT MVP - FULL TEST SUITE")
    print("#"*60)
    
    for test_file in test_files:
        if test_file.exists():
            results[test_file.name] = run_test_file(test_file)
        else:
            print(f"\n⚠ Test file not found: {test_file}")
            results[test_file.name] = False
    
    # Summary
    print("\n" + "#"*60)
    print("#  TEST SUMMARY")
    print("#"*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
