import pytest
from unittest.mock import MagicMock
from app.core.aws.deployer import ResourceDeployer

@pytest.mark.unit
@pytest.mark.asyncio
async def test_deploy_vpc_subnet(mock_boto_session, sample_deployment_yaml):
    # Mock EC2
    mock_ec2 = MagicMock()
    mock_ec2.create_vpc.return_value = {'Vpc': {'VpcId': 'vpc-test'}}
    mock_ec2.create_subnet.return_value = {'Subnet': {'SubnetId': 'subnet-test'}}
    mock_ec2.create_security_group.return_value = {'GroupId': 'sg-test'}
    mock_ec2.run_instances.return_value = {'Instances': [{'InstanceId': 'i-test'}]}
    
    # Ensure client() returns mock_ec2
    mock_boto_session.return_value.client.return_value = mock_ec2
    
    deployer = ResourceDeployer()
    
    progress_calls = []
    def on_progress(msg, step=None, total=None):
        progress_calls.append((step, msg))
        
    await deployer.deploy(sample_deployment_yaml, progress_callback=on_progress)
    
    # Verify sequence
    assert mock_ec2.create_vpc.called
    assert mock_ec2.create_subnet.called
    
    # Verify progress callback
    assert len(progress_calls) > 0
    steps = [s[0] for s in progress_calls]
    assert steps == sorted(steps) # Monotonic progress

@pytest.mark.unit
@pytest.mark.asyncio
async def test_deploy_failure(mock_boto_session, sample_deployment_yaml):
    mock_ec2 = MagicMock()
    mock_ec2.create_vpc.side_effect = Exception("AWS Limit Exceeded")
    mock_boto_session.return_value.client.return_value = mock_ec2
    
    deployer = ResourceDeployer()
    
    with pytest.raises(Exception) as exc:
        await deployer.deploy(sample_deployment_yaml)
    
    assert "AWS Limit Exceeded" in str(exc.value)
