# Clinic App

A clinic management app: patient records with visit history, an "Add follow-up" flow
that doesn't require re-entering patient details, Excel export for analysis, and an
automated WhatsApp reminder sent the evening before a patient's next follow-up.

## How the data is structured

Two tables:
- **patients** — identity/demographics, entered once (registration no., name, DOB,
  gender, phone, city, country, source)
- **visits** — one row per visit or follow-up, linked to a patient (visit type,
  consultation mode, notes, medicine duration, charges, payment mode, visit date,
  next follow-up date, and a reminder on/off toggle)

## 1. Set up the database (Supabase)

1. Open your Supabase project's **SQL Editor**.
2. Paste the contents of `schema.sql` and click **Run**. This creates both tables.

## 2. Test locally (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your real DATABASE_URL
python app.py
```

Open http://localhost:5000 in your browser.

## 3. Push to GitHub

If you're not comfortable with git commands, the easiest way is:
1. Create a new **private** repository on github.com (e.g. `clinic-app`).
2. On the repo page, click **uploading an existing file** and drag in every file and
   folder here — make sure `templates/` and `static/` stay as folders, not flattened.
3. Do **not** upload your real `.env` file — only `.env.example` (it has no real secrets).

## 4. Deploy the web app on Render

1. New **Web Service** → connect your GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn app:app`
4. Under **Environment**, add: `DATABASE_URL` = your Supabase connection string.
5. Deploy. Render gives you a URL like `https://clinic-app-xxxx.onrender.com` — this
   is the page you'll use day to day.

## 5. Deploy the reminder job on Render (separate service)

1. New **Cron Job** → connect the same GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Command: `python reminder_job.py`
4. Schedule: `30 12 * * *` (UTC — this is 6:00 PM IST)
5. Add the same `DATABASE_URL`, plus once you have them:
   `WHATSAPP_API_URL`, `WHATSAPP_API_KEY`, `WHATSAPP_TEMPLATE_NAME`, `CLINIC_NAME`.

## 6. Test end-to-end

Add a dummy patient with tomorrow's date as the next follow-up and a real phone
number. Trigger the Cron Job manually once from Render's dashboard ("Trigger Run")
to confirm the message actually arrives, rather than waiting for the schedule.

## How to use the app day to day

- **Patients** (home page): search or filter, click any row to open that person's profile.
- **New case**: only for someone who has never visited before — fills in their
  details once and records their first visit together.
- **Inside a patient's profile**: click **+ Add follow-up** for a short form (just
  the visit-specific fields) — no retyping name, phone, DOB, etc.
- **Edit** on any visit row: change any detail, or untick "Send WhatsApp reminder for
  this follow-up" to silence that specific reminder (e.g. patient has recovered)
  without deleting the follow-up date itself.
- The **On/Off** button in the Reminder column on a patient's profile is a one-click
  shortcut for the same toggle, without opening the full edit form.
- **Export data**: filter by date range, visit type, source, consultation mode, or
  payment mode, then download exactly that as an Excel file.

## Notes

- No login is required (by your choice) — keep the Render URL private. A simple
  shared password can be added later in about 10 lines of code if that ever feels
  necessary.
- `reminder_sent` prevents a message going out twice for the same follow-up;
  `reminder_enabled` is the manual on/off switch you control per visit.
- The WhatsApp request shape in `reminder_job.py` is generic — check your chosen
  BSP's docs once you sign up, in case their exact API payload differs slightly.
- Editing a patient's own core details (wrong phone number, name spelling) isn't
  built into the app — you said this is rare enough to fix directly in Supabase's
  table editor if it ever comes up.
