"""
Run once (or whenever you want a fresh copy) to generate requests_template.xlsx
— the file admins fill in and upload via the dashboard's Excel import.
    python make_template.py
"""
import pandas as pd

COLUMNS = [
    "request_id", "department", "service", "importance", "stage",
    "days_remaining", "sla_window", "days_in_stage", "previous_delays", "officer_email",
]

SAMPLE_ROWS = [
    ["R101", "Revenue", "Land Registration (RTC)", "Critical", "Approval", 1, 10, 5, 3, "employee1@cityservices.gov"],
    ["R102", "Transport", "Driving Licence Renewal", "Normal", "Approval", 4, 12, 2, 0, "employee2@cityservices.gov"],
    ["R103", "Revenue", "Income Certificate", "Normal", "Document Review", 1, 7, 4, 2, "employee1@cityservices.gov"],
]

NOTES = pd.DataFrame({
    "column": COLUMNS,
    "notes": [
        "Unique ID, e.g. R121. Existing IDs are updated, new IDs are created.",
        "Must be one of: Revenue, Transport, Municipal Services, Registration, Welfare (or add a new one).",
        "Free text — name of the service being requested.",
        "One of: Critical, Normal, Low.",
        "One of: Intake, Verification, Document Review, Approval, Completion.",
        "Whole number. Days left before the SLA deadline (0 or negative = breached).",
        "Whole number. Total SLA window in days for this request.",
        "Whole number. Days the request has spent in its current stage.",
        "Whole number. Times this request has already been delayed in earlier stages.",
        "Email of the employee this request is assigned to. Must match a user account.",
    ],
})

with pd.ExcelWriter("requests_template.xlsx", engine="openpyxl") as writer:
    pd.DataFrame(SAMPLE_ROWS, columns=COLUMNS).to_excel(writer, sheet_name="requests", index=False)
    NOTES.to_excel(writer, sheet_name="column_notes", index=False)

print("Wrote requests_template.xlsx")
