Cost Optimization Notes

- Prefer smaller instance types by default; scale up only when needed.
- Use autoscaling for variable load instead of fixed large instances.
- Stop non-production resources outside business hours.
- Use S3 lifecycle policies to move cold data to cheaper storage.
- Use RDS storage autoscaling and right-size DB instance classes.
- Track costs by project tag and set monthly budgets.
