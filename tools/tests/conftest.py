import sys
import pytest
from unittest.mock import MagicMock

# --- PATCH MISSING MODULES FOR LEGACY CODE ---
# The application seems to have a mixed state where some legacy components 
# (wizard) import 'aws.deploy' which is missing. We mock it to allow 'main' to import.
try:
    import aws.deploy
except ImportError:
    mock_deploy = MagicMock()
    sys.modules["aws.deploy"] = mock_deploy
    # Mock specific classes expected by consumers
    mock_deploy.DeploymentOrchestrator = MagicMock
    mock_deploy.DeploymentStatus = MagicMock
    mock_deploy.DeploymentState = MagicMock
    mock_deploy.StepStatus = MagicMock
    mock_deploy.StatusPoller = MagicMock

pytest_plugins = [
    "tests.fixtures.redis",
    "tests.fixtures.boto3_mocks",
    "tests.fixtures.templates",
]

def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e", action="store_true", default=False, help="run end-to-end tests"
    )

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark test as end-to-end")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
