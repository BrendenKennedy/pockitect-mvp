"""
AWS Cost Service - Fetches and caches cost data from AWS Cost Explorer.

This service provides:
- Current month's total AWS spend
- Cost breakdown by project (via tags)
- Budget tracking against a configurable monthly limit
- Cached data in Redis for fast AI queries
"""

import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

import boto3
from botocore.exceptions import ClientError

from app.core.redis_client import RedisClient
from app.core.aws.credentials_helper import get_session

logger = logging.getLogger(__name__)

# Redis keys for cost data
KEY_COST_SUMMARY = "pockitect:cost:summary"
KEY_COST_BY_PROJECT = "pockitect:cost:by_project"
KEY_BUDGET_CONFIG = "pockitect:cost:budget"
KEY_COST_LAST_REFRESH = "pockitect:cost:last_refresh"

# Cache TTL (costs don't change that frequently, 1 hour is reasonable)
COST_CACHE_TTL_SECONDS = 3600


@dataclass
class CostSummary:
    """Summary of AWS costs for the current billing period."""
    total_cost: float
    currency: str
    period_start: str
    period_end: str
    last_updated: str
    forecast_end_of_month: Optional[float] = None
    by_service: Dict[str, float] = field(default_factory=dict)
    by_project: Dict[str, float] = field(default_factory=dict)


@dataclass 
class BudgetStatus:
    """Budget tracking status."""
    monthly_budget: float
    current_spend: float
    remaining: float
    percentage_used: float
    forecast_end_of_month: Optional[float] = None
    forecast_percentage: Optional[float] = None
    is_over_budget: bool = False
    is_forecast_over_budget: bool = False
    days_remaining: int = 0
    currency: str = "USD"


