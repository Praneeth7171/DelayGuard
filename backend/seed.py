"""
Run this once to set up the database:
    python make_template.py && python seed.py

Creates:
  - admin@cityservices.gov / admin123          (role: admin)
  - employee1@cityservices.gov / employee123    (role: employee)
  - employee2@cityservices.gov / employee123    (role: employee)

Then loads requests_template.xlsx (the "requests" sheet) into the database,
using the exact same column rules as the dashboard's Excel import — so the
starting data is never anything other than what's in that spreadsheet.
"""
import os

import pandas as pd

from app import app
from models import db, User, Request as ReqModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "requests_template.xlsx")


def run():
    with app.app_context():
        db.create_all()

        def get_or_create_user(name, email, password, role):
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(name=name, email=email, role=role)
                u.set_password(password)
                db.session.add(u)
                db.session.commit()
            return u

        admin = get_or_create_user("Admin User", "admin@cityservices.gov", "admin123", "admin")
        emp1 = get_or_create_user("Field Officer 1", "employee1@cityservices.gov", "employee123", "employee")
        emp2 = get_or_create_user("Field Officer 2", "employee2@cityservices.gov", "employee123", "employee")

        created, updated = 0, 0
        if not os.path.exists(TEMPLATE_PATH):
            print(f"No {os.path.basename(TEMPLATE_PATH)} found — run 'python make_template.py' first. "
                  "Skipping request import; users are still ready to log in.")
        else:
            df = pd.read_excel(TEMPLATE_PATH, sheet_name="requests")
            for _, row in df.iterrows():
                rid = str(row["request_id"]).strip()
                officer = User.query.filter_by(
                    email=str(row.get("officer_email", "")).strip().lower()
                ).first()

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
            db.session.commit()

        print(f"Users ready: {admin.email} (admin), {emp1.email} (employee), {emp2.email} (employee)")
        print(f"Requests from requests_template.xlsx — created: {created}, updated: {updated}")
        print("Passwords: admin123 / employee123 — change these before this goes anywhere public.")


if __name__ == "__main__":
    run()