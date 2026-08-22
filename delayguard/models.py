from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

STAGE_ORDER = ["Intake", "Verification", "Document Review", "Approval", "Completion"]
STAGE_NORMAL = {"Intake": 1, "Verification": 2, "Document Review": 2, "Approval": 2, "Completion": 1}
STAGE_DELAY_RATE = {"Intake": 0.05, "Verification": 0.18, "Document Review": 0.24, "Approval": 0.46, "Completion": 0.03}
DEPT_DELAY_RATE = {
    "Revenue": 0.42, "Transport": 0.19, "Municipal Services": 0.27,
    "Registration": 0.35, "Welfare": 0.15
}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'employee'

    requests = db.relationship("Request", backref="officer_ref", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Request(db.Model):
    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(20), unique=True, nullable=False)  # e.g. R101
    department = db.Column(db.String(80), nullable=False)
    service = db.Column(db.String(160), nullable=False)
    importance = db.Column(db.String(20), nullable=False, default="Normal")  # Critical/Normal/Low
    stage = db.Column(db.String(40), nullable=False, default="Intake")
    days_remaining = db.Column(db.Integer, nullable=False, default=0)
    sla_window = db.Column(db.Integer, nullable=False, default=10)
    days_in_stage = db.Column(db.Integer, nullable=False, default=0)
    previous_delays = db.Column(db.Integer, nullable=False, default=0)
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Open")  # Open/Completed
    officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def enriched(self):
        """Port of the frontend's risk engine (deadline urgency, stage delay,
        historical delay, department risk -> riskScore/priorityScore/category)."""
        normal = STAGE_NORMAL.get(self.stage, 2)
        stage_delay_rate = STAGE_DELAY_RATE.get(self.stage, 0.1)
        dept_rate = DEPT_DELAY_RATE.get(self.department, 0.1)

        deadline_urgency = 100 if self.days_remaining <= 0 else max(
            0, 100 - (self.days_remaining / self.sla_window) * 100
        )
        stage_delay = min(100, (self.days_in_stage / normal) * 50)
        historical_delay = stage_delay_rate * 100
        department_risk = dept_rate * 100

        risk_score = round(
            deadline_urgency * 0.40 + stage_delay * 0.30 +
            historical_delay * 0.20 + department_risk * 0.10
        )
        risk_score = max(0, min(100, risk_score))

        weight = 1.5 if self.importance == "Critical" else (0.7 if self.importance == "Low" else 1.0)
        priority_score = round(risk_score * weight)

        category = "Low" if risk_score <= 30 else ("Medium" if risk_score <= 60 else "High")
        if self.days_remaining <= 0:
            category = "Breached"

        reasons = []
        if self.days_remaining <= 0:
            reasons.append("The SLA deadline has already passed.")
        elif self.days_remaining <= 1:
            reasons.append(f"Only {self.days_remaining} day remains before the SLA deadline.")
        elif self.days_remaining <= 3:
            reasons.append(f"Just {self.days_remaining} days remain before the SLA deadline.")
        if self.days_in_stage > normal:
            reasons.append(
                f"Stuck in {self.stage} for {self.days_in_stage} day"
                f"{'s' if self.days_in_stage > 1 else ''} — typical duration is {normal} day"
                f"{'s' if normal > 1 else ''}."
            )
        if stage_delay_rate >= 0.3:
            reasons.append(f"{self.stage} has a {round(stage_delay_rate*100)}% historical delay rate across all requests.")
        if dept_rate >= 0.3:
            reasons.append(f"{self.department} shows a {round(dept_rate*100)}% historical SLA delay rate.")
        if self.previous_delays >= 2:
            reasons.append(f"This request has already been delayed {self.previous_delays} times in earlier stages.")
        if not reasons:
            reasons.append("Progressing normally within the expected timeline for this stage.")

        if self.days_remaining <= 1:
            action, action_icon = "Escalate immediately", "🚨"
        elif self.days_in_stage > normal * 1.5:
            action, action_icon = "Reassign to an available officer", "👤"
        elif dept_rate >= 0.3:
            action, action_icon = "Add resources to this department's queue", "⚡"
        elif self.importance == "Critical":
            action, action_icon = "Mark as priority and expedite", "⭐"
        else:
            action, action_icon = "Monitor — currently on track", "🟢"

        officer_name = self.officer_ref.name if self.officer_ref else "Unassigned"

        return {
            "id": self.request_id,
            "department": self.department,
            "service": self.service,
            "importance": self.importance,
            "stage": self.stage,
            "daysRemaining": self.days_remaining,
            "slaWindow": self.sla_window,
            "daysInStage": self.days_in_stage,
            "previousDelays": self.previous_delays,
            "officer": officer_name,
            "officerId": self.officer_id,
            "remarks": self.remarks,
            "status": self.status,
            "normal": normal,
            "riskScore": risk_score,
            "priorityScore": priority_score,
            "category": category,
            "reasons": reasons,
            "action": action,
            "actionIcon": action_icon,
        }
