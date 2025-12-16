# PeriCare DOO Command Center

Executive-style daily command center for Winston Guevara (Director of Operations) to track weekday tasks across AM Command Check, Weekly Focus, and PM Closeout.

## Features
- Tabs for Overview, weekday checklists (Monday–Friday), and Weekly Review.
- Daily tasks broken down by AM/PM blocks with owner filters, status dropdowns, checkboxes, and notes.
- Overdue detection based on due time and completion state plus red/yellow/green visual cues.
- Red Flags panel (manual inputs for cases &gt;24h without next step, documentation lag &gt;48h, SLA breaches).
- Weekly summary view with CSV export of the last 7 days of task logs.
- SQLite backing store with seeded task templates for AM Command Check, PM Closeout, and day-specific focuses.

## Getting Started
1. **Install dependencies** (preferably in a virtualenv):
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the server** (initializes the SQLite database with seed data on first start):
   ```bash
   python app.py
   ```
3. Open the dashboard at http://localhost:5000.

The SQLite database (`pericare.db`) is created in the project root. Seeded tasks include AM/PM checklists and weekday-specific work such as SLA enforcement, KPI scans, and readiness checks.

## Data Model
- **tasks**: `id`, `title`, `day_of_week`, `time_block`, `category`, `owner`, `due_time`, `description`
- **task_logs**: `id`, `task_id`, `date`, `status`, `notes`, `updated_at`

## CSV Export
Use the **Export CSV** button on the Weekly Review tab to download the last 7 days of task activity for reporting.
