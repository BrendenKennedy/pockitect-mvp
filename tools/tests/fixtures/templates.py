import pytest
import yaml

@pytest.fixture
def sample_deployment_yaml(tmp_path):
    data = {
        "project": {"name": "test-project", "region": "us-east-1"},
        "resources": {
            "web-vpc": {"type": "vpc", "properties": {"cidr_block": "10.0.0.0/16"}},
            "web-subnet": {"type": "subnet", "properties": {"vpc_id": "web-vpc", "cidr_block": "10.0.1.0/24"}}
        }
    }
    p = tmp_path / "test_deploy.yaml"
    with open(p, "w") as f:
        yaml.dump(data, f)
    return str(p)
