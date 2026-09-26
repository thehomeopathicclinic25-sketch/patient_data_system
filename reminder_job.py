"""
Run once a day (via Render Cron Job), in the evening, so tomorrow's follow-ups get a
full day's notice. Finds every visit whose next_followup_date is tomorrow, hasn't
been reminded yet, and hasn't had its reminder turned off, sends a WhatsApp message,
then marks it as reminded so it's never sent twice.

NOTE: The actual API call in send_whatsapp_message() is written generically.
Once you sign up with a WhatsApp BSP, check their exact API docs in case the
payload/headers shape needs adjusting to match that provider.
"""

import os
import requests
from dotenv import load_dotenv

from db import get_dict_connection

load_dotenv()


def get_visits_due_tomorrow(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.id, v.next_followup_date, p.name, p.phone_number
            FROM visits v
            JOIN patients p ON p.id = v.patient_id
            WHERE v.next_followup_date = CURRENT_DATE + INTERVAL '1 day'
              AND v.reminder_enabled = TRUE
              AND (v.reminder_sent IS NOT TRUE)
              AND p.phone_number IS NOT NULL
              AND p.phone_number <> ''
            """
        )
        return cur.fetchall()


def send_whatsapp_message(phone_number, patient_name, followup_date):
    api_url = os.environ["WHATSAPP_API_URL"]
    api_key = os.environ["WHATSAPP_API_KEY"]
    template_name = os.environ["WHATSAPP_TEMPLATE_NAME"]
    clinic_name = os.environ.get("CLINIC_NAME", "the clinic")

    payload = {
        "to": phone_number,
        "template_name": template_name,
        "parameters": {
            "patient_name": patient_name,
            "followup_date": str(followup_date),
            "clinic_name": clinic_name,
        },
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    response = requests.post(api_url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    return response


def mark_reminded(conn, visit_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE visits SET reminder_sent = TRUE WHERE id = %s", (visit_id,))
    conn.commit()


def main():
    conn = get_dict_connection()
    try:
        visits = get_visits_due_tomorrow(conn)
        print(f"Found {len(visits)} visit(s) due for a reminder.")

        for visit in visits:
            try:
                send_whatsapp_message(visit["phone_number"], visit["name"], visit["next_followup_date"])
                mark_reminded(conn, visit["id"])
                print(f"Reminder sent to {visit['name']} ({visit['phone_number']})")
            except Exception as e:
                print(f"FAILED to remind {visit['name']} ({visit['phone_number']}): {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
