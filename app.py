import csv
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path

from flask import (Flask, Response, flash, redirect, render_template, request,
                   url_for)

app = Flask(__name__)
app.secret_key = "pericare-doo-command-center"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pericare.db"


STATUS_COLORS = {
    "done": "success",
    "blocked": "warning",
    "pending": "secondary",
    "in_progress": "info",
    "overdue": "danger",
}

DEFAULT_OWNERS = [
    "Winston",
    "Armando",
    "Paulande",
    "Claudia",
    "Kelly",
    "Yasmin",
    "IT",
]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_db_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                day_of_week TEXT NOT NULL,
                time_block TEXT NOT NULL,
                category TEXT,
                owner TEXT NOT NULL,
                due_time TEXT NOT NULL,
                description TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
        )
        conn.commit()
    seed_tasks()


def seed_tasks():
    with closing(get_db_connection()) as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count > 0:
            return

        am_tasks = [
            {
                "title": "Case flow",
                "time_block": "AM Command Check",
                "category": "Operations",
                "owner": "Winston",
                "description": "Review inflow/outflow and bottlenecks.",
            },
            {
                "title": "Escalations & safety",
                "time_block": "AM Command Check",
                "category": "Risk",
                "owner": "Armando",
                "description": "Scan for safety flags and escalations.",
            },
            {
                "title": "Partner/staff readiness",
                "time_block": "AM Command Check",
                "category": "Readiness",
                "owner": "Kelly",
                "description": "Confirm teams and partners are staffed and aligned.",
            },
            {
                "title": "Cost/revenue scan",
                "time_block": "AM Command Check",
                "category": "Finance",
                "owner": "Claudia",
                "description": "Check expense trends and revenue pacing.",
            },
        ]

        pm_tasks = [
            {
                "title": "Completion checks",
                "time_block": "PM Closeout",
                "category": "Quality",
                "owner": "Paulande",
                "description": "Validate daily deliverables are complete.",
            },
            {
                "title": "Documentation queue",
                "time_block": "PM Closeout",
                "category": "Documentation",
                "owner": "Yasmin",
                "description": "Confirm notes and records are up to date.",
            },
            {
                "title": "Next steps assigned",
                "time_block": "PM Closeout",
                "category": "Planning",
                "owner": "Winston",
                "description": "Ensure owners and timelines are set for tomorrow.",
            },
        ]

        weekly_specifics = {
            "Monday": [
                ("Weekly reset", "Set baselines and clean queues.", "Winston"),
                ("KPI trend scan", "Review directional signals.", "Kelly"),
                ("Priorities", "Lock this week's priorities.", "Winston"),
            ],
            "Tuesday": [
                ("Partner SLA enforcement", "Check SLAs and send nudges.", "Armando"),
                (
                    "Documentation/billing verification",
                    "Audit records against billing.",
                    "Claudia",
                ),
            ],
            "Wednesday": [
                ("Clinical/AI alignment", "Sync on AI + clinical workflows.", "Paulande"),
                ("IT translation", "Ensure IT tickets match needs.", "IT"),
            ],
            "Thursday": [
                ("Cost/quality/risk deep dive", "Run weekly drill down.", "Claudia"),
            ],
            "Friday": [
                ("Weekly OP review", "Ops review with actions.", "Winston"),
                ("Decision log", "Capture decisions + rationale.", "Kelly"),
                ("Next week readiness", "Prep staffing + priorities.", "Yasmin"),
            ],
        }

        due_times = {
            "AM Command Check": "10:00",
            "PM Closeout": "17:00",
        }

        tasks_to_insert = []
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            for task in am_tasks + pm_tasks:
                tasks_to_insert.append(
                    (
                        task["title"],
                        day,
                        task["time_block"],
                        task["category"],
                        task["owner"],
                        due_times[task["time_block"]],
                        task["description"],
                    )
                )
            for title, description, owner in weekly_specifics.get(day, []):
                tasks_to_insert.append(
                    (
                        title,
                        day,
                        "Weekly Focus",
                        "Strategy",
                        owner,
                        "12:00",
                        description,
                    )
                )

        conn.executemany(
            """
            INSERT INTO tasks (title, day_of_week, time_block, category, owner, due_time, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            tasks_to_insert,
        )
        conn.commit()


def fetch_tasks(day_of_week: str, target_date: date, owner_filter: str | None = None):
    with closing(get_db_connection()) as conn:
        params = [day_of_week]
        owner_clause = ""
        if owner_filter and owner_filter != "All":
            owner_clause = " AND owner = ?"
            params.append(owner_filter)
        tasks = conn.execute(
            f"SELECT * FROM tasks WHERE day_of_week = ?{owner_clause} ORDER BY time_block, id",
            params,
        ).fetchall()

        logs = conn.execute(
            "SELECT * FROM task_logs WHERE date = ?",
            (target_date.isoformat(),),
        ).fetchall()
        log_map = {(log["task_id"], log["date"]): log for log in logs}

        detailed_tasks = []
        now = datetime.now()
        for task in tasks:
            log = log_map.get((task["id"], target_date.isoformat()))
            status = log["status"] if log else "pending"
            notes = log["notes"] if log else ""
            overdue = False

            try:
                due_dt = datetime.strptime(task["due_time"], "%H:%M").time()
            except ValueError:
                due_dt = datetime.strptime("17:00", "%H:%M").time()

            if status != "done":
                task_datetime = datetime.combine(target_date, due_dt)
                if task_datetime < now:
                    overdue = True

            detailed_tasks.append(
                {
                    "data": task,
                    "status": "overdue" if overdue else status,
                    "notes": notes,
                    "overdue": overdue,
                }
            )
        return detailed_tasks


def upsert_log(task_id: int, target_date: date, status: str, notes: str):
    with closing(get_db_connection()) as conn:
        existing = conn.execute(
            "SELECT id FROM task_logs WHERE task_id = ? AND date = ?",
            (task_id, target_date.isoformat()),
        ).fetchone()
        now_str = datetime.utcnow().isoformat()
        if existing:
            conn.execute(
                "UPDATE task_logs SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                (status, notes, now_str, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO task_logs (task_id, date, status, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, target_date.isoformat(), status, notes, now_str),
            )
        conn.commit()


def parse_date(date_str: str | None):
    if not date_str:
        return date.today()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


@app.before_request
def ensure_db():
    if not DB_PATH.exists():
        init_db()


@app.route("/")
def overview():
    today = date.today()
    day_name = today.strftime("%A")
    owner_filter = request.args.get("owner", "All")
    tasks = fetch_tasks(day_name, today, owner_filter)

    overdue_tasks = [t for t in tasks if t["overdue"]]
    red_flags = {
        "cases": request.args.get("cases", ""),
        "documentation": request.args.get("documentation", ""),
        "sla": request.args.get("sla", ""),
    }

    return render_template(
        "overview.html",
        tasks=tasks,
        owner_filter=owner_filter,
        owners=["All"] + DEFAULT_OWNERS,
        day_name=day_name,
        today=today,
        overdue_tasks=overdue_tasks,
        red_flags=red_flags,
    )


@app.route("/day/<day>", methods=["GET", "POST"])
def day_view(day):
    target_date = parse_date(request.args.get("date"))
    owner_filter = request.args.get("owner", "All")
    if request.method == "POST":
        for key, value in request.form.items():
            if key.startswith("status_"):
                task_id = int(key.split("_")[1])
                status = value
                notes = request.form.get(f"notes_{task_id}", "").strip()
                done_checked = request.form.get(f"done_{task_id}") == "on"
                final_status = "done" if done_checked else status
                upsert_log(task_id, target_date, final_status, notes)
        flash("Updates saved for " + target_date.isoformat())
        return redirect(url_for("day_view", day=day, date=target_date.isoformat(), owner=owner_filter))

    tasks = fetch_tasks(day, target_date, owner_filter)
    return render_template(
        "day.html",
        day=day,
        tasks=tasks,
        target_date=target_date,
        owners=["All"] + DEFAULT_OWNERS,
        owner_filter=owner_filter,
    )


@app.route("/weekly")
def weekly_review():
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    with closing(get_db_connection()) as conn:
        summary = conn.execute(
            """
            SELECT t.day_of_week, tl.date, t.title, tl.status, tl.notes, t.owner, t.time_block
            FROM task_logs tl
            JOIN tasks t ON tl.task_id = t.id
            WHERE tl.date BETWEEN ? AND ?
            ORDER BY tl.date DESC, t.day_of_week, t.time_block, t.id
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

        stats = conn.execute(
            """
            SELECT status, COUNT(*) as count FROM task_logs
            WHERE date BETWEEN ? AND ?
            GROUP BY status
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    status_counts = {row["status"]: row["count"] for row in stats}
    return render_template(
        "weekly.html",
        summary=summary,
        start_date=start_date,
        end_date=end_date,
        status_counts=status_counts,
    )


@app.route("/export")
def export_csv():
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            """
            SELECT tl.date, t.day_of_week, t.time_block, t.title, t.owner, tl.status, tl.notes
            FROM task_logs tl
            JOIN tasks t ON tl.task_id = t.id
            WHERE tl.date BETWEEN ? AND ?
            ORDER BY tl.date, t.day_of_week, t.time_block, t.id
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Day", "Time Block", "Task", "Owner", "Status", "Notes"])
    for row in rows:
        writer.writerow([row["date"], row["day_of_week"], row["time_block"], row["title"], row["owner"], row["status"], row["notes"]])

    output.seek(0)
    csv_data = output.read()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=weekly_review.csv"},
    )


@app.context_processor
def inject_helpers():
    return {
        "status_colors": STATUS_COLORS,
    }


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
