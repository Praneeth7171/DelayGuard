# DelayGuard

One shared database. Admin uploads an Excel sheet → everyone (admin + employees)
sees the same live data, scored automatically for SLA risk.

## Run it locally — 4 commands

```bash
pip install -r requirements.txt
python make_template.py && python seed.py
python app.py
```

Open **http://localhost:5000** in your browser.

| Role     | Email                       | Password    |
|----------|------------------------------|-------------|
| Admin    | admin@cityservices.gov       | admin123    |
| Employee | employee1@cityservices.gov   | employee123 |
| Employee | employee2@cityservices.gov   | employee123 |

That's it — one Flask process serves both the API and the web page.

## How the "shared Excel" part works

1. Log in as **admin**.
2. Sidebar → **Download template** → fills you a `.xlsx` with the right columns.
3. Edit rows in Excel (add new `request_id`s, or edit existing ones), save.
4. Sidebar → **Import Excel** → pick the file.
5. That data goes straight into `delayguard.db` (SQLite) — the **one** database
   both admin and employee logins read from. Employees just need to refresh
   or log back in to see the update; nothing is stored per-browser.

No spreadsheet syncing, no separate "employee data" file — one database,
one source of truth, Excel is just the admin's input method.

## Running it for a demo on multiple laptops

1. One laptop runs `python app.py`. Its terminal prints something like
   `Running on http://192.168.x.x:5000` — that's the address.
2. Everyone else, same WiFi, opens `http://<that-ip>:5000` in a browser.
   Nothing to install on their side.
3. If it won't connect, it's almost always the host's firewall blocking
   port 5000 — allow it (or turn the firewall off for the demo).

## Pushing to GitHub

`delayguard.db` is your live data — it's already in `.gitignore` so it won't
get committed. Push everything else as normal; whoever clones the repo runs
the same 4 commands above to get their own fresh database.

## If you want a "real" database later

Only one line changes, in `backend/app.py`:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:pass@host/dbname"
```
(install `psycopg2-binary` first). Everything else — models, routes, risk
scoring, the frontend — stays exactly the same.

## What's in here

Everything lives in one flat folder — no subfolders to worry about:

```
app.py                 Flask app: routes, sessions, Excel upload, serves index.html
models.py              User + Request models, the SLA risk-scoring formula
seed.py                Run once: creates the 3 logins + loads 20 demo requests
make_template.py       Generates requests_template.xlsx
requirements.txt
index.html             The dashboard UI — calls the API instead of using fake data
requests_template.xlsx Pre-generated template (make_template.py regenerates it)
```

`delayguard.db` gets created next to these files the first time you run
`seed.py` — it's already in `.gitignore` so it won't get committed.
