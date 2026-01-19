# Pockitect MVP – Development Log

This file tracks daily progress, technical decisions, and notes during development.

---

## 2026-01-16 – Project Initialization

### Summary
- Initialized project structure based on the refined architecture plan
- Created documentation files (architecture plan, devlog, progress tracker)
- Set up directory scaffolding (`projects/`, `training/`, `src/`, `tests/`)
- Created `requirements.txt` with core dependencies

### Decisions Made
- **UI Framework**: Plain PyQt6 widgets (simpler, faster to build pure Python MVP)
- **Storage**: JSON files on disk in `./projects/` directory
- **No external database** for MVP phase

### Notes
- Project slug will be auto-generated from project name
- Deployment order is enforced in backend, not wizard UI order
- Private keys stored temporarily or in `~/.ssh/`, never persisted in project JSON

### Implementation Complete
- `src/storage.py` - Full filesystem storage module with:
  - `init_storage()` - Ensures directories exist
  - `slugify()` - Converts project names to filesystem-safe slugs
  - `save_project()` - Writes JSON to `projects/<slug>.json`
  - `load_project()` - Reads JSON from disk
  - `list_projects()` - Scans projects directory with status aggregation
  - `delete_project()` - Removes project files
  - `create_empty_blueprint()` - Creates canonical project structure
- `tests/test_storage.py` - Comprehensive test suite (all 7 tests passing)

- `src/wizard/` - Complete PyQt6 wizard implementation:
  - `pages/project_basics.py` - Project name, description, region, owner
  - `pages/compute.py` - Instance type, AMI, user data templates
  - `pages/network.py` - VPC, subnet, firewall rules with presets
  - `pages/data.py` - Optional RDS and S3 configuration
  - `pages/security.py` - SSH key, certificate, IAM role settings
  - `pages/review.py` - Summary display with JSON preview
  - `wizard.py` - Main wizard orchestrator with data flow between pages

- `src/main.py` - Main application entry point:
  - Tab-based UI (Projects + AI Chat placeholder)
  - Project list with create/open/delete actions
  - Wizard integration for creating new projects
  - Status bar and modern styling

- Virtual environment created with PyQt6 and boto3 installed

---

## 2026-01-16 – AWS Integration

### Summary
- Implemented full AWS integration layer using boto3
- Created quota pre-fetch service for filtering available resources
- Built resource manager with create/read/delete functions
- Developed deployment orchestrator with ordered execution
- Added local credential and key management

### Implementation Details

**Quota Pre-fetch Service (`src/aws/quota.py`)**:
- Fetches regions, instance types, AMIs, key pairs, VPCs
- Background refresh with 1-hour cache TTL
- Thread-safe with lazy loading per region

**Resource Manager (`src/aws/resources.py`)**:
- VPC: create, get default
- Subnet: create with public IP mapping
- Security Group: create with rules
- Key Pair: create (saves to ~/.ssh/), delete
- IAM Role: create with S3/RDS policies, instance profile
- EC2: launch, get status, terminate
- RDS: create, get status, delete
- S3: create bucket (with public access block), delete

**Deployment Orchestrator (`src/aws/deploy.py`)**:
- Follows execution order from architecture plan
- Step-by-step execution with status tracking
- Async deployment with progress callbacks
- StatusPoller for background updates
- Updates blueprint with resource IDs

**Credential Management (`src/aws/credentials.py`)**:
- Saves keys to ~/.pockitect/keys/ and ~/.ssh/
- Secure file permissions (600)
- Certificate storage support
- SSH config entry generation

### Architecture
```
DeploymentOrchestrator
    ├── Step 1: VPC/Subnet
    ├── Step 2: Security Group
    ├── Step 3: Key Pair
    ├── Step 4: IAM Role
    ├── Step 5: EC2 Instance
    ├── Step 6: RDS (optional)
    ├── Step 7: S3 (optional)
    └── Step 8: Verify
            ↓
StatusPoller (background)
    └── Updates blueprint every 30s
```

---

## 2026-01-16 – MVP Complete

### Summary
- All 8 implementation steps complete
- Full test suite (44 tests) passing
- 5 training data pairs created
- Filesystem watcher integrated for auto-refresh

### Final Implementation

**Tests Added**:
- `test_aws_quota.py` - 8 tests for quota service
- `test_aws_resources.py` - 10 tests for resource manager
- `test_aws_deploy.py` - 11 tests for orchestrator
- `test_aws_credentials.py` - 6 tests for key management
- `run_all_tests.py` - Test runner for full suite

**Deployment Dialog (`src/wizard/deploy_dialog.py`)**:
- Real-time progress with step-by-step status
- Visual indicators (✅❌🔄⏳)
- Log output with timestamps
- Cancel support with confirmation

**Filesystem Watcher (`src/watcher.py`)**:
- Polling-based change detection (2s interval)
- Auto-refresh of project list
- Background status refresher (optional)

