import os
from functools import wraps

import pandas as pd
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename

from models import db, User, Request as ReqModel, STAGE_ORDER, STAGE_NORMAL, DEPT_DELAY_RATE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "delayguard.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("DELAYGUARD_SECRET", "hackathon-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB upload cap

db.init_app(app)

REQUIRED_EXCEL_COLUMNS = [
    "request_id", "department", "service", "importance", "stage",
    "days_remaining", "sla_window", "days_in_stage", "previous_delays", "officer_email",
]


# ---------------- auth helpers ----------------
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*a, **kw)
    return wrapper


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


# ---------------- frontend ----------------
@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


# ---------------- auth routes ----------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user.id
    session["role"] = user.role
    return jsonify({"user": user.to_dict()})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
def me():
    user = current_user()
    if not user:
        return jsonify({"user": None}), 200
    return jsonify({"user": user.to_dict()})


# ---------------- requests routes ----------------
@app.route("/api/requests", methods=["GET"])
@login_required
def get_requests():
    user = current_user()
    query = ReqModel.query
    if user.role == "employee":
        query = query.filter_by(officer_id=user.id)
    items = [r.enriched() for r in query.all()]
    return jsonify(items)


@app.route("/api/requests/<request_id>", methods=["PATCH"])
@login_required
def update_request(request_id):
    """Employees update stage/status/remarks on their own requests.
    Admins can update any request and reassign officers."""
    user = current_user()
    r = ReqModel.query.filter_by(request_id=request_id).first()
    if not r:
        return jsonify({"error": "Not found"}), 404
    if user.role == "employee" and r.officer_id != user.id:
        return jsonify({"error": "Not your request"}), 403

    data = request.get_json(silent=True) or {}
    if "stage" in data and data["stage"] in STAGE_ORDER:
        r.stage = data["stage"]
        r.days_in_stage = 0
    if "status" in data and data["status"] in ("Open", "Completed"):
        r.status = data["status"]
    if "remarks" in data:
        r.remarks = data["remarks"]
    if user.role == "admin" and "officer_email" in data:
        officer = User.query.filter_by(email=data["officer_email"].strip().lower()).first()
        if officer:
            r.officer_id = officer.id

    db.session.commit()
    return jsonify(r.enriched())


@app.route("/api/departments", methods=["GET"])
@login_required
def departments():
    depts = sorted({r.department for r in ReqModel.query.all()})
    return jsonify(depts)


@app.route("/api/bottlenecks", methods=["GET"])
@admin_required
def bottlenecks():
    items = [r.enriched() for r in ReqModel.query.all()]

    stage_agg = {s: {"total": 0, "count": 0} for s in STAGE_ORDER}
    for r in items:
        stage_agg[r["stage"]]["total"] += r["daysInStage"]
        stage_agg[r["stage"]]["count"] += 1

    stage_rows = []
    for s in STAGE_ORDER:
        agg = stage_agg[s]
        avg = agg["total"] / agg["count"] if agg["count"] else 0
        normal = STAGE_NORMAL[s]
        ratio = avg / normal if normal else 0
        stage_rows.append({"stage": s, "avg": round(avg, 1), "normal": normal, "ratio": ratio})
    stage_rows.sort(key=lambda x: -x["ratio"])

    dept_agg = {}
    for r in items:
        d = r["department"]
        dept_agg.setdefault(d, {"count": 0, "riskTotal": 0})
        dept_agg[d]["count"] += 1
        dept_agg[d]["riskTotal"] += r["riskScore"]

    dept_rows = []
    for d, agg in dept_agg.items():
        avg_risk = round(agg["riskTotal"] / agg["count"]) if agg["count"] else 0
        dept_rows.append({
            "dept": d, "count": agg["count"], "avgRisk": avg_risk,
            "delayRate": DEPT_DELAY_RATE.get(d, 0),
        })
    dept_rows.sort(key=lambda x: -x["avgRisk"])

    return jsonify({"stages": stage_rows, "departments": dept_rows})


# ---------------- Excel import (admin only) ----------------
@app.route("/api/upload", methods=["POST"])
@admin_required
def upload_excel():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    filename = secure_filename(file.filename or "")
    if not filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "Please upload a .xlsx or .xls file"}), 400

    try:
        df = pd.read_excel(file)
    except Exception as e:
        return jsonify({"error": f"Could not read Excel file: {e}"}), 400

    missing = [c for c in REQUIRED_EXCEL_COLUMNS if c not in df.columns]
    if missing:
        return jsonify({"error": f"Missing required columns: {', '.join(missing)}"}), 400

    created, updated, errors = 0, 0, []
    for i, row in df.iterrows():
        try:
            rid = str(row["request_id"]).strip()
            officer = User.query.filter_by(email=str(row.get("officer_email", "")).strip().lower()).first()

            r = ReqModel.query.filter_by(request_id=rid).first()
            if not r:
                r = ReqModel(request_id=rid)
                db.session.add(r)
                created += 1
            else:
                updated += 1

            r.department = str(row["department"]).strip()
            r.service = str(row["service"]).strip()
            r.importance = str(row["importance"]).strip()
            r.stage = str(row["stage"]).strip()
            r.days_remaining = int(row["days_remaining"])
            r.sla_window = int(row["sla_window"])
            r.days_in_stage = int(row["days_in_stage"])
            r.previous_delays = int(row["previous_delays"])
            r.officer_id = officer.id if officer else r.officer_id
        except Exception as e:
            errors.append(f"Row {i + 2}: {e}")

    db.session.commit()
    return jsonify({"created": created, "updated": updated, "errors": errors})


@app.route("/api/upload/template", methods=["GET"])
@admin_required
def download_template():
    return send_from_directory(BASE_DIR, "requests_template.xlsx", as_attachment=True)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # host=0.0.0.0 so other laptops on the same wifi/hotspot can reach this one
    app.run(host="0.0.0.0", port=5000, debug=True)
