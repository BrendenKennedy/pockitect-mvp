AWS Well-Architected (Summary)

Operational Excellence
- Automate changes and operations; use infrastructure as code.
- Observe system health with metrics/logs/alerts.
- Run game days and post-incident reviews.

Security
- Least privilege IAM, MFA, and short-lived credentials.
- Encrypt data at rest and in transit.
- Log and monitor all access; centralize audit logs.

Reliability
- Use multi-AZ where possible; avoid single points of failure.
- Automate recovery and replace instead of repair.
- Design for throttling and service limits.

Performance Efficiency
- Choose right instance types and sizes; avoid over-provisioning.
- Use managed services when they reduce operational load.
- Cache where appropriate and use autoscaling.

Cost Optimization
- Match resources to demand; turn off idle resources.
- Use reserved/savings plans for predictable workloads.
- Monitor costs and set budgets/alerts.
