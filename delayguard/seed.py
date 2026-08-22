"""
Run this once to set up the database:
    python seed.py

Creates:
  - admin@cityservices.gov / admin123          (role: admin)
  - employee1@cityservices.gov / employee123    (role: employee, K. Rao's requests)
  - employee2@cityservices.gov / employee123    (role: employee, unassigned demo requests)
Also loads the original 20 demo requests from index.html into the database
so the app has data to show immediately.
"""
from app import app
from models import db, User, Request as ReqModel

DEMO_REQUESTS = [
    ("R101", "Revenue", "Land Registration (RTC)", "Critical", "Approval", 1, 10, 5, 3, "K. Rao"),
    ("R102", "Transport", "Driving Licence Renewal", "Normal", "Approval", 4, 12, 2, 0, "S. Iyer"),
    ("R103", "Revenue", "Income Certificate", "Normal", "Document Review", 1, 7, 4, 2, "K. Rao"),
    ("R104", "Registration", "Property Mutation", "Critical", "Verification", 6, 15, 2, 1, "P. Reddy"),
    ("R105", "Welfare", "Scholarship Application", "Normal", "Intake", 8, 10, 1, 0, "A. Basu"),
    ("R106", "Municipal Services", "Water Connection", "Normal", "Approval", 2, 9, 4, 2, "M. Fernandes"),
    ("R107", "Registration", "Birth Certificate", "Low", "Document Review", 5, 6, 1, 0, "P. Reddy"),
    ("R108", "Revenue", "Land Registration (RTC)", "Critical", "Approval", 0, 10, 7, 4, "K. Rao"),
    ("R109", "Transport", "Trade Licence", "Normal", "Verification", 3, 8, 1, 0, "S. Iyer"),
    ("R110", "Welfare", "Pension Verification", "Critical", "Approval", 2, 9, 5, 2, "A. Basu"),
    ("R111", "Municipal Services", "Building Permission", "Normal", "Document Review", 7, 20, 3, 1, "M. Fernandes"),
    ("R112", "Registration", "Caste Certificate", "Normal", "Intake", 5, 7, 1, 0, "P. Reddy"),
    ("R113", "Revenue", "Mutation Certificate", "Normal", "Verification", 6, 10, 2, 1, "K. Rao"),
    ("R114", "Transport", "Vehicle Fitness Certificate", "Low", "Completion", 3, 6, 1, 0, "S. Iyer"),
    ("R115", "Welfare", "Disability Certificate", "Critical", "Document Review", 2, 8, 4, 2, "A. Basu"),
    ("R116", "Municipal Services", "Trade Licence Renewal", "Normal", "Intake", 9, 12, 1, 0, "M. Fernandes"),
    ("R117", "Revenue", "Land Records Correction", "Normal", "Approval", 3, 9, 3, 1, "K. Rao"),
    ("R118", "Registration", "Marriage Certificate", "Low", "Verification", 8, 10, 2, 0, "P. Reddy"),
    ("R119", "Transport", "Learner's Licence", "Normal", "Completion", 4, 5, 1, 0, "S. Iyer"),
    ("R120", "Welfare", "Ration Card Update", "Normal", "Approval", 1, 7, 6, 3, "A. Basu"),
]

# In the original demo, "mine:true" rows belonged to the logged-in employee.
# We map those officer display names to employee1 so the "My queue" view
# still shows the same rows out of the box.
OFFICER_TO_LOGIN_EMPLOYEE = {
    "K. Rao": "employee1@cityservices.gov",
    "A. Basu": "employee1@cityservices.gov",
    "M. Fernandes": "employee1@cityservices.gov",
}


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

        # every distinct officer name in the demo data gets its own login too,
        # defaulting unmapped ones to employee2 so nothing is orphaned
        officer_names = sorted({row[9] for row in DEMO_REQUESTS})
        officer_users = {}
        for name in officer_names:
            login_email = OFFICER_TO_LOGIN_EMPLOYEE.get(name, "employee2@cityservices.gov")
            login_user = emp1 if login_email == emp1.email else emp2
            officer_users[name] = login_user

        created = 0
        for (rid, dept, service, importance, stage, days_remaining, sla_window,
             days_in_stage, previous_delays, officer_name) in DEMO_REQUESTS:
            if ReqModel.query.filter_by(request_id=rid).first():
                continue
            r = ReqModel(
                request_id=rid, department=dept, service=service, importance=importance,
                stage=stage, days_remaining=days_remaining, sla_window=sla_window,
                days_in_stage=days_in_stage, previous_delays=previous_delays,
                officer_id=officer_users[officer_name].id, status="Open",
            )
            db.session.add(r)
            created += 1
        db.session.commit()

        print(f"Users ready: {admin.email} (admin), {emp1.email} (employee), {emp2.email} (employee)")
        print(f"Requests created: {created}")
        print("Passwords: admin123 / employee123 — change these before this goes anywhere public.")


if __name__ == "__main__":
    run()
