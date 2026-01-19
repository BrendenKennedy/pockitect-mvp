# Pockitect MVP – Progress Tracker

This file tracks the completion status of implementation steps from the architecture plan.

## Implementation Steps

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 1 | Filesystem project store (`./projects/`, `./training/`) | Complete | `src/storage.py` |
| 2 | Wizard skeleton (collect all fields → in-memory dict) | Complete | `src/wizard/` |
| 3 | Quota pre-fetch service (startup task) | Complete | `src/aws/quota.py` |
| 4 | Boto3 wrapper – create/read functions per resource type | Complete | `src/aws/resources.py` |
| 5 | Deployment orchestrator (ordered sequence + status update loop) | Complete | `src/aws/deploy.py` |
| 6 | Key/cert local save logic (~/.ssh/ or app-specific folder) | Complete | `src/aws/credentials.py` |
| 7 | UI refresh from filesystem watcher | Complete | `src/watcher.py` |
| 8 | First 5–10 manual prompt → JSON pairs (bootstrap training set) | Complete | `training/` (5 pairs) |

## Milestones

- [x] **M1**: Project store functional (save/load/list projects)
- [x] **M2**: Wizard UI complete (all 6 screens)
- [x] **M3**: Single resource deployment working (EC2 only)
- [x] **M4**: Full deployment pipeline (VPC → EC2 → RDS → S3)
- [x] **M5**: Status polling and UI refresh
- [x] **M6**: First training data pairs created

## Additional Features

### AWS Authentication Login Gate
- [x] Policy display with JSON formatting
- [x] Copy policy to clipboard button
- [x] Access Key ID input field
- [x] Secret Access Key input (password mode with show toggle)
- [x] Keyring integration for secure storage
- [x] Permission validation via boto3
- [x] Background thread validation (non-blocking)
- [x] Clear error messages for permission issues
- [x] Modal login dialog gates app access
- [x] Auto-login with stored valid credentials
- [x] Quit button with confirmation
- [x] Cannot dismiss without authentication

### Documentation
- [x] `architecture.md` – Security model and auth flow
- [x] `DEVLOG.md` – Implementation notes
- [x] `PROGRESS.md` – Feature checklist

---

*Last updated: 2026-01-16*