class CostService:
    """
    Service for fetching and caching AWS cost data.
    
    Uses AWS Cost Explorer API to get real cost data and caches
    results in Redis for quick access by the AI agent.
    """
    
    def __init__(self, default_budget: float = 100.0):
        self.session = get_session()
        self.redis = RedisClient()
        self.default_budget = default_budget
        self._cost_explorer = None
    
    @property
    def cost_explorer(self):
        """Lazy-load Cost Explorer client."""
        if self._cost_explorer is None:
            # Cost Explorer is only available in us-east-1
            self._cost_explorer = self.session.client('ce', region_name='us-east-1')
        return self._cost_explorer
    
    def get_monthly_budget(self) -> float:
        """Get the configured monthly budget from Redis or return default."""
        try:
            conn = self.redis.get_connection()
            budget_str = conn.get(KEY_BUDGET_CONFIG)
            if budget_str:
                config = json.loads(budget_str)
                return float(config.get("monthly_budget", self.default_budget))
        except Exception as e:
            logger.warning(f"Failed to get budget config: {e}")
        return self.default_budget
    
    def set_monthly_budget(self, budget: float) -> bool:
        """Set the monthly budget."""
        try:
            conn = self.redis.get_connection()
            config = {
                "monthly_budget": budget,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            conn.set(KEY_BUDGET_CONFIG, json.dumps(config))
            logger.info(f"Monthly budget set to ${budget:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to set budget: {e}")
            return False
    
    def get_cost_summary(self, force_refresh: bool = False) -> Optional[CostSummary]:
        """
        Get current month's cost summary.
        
        Uses cached data if available and not expired.
        
        Args:
            force_refresh: If True, fetch fresh data from AWS
            
        Returns:
            CostSummary or None if fetch fails
        """
        # Try cache first
        if not force_refresh:
            cached = self._get_cached_summary()
            if cached:
                return cached
        
        # Fetch fresh data
        try:
            summary = self._fetch_costs_from_aws()
            if summary:
                self._cache_summary(summary)
            return summary
        except Exception as e:
            logger.error(f"Failed to fetch cost data: {e}")
            return None
    
    def get_budget_status(self, force_refresh: bool = False) -> Optional[BudgetStatus]:
        """
        Get current budget status.
        
        Returns:
            BudgetStatus with current spend vs budget analysis
        """
        summary = self.get_cost_summary(force_refresh=force_refresh)
        if not summary:
            return None
        
        budget = self.get_monthly_budget()
        remaining = budget - summary.total_cost
        percentage = (summary.total_cost / budget * 100) if budget > 0 else 0
        
        # Calculate days remaining in month
        today = datetime.utcnow()
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        days_remaining = (next_month - today).days
        
        # Check forecast
        forecast_percentage = None
        is_forecast_over = False
        if summary.forecast_end_of_month:
            forecast_percentage = (summary.forecast_end_of_month / budget * 100) if budget > 0 else 0
            is_forecast_over = summary.forecast_end_of_month > budget
        
        return BudgetStatus(
            monthly_budget=budget,
            current_spend=summary.total_cost,
            remaining=remaining,
            percentage_used=percentage,
            forecast_end_of_month=summary.forecast_end_of_month,
            forecast_percentage=forecast_percentage,
            is_over_budget=summary.total_cost > budget,
            is_forecast_over_budget=is_forecast_over,
            days_remaining=days_remaining,
            currency=summary.currency
        )
    
    def _fetch_costs_from_aws(self) -> Optional[CostSummary]:
        """Fetch cost data from AWS Cost Explorer."""
        today = datetime.utcnow()
        start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')  # Cost Explorer uses exclusive end
        
        try:
            # Get total cost and by-service breakdown
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': start_of_month,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                ]
            )
            
            total_cost = 0.0
            by_service = {}
            currency = "USD"
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service_name = group['Keys'][0]
                    amount = float(group['Metrics']['UnblendedCost']['Amount'])
                    currency = group['Metrics']['UnblendedCost']['Unit']
                    total_cost += amount
                    if amount > 0.01:  # Only include services with meaningful cost
                        by_service[service_name] = amount
            
            # Get cost by project tag
            by_project = self._fetch_costs_by_project(start_of_month, end_date)
            
            # Get forecast (optional, may fail for new accounts)
            forecast = self._fetch_forecast()
            
            return CostSummary(
                total_cost=round(total_cost, 2),
                currency=currency,
                period_start=start_of_month,
                period_end=end_date,
                last_updated=datetime.utcnow().isoformat() + "Z",
                forecast_end_of_month=forecast,
                by_service=by_service,
                by_project=by_project
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'AccessDeniedException':
                logger.error("Access denied to Cost Explorer. Ensure you have ce:GetCostAndUsage permission.")
            else:
                logger.error(f"Cost Explorer API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching costs: {e}")
            return None
    
    def _fetch_costs_by_project(self, start_date: str, end_date: str) -> Dict[str, float]:
        """Fetch costs grouped by pockitect:project tag."""
        try:
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'TAG', 'Key': 'pockitect:project'}
                ]
            )
            
            by_project = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    tag_value = group['Keys'][0]
                    # Tag format is "pockitect:project$value" or "pockitect:project$" for untagged
                    if '$' in tag_value:
                        project_name = tag_value.split('$', 1)[1]
                        if project_name:  # Skip untagged
                            amount = float(group['Metrics']['UnblendedCost']['Amount'])
                            if amount > 0.01:
                                by_project[project_name] = round(amount, 2)
            
            return by_project
            
        except Exception as e:
            logger.warning(f"Failed to fetch costs by project: {e}")
            return {}
    
    def _fetch_forecast(self) -> Optional[float]:
        """Fetch end-of-month cost forecast."""
        try:
            today = datetime.utcnow()
            
            # Forecast needs at least a few days of data
            if today.day < 3:
                return None
            
            # End of current month
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1)
            
            start_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
            end_date = end_of_month.strftime('%Y-%m-%d')
            
            response = self.cost_explorer.get_cost_forecast(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Metric='UNBLENDED_COST',
                Granularity='MONTHLY'
            )
            
            forecast = float(response.get('Total', {}).get('Amount', 0))
            
            # Add current spend to forecast for total
            summary = self._get_cached_summary()
            if summary:
                return round(summary.total_cost + forecast, 2)
            
            return round(forecast, 2)
            
        except ClientError as e:
            # Forecast often fails for accounts with little history
            logger.debug(f"Cost forecast not available: {e}")
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch forecast: {e}")
            return None
    
    def _get_cached_summary(self) -> Optional[CostSummary]:
        """Get cached cost summary from Redis."""
        try:
            conn = self.redis.get_connection()
            cached = conn.get(KEY_COST_SUMMARY)
            if cached:
                data = json.loads(cached)
                return CostSummary(**data)
        except Exception as e:
            logger.debug(f"Cache read failed: {e}")
        return None
    
    def _cache_summary(self, summary: CostSummary):
        """Cache cost summary to Redis."""
        try:
            conn = self.redis.get_connection()
            conn.setex(KEY_COST_SUMMARY, COST_CACHE_TTL_SECONDS, json.dumps(asdict(summary)))
            conn.set(KEY_COST_LAST_REFRESH, summary.last_updated)
            logger.debug("Cost summary cached")
        except Exception as e:
            logger.warning(f"Failed to cache cost summary: {e}")
    
    def format_budget_status_for_ai(self, status: Optional[BudgetStatus] = None) -> str:
        """
        Format budget status as a human-readable string for AI context.
        
        Returns:
            Formatted string suitable for AI agent context
        """
        if status is None:
            status = self.get_budget_status()
        
        if status is None:
            return "Cost data unavailable. AWS Cost Explorer access may be required."
        
        lines = [
            f"Monthly Budget: ${status.monthly_budget:.2f} {status.currency}",
            f"Current Spend: ${status.current_spend:.2f} ({status.percentage_used:.1f}% of budget)",
            f"Remaining: ${status.remaining:.2f}",
            f"Days Left in Month: {status.days_remaining}",
        ]
        
        if status.forecast_end_of_month:
            lines.append(f"Forecast End of Month: ${status.forecast_end_of_month:.2f} ({status.forecast_percentage:.1f}% of budget)")
        
        if status.is_over_budget:
            lines.append("⚠️ WARNING: Over budget!")
        elif status.is_forecast_over_budget:
            lines.append("⚠️ WARNING: Forecast to exceed budget!")
        elif status.percentage_used > 80:
            lines.append("⚠️ CAUTION: Approaching budget limit")
        else:
            lines.append("✅ Budget on track")
        
        return "\n".join(lines)
    
    def format_cost_breakdown_for_ai(self, summary: Optional[CostSummary] = None) -> str:
        """
        Format cost breakdown for AI context.
        
        Returns:
            Formatted string with service and project breakdown
        """
        if summary is None:
            summary = self.get_cost_summary()
        
        if summary is None:
            return "Cost breakdown unavailable."
        
        lines = [f"Cost breakdown for {summary.period_start} to {summary.period_end}:"]
        
        # Top services by cost
        if summary.by_service:
            lines.append("\nBy AWS Service:")
            sorted_services = sorted(summary.by_service.items(), key=lambda x: x[1], reverse=True)
            for service, amount in sorted_services[:5]:  # Top 5
                lines.append(f"  - {service}: ${amount:.2f}")
        
        # By project
        if summary.by_project:
            lines.append("\nBy Project (pockitect:project tag):")
            sorted_projects = sorted(summary.by_project.items(), key=lambda x: x[1], reverse=True)
            for project, amount in sorted_projects:
                lines.append(f"  - {project}: ${amount:.2f}")
        
        return "\n".join(lines)


# Singleton instance
_cost_service: Optional[CostService] = None


def get_cost_service(default_budget: float = 100.0) -> CostService:
    """Get or create the singleton CostService instance."""
    global _cost_service
    if _cost_service is None:
        _cost_service = CostService(default_budget=default_budget)
    return _cost_service
