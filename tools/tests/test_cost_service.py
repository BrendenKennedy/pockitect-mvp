"""
Tests for the AWS Cost Service.

These tests use mocking to avoid actual AWS API calls.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.core.aws.cost_service import (
    CostService,
    CostSummary,
    BudgetStatus,
    get_cost_service,
)


def test_cost_summary_dataclass():
    """Test CostSummary dataclass."""
    print("Testing CostSummary dataclass...")
    
    summary = CostSummary(
        total_cost=45.67,
        currency="USD",
        period_start="2026-01-01",
        period_end="2026-01-20",
        last_updated="2026-01-19T12:00:00Z",
        forecast_end_of_month=92.50,
        by_service={"Amazon EC2": 30.00, "Amazon RDS": 15.67},
        by_project={"my-blog": 25.00, "api-server": 20.67}
    )
    
    assert summary.total_cost == 45.67
    assert summary.currency == "USD"
    assert summary.forecast_end_of_month == 92.50
    assert "Amazon EC2" in summary.by_service
    assert "my-blog" in summary.by_project
    
    print("  ✓ CostSummary dataclass test passed")


def test_budget_status_dataclass():
    """Test BudgetStatus dataclass."""
    print("Testing BudgetStatus dataclass...")
    
    status = BudgetStatus(
        monthly_budget=100.00,
        current_spend=45.67,
        remaining=54.33,
        percentage_used=45.67,
        forecast_end_of_month=92.50,
        forecast_percentage=92.50,
        is_over_budget=False,
        is_forecast_over_budget=False,
        days_remaining=12,
        currency="USD"
    )
    
    assert status.monthly_budget == 100.00
    assert status.current_spend == 45.67
    assert status.remaining == 54.33
    assert status.percentage_used == 45.67
    assert not status.is_over_budget
    assert status.days_remaining == 12
    
    print("  ✓ BudgetStatus dataclass test passed")


def test_budget_status_over_budget():
    """Test BudgetStatus when over budget."""
    print("Testing BudgetStatus over budget...")
    
    status = BudgetStatus(
        monthly_budget=50.00,
        current_spend=75.00,
        remaining=-25.00,
        percentage_used=150.0,
        is_over_budget=True,
        days_remaining=5
    )
    
    assert status.is_over_budget
    assert status.remaining < 0
    assert status.percentage_used > 100
    
    print("  ✓ BudgetStatus over budget test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_cost_service_initialization(mock_redis):
    """Test CostService initializes correctly."""
    print("Testing CostService initialization...")
    
    mock_redis.return_value = MagicMock()
    
    service = CostService(default_budget=150.0)
    
    assert service.default_budget == 150.0
    assert service._cost_explorer is None  # Lazy loaded
    
    print("  ✓ CostService initialization test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_get_monthly_budget_default(mock_redis):
    """Test getting default budget when none set."""
    print("Testing get_monthly_budget default...")
    
    mock_conn = MagicMock()
    mock_conn.get.return_value = None
    mock_redis.return_value.get_connection.return_value = mock_conn
    
    service = CostService(default_budget=100.0)
    budget = service.get_monthly_budget()
    
    assert budget == 100.0
    
    print("  ✓ get_monthly_budget default test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_get_monthly_budget_from_cache(mock_redis):
    """Test getting budget from Redis cache."""
    print("Testing get_monthly_budget from cache...")
    
    import json
    mock_conn = MagicMock()
    mock_conn.get.return_value = json.dumps({"monthly_budget": 250.0})
    mock_redis.return_value.get_connection.return_value = mock_conn
    
    service = CostService(default_budget=100.0)
    budget = service.get_monthly_budget()
    
    assert budget == 250.0
    
    print("  ✓ get_monthly_budget from cache test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_set_monthly_budget(mock_redis):
    """Test setting monthly budget."""
    print("Testing set_monthly_budget...")
    
    mock_conn = MagicMock()
    mock_redis.return_value.get_connection.return_value = mock_conn
    
    service = CostService()
    result = service.set_monthly_budget(200.0)
    
    assert result is True
    mock_conn.set.assert_called_once()
    
    print("  ✓ set_monthly_budget test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_format_budget_status_for_ai(mock_redis):
    """Test formatting budget status for AI context."""
    print("Testing format_budget_status_for_ai...")
    
    mock_redis.return_value = MagicMock()
    
    service = CostService()
    
    status = BudgetStatus(
        monthly_budget=100.00,
        current_spend=45.67,
        remaining=54.33,
        percentage_used=45.67,
        forecast_end_of_month=92.50,
        forecast_percentage=92.50,
        is_over_budget=False,
        is_forecast_over_budget=False,
        days_remaining=12,
        currency="USD"
    )
    
    formatted = service.format_budget_status_for_ai(status)
    
    assert "Monthly Budget: $100.00" in formatted
    assert "Current Spend: $45.67" in formatted
    assert "45.7% of budget" in formatted
    assert "Remaining: $54.33" in formatted
    assert "Days Left in Month: 12" in formatted
    assert "✅ Budget on track" in formatted
    
    print("  ✓ format_budget_status_for_ai test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_format_budget_status_over_budget(mock_redis):
    """Test formatting when over budget."""
    print("Testing format_budget_status_for_ai over budget...")
    
    mock_redis.return_value = MagicMock()
    
    service = CostService()
    
    status = BudgetStatus(
        monthly_budget=50.00,
        current_spend=75.00,
        remaining=-25.00,
        percentage_used=150.0,
        is_over_budget=True,
        days_remaining=5,
        currency="USD"
    )
    
    formatted = service.format_budget_status_for_ai(status)
    
    assert "⚠️ WARNING: Over budget!" in formatted
    
    print("  ✓ format_budget_status_for_ai over budget test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_format_budget_status_approaching_limit(mock_redis):
    """Test formatting when approaching budget limit."""
    print("Testing format_budget_status_for_ai approaching limit...")
    
    mock_redis.return_value = MagicMock()
    
    service = CostService()
    
    status = BudgetStatus(
        monthly_budget=100.00,
        current_spend=85.00,
        remaining=15.00,
        percentage_used=85.0,
        is_over_budget=False,
        days_remaining=10,
        currency="USD"
    )
    
    formatted = service.format_budget_status_for_ai(status)
    
    assert "⚠️ CAUTION: Approaching budget limit" in formatted
    
    print("  ✓ format_budget_status_for_ai approaching limit test passed")


@patch('app.core.aws.cost_service.RedisClient')
def test_format_cost_breakdown_for_ai(mock_redis):
    """Test formatting cost breakdown for AI context."""
    print("Testing format_cost_breakdown_for_ai...")
    
    mock_redis.return_value = MagicMock()
    
    service = CostService()
    
    summary = CostSummary(
        total_cost=45.67,
        currency="USD",
        period_start="2026-01-01",
        period_end="2026-01-20",
        last_updated="2026-01-19T12:00:00Z",
        by_service={"Amazon EC2": 30.00, "Amazon RDS": 15.67},
        by_project={"my-blog": 25.00, "api-server": 20.67}
    )
    
    formatted = service.format_cost_breakdown_for_ai(summary)
    
    assert "2026-01-01 to 2026-01-20" in formatted
    assert "By AWS Service:" in formatted
    assert "Amazon EC2: $30.00" in formatted
    assert "By Project" in formatted
    assert "my-blog: $25.00" in formatted
    
    print("  ✓ format_cost_breakdown_for_ai test passed")


@patch('app.core.aws.cost_service.get_session')
@patch('app.core.aws.cost_service.RedisClient')
def test_fetch_costs_from_aws(mock_redis, mock_get_session):
    """Test fetching costs from AWS Cost Explorer."""
    print("Testing _fetch_costs_from_aws...")
    
    mock_redis.return_value = MagicMock()
    
    # Mock Cost Explorer response
    mock_ce = MagicMock()
    mock_ce.get_cost_and_usage.return_value = {
        'ResultsByTime': [{
            'Groups': [
                {
                    'Keys': ['Amazon EC2'],
                    'Metrics': {'UnblendedCost': {'Amount': '30.00', 'Unit': 'USD'}}
                },
                {
                    'Keys': ['Amazon RDS'],
                    'Metrics': {'UnblendedCost': {'Amount': '15.67', 'Unit': 'USD'}}
                }
            ]
        }]
    }
    mock_ce.get_cost_forecast.side_effect = Exception("Forecast not available")
    
    mock_session = MagicMock()
    mock_session.client.return_value = mock_ce
    mock_get_session.return_value = mock_session
    
    service = CostService()
    summary = service._fetch_costs_from_aws()
    
    assert summary is not None
    assert summary.total_cost == 45.67
    assert summary.currency == "USD"
    assert "Amazon EC2" in summary.by_service
    
    print("  ✓ _fetch_costs_from_aws test passed")


def test_get_cost_service_singleton():
    """Test that get_cost_service returns singleton."""
    print("Testing get_cost_service singleton...")
    
    # Reset the global
    import app.core.aws.cost_service as cost_module
    cost_module._cost_service = None
    
    with patch('app.core.aws.cost_service.RedisClient'):
        with patch('app.core.aws.cost_service.get_session'):
            service1 = get_cost_service()
            service2 = get_cost_service()
            
            assert service1 is service2
    
    print("  ✓ get_cost_service singleton test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AWS Cost Service Tests")
    print("="*60 + "\n")
    
    test_cost_summary_dataclass()
    test_budget_status_dataclass()
    test_budget_status_over_budget()
    test_cost_service_initialization()
    test_get_monthly_budget_default()
    test_get_monthly_budget_from_cache()
    test_set_monthly_budget()
    test_format_budget_status_for_ai()
    test_format_budget_status_over_budget()
    test_format_budget_status_approaching_limit()
    test_format_cost_breakdown_for_ai()
    test_fetch_costs_from_aws()
    test_get_cost_service_singleton()
    
    print("\n" + "="*60)
    print("All cost service tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