**Training Data (`training/`)**:
- 001-simple-blog: Basic blog with PostgreSQL
- 002-static-website: Static site with S3
- 003-api-server: Node.js API with MySQL
- 004-docker-host: Container host with custom VPC
- 005-full-stack: Complete app with everything

### Test Results
```
test_storage.py:        7 tests  ✓
test_aws_quota.py:      8 tests  ✓
test_aws_resources.py: 10 tests  ✓
test_aws_deploy.py:    11 tests  ✓
test_aws_credentials.py: 6 tests ✓
─────────────────────────────────
Total:                 44 tests  🎉
```

---

## 2026-01-16 – UI Improvements & PySide6 Migration

### Summary
- Migrated from PyQt6 to PySide6 (official Qt for Python binding)
- Implemented comprehensive dark mode theme
- Fixed segfault issue on WSL2
- Enhanced network rules UI with manual row creation

### UI Framework Migration

**PyQt6 → PySide6**:
- PySide6 is the official Qt for Python from The Qt Company
- Better long-term support and licensing (LGPL)
- API nearly identical, main changes:
  - `pyqtSignal` → `Signal`
  - Import paths: `from PyQt6.` → `from PySide6.`

**Files Updated**:
- `src/main.py`
- `src/watcher.py`
- `src/wizard/wizard.py`
- `src/wizard/base.py`
- `src/wizard/deploy_dialog.py`
- `src/wizard/pages/*.py` (all 6 pages)
- `requirements.txt`
- `README.md`

### Dark Mode Theme

**New: `src/styles.py`**
- Deep blue background: `#1a1a2e`
- Accent color: `#e94560` (coral/pink)
- Secondary blue: `#0f3460`, `#16213e`
- Comprehensive styling for all Qt widgets:
  - Buttons, inputs, combo boxes
  - Tables, lists, scroll areas
  - Progress bars, check boxes, radio buttons
  - Tabs, group boxes, tooltips

### WSL2 Compatibility Fix
- Added auto-detection for WSL environment
- Default to Wayland platform on WSL2 (via WSLg)
- Created `run.sh` launcher script for easy startup
- Fallback handling for missing xcb-cursor library

### Network Rules Enhancement
- Added dedicated "Add Custom Rule" section
- Organized fields: Port/Protocol on row 1, CIDR/Description on row 2
- Added ICMP protocol option
- "Clear All" button to remove all rules
- Enter key support in text fields for quick rule addition
- Improved delete button styling

---

## 2026-01-16 – AWS Authentication Login Gate

### Summary
- Implemented secure AWS credential login dialog
- Authentication gates access to the entire application
- Added IAM policy display with one-click copy to clipboard
- Integrated system keyring for encrypted credential storage
- Added real-time permission validation via boto3
- Auto-login support for returning users

### Security Implementation

**Credential Storage**:
- Uses `keyring` library for OS-native secure storage
- Service name: `PockitectApp`
- Stores Access Key ID and Secret Access Key separately
- Never stores credentials in plaintext files or environment variables

**Permission Validation**:
- Background thread validation (non-blocking UI)
- Tests: `sts:GetCallerIdentity`, `s3:ListAllMyBuckets`, `ec2:DescribeInstances`
- Clear error messages for missing permissions
- Guidance to update IAM policy on failure

### New Files

**`src/auth_dialog.py`**:
- `AWSLoginDialog(QDialog)` - Modal login dialog that gates app access
- `CredentialValidationWorker(QThread)` - Background validation
- `REQUIRED_IAM_POLICY` - Least-privilege policy JSON
- `get_aws_credentials()` - Retrieve stored credentials
- `clear_aws_credentials()` - Remove stored credentials
- Features:
  - Shows on app startup before main window
  - Auto-login with stored valid credentials
  - Policy JSON display with syntax highlighting
  - Copy to clipboard (Qt clipboard + pyperclip fallback)
  - Access Key ID input (visible)
  - Secret Access Key input (password mode with toggle)
  - "Login" button with visual feedback
  - "Quit" button with confirmation
  - Cannot be dismissed without authentication
  - Status messages (info/success/error)

**`architecture.md`**:
- High-level architecture documentation
- Authentication flow diagram
- Security model description
- Full IAM policy JSON
- Class structure overview
- Error handling strategy

### Dependencies Added
- `keyring>=24.0.0` - Secure credential storage
- `pyperclip>=1.8.0` - Clipboard fallback

### Application Flow
1. App starts → Login dialog appears
2. If credentials in keyring → auto-validate silently
3. If valid → proceed to main app
4. If invalid/missing → user must enter credentials
5. User clicks "Login" → validate → save to keyring
6. Success → main window shown
7. Quit button → confirm and exit app

### Technical Decisions
- **QThread for validation**: Prevents UI freeze during AWS API calls
- **Keyring service naming**: `PockitectApp` (consistent, app-specific)
- **Policy completeness**: Includes all actions used by deployment orchestrator
- **Error granularity**: Specific permission failures shown individually
- **Modal dialog**: Cannot be bypassed - ensures all app usage is authenticated

---
