import io
from datetime import datetime

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, abort
from dotenv import load_dotenv

from db import get_connection, get_dict_connection

load_dotenv()

app = Flask(__name__)

VISIT_TYPES = ["New Case", "Follow Up"]
GENDERS = ["Male", "Female", "Other"]
CONSULTATION_MODES = ["In Clinic", "Online"]
SOURCES = ["Google My Business", "Walk-in", "Instagram", "Referral", "Other"]
PAYMENT_MODES = ["Cash", "Card", "UPI", "Netbanking", "Other"]

FORM_OPTIONS = dict(
    visit_types=VISIT_TYPES,
    genders=GENDERS,
    consultation_modes=CONSULTATION_MODES,
    sources=SOURCES,
    payment_modes=PAYMENT_MODES,
)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# ---------- Patients list (main page) ----------

@app.route("/")
def patients():
    filters = {
        "search": request.args.get("search", "").strip(),
        "source": request.args.get("source", "").strip(),
        "city": request.args.get("city", "").strip(),
    }

    query = """
        SELECT p.*,
               (SELECT MAX(visit_date) FROM visits v WHERE v.patient_id = p.id) AS last_visit_date,
               (SELECT MIN(next_followup_date) FROM visits v
                  WHERE v.patient_id = p.id AND next_followup_date >= CURRENT_DATE
                    AND reminder_enabled = TRUE) AS next_followup_date
        FROM patients p
        WHERE 1=1
    """
    params = []

    if filters["search"]:
        query += " AND (p.name ILIKE %s OR p.registration_no ILIKE %s)"
        like = f"%{filters['search']}%"
        params += [like, like]
    if filters["source"]:
        query += " AND p.source = %s"
        params.append(filters["source"])
    if filters["city"]:
        query += " AND p.city ILIKE %s"
        params.append(f"%{filters['city']}%")

    query += " ORDER BY p.created_at DESC LIMIT 500"

    conn = get_dict_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return render_template(
        "patients.html", rows=rows, filters=filters, active="patients", **FORM_OPTIONS
    )


# ---------- New patient + first visit ----------

@app.route("/patients/new", methods=["GET", "POST"])
def new_patient():
    if request.method == "POST":
        patient_data = {
            "registration_no": request.form["registration_no"].strip(),
            "name": request.form["name"].strip(),
            "dob": request.form.get("dob") or None,
            "gender": request.form.get("gender") or None,
            "phone_number": request.form.get("phone_number", "").strip(),
            "city": request.form.get("city", "").strip(),
            "country": request.form.get("country", "").strip(),
            "source": request.form.get("source") or None,
        }

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO patients (registration_no, name, dob, gender, phone_number, city, country, source)
                    VALUES (%(registration_no)s, %(name)s, %(dob)s, %(gender)s, %(phone_number)s, %(city)s, %(country)s, %(source)s)
                    RETURNING id
                    """,
                    patient_data,
                )
                patient_id = cur.fetchone()[0]

                visit_data = _visit_form_data(request.form, patient_id, visit_type="New Case")
                _insert_visit(cur, visit_data)
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for("patient_profile", patient_id=patient_id))

    return render_template("new_patient.html", active="new", **FORM_OPTIONS)


# ---------- Patient profile ----------

@app.route("/patients/<int:patient_id>")
def patient_profile(patient_id):
    conn = get_dict_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
            patient = cur.fetchone()
            if not patient:
                abort(404)

            cur.execute(
                "SELECT * FROM visits WHERE patient_id = %s ORDER BY visit_date DESC, id DESC",
                (patient_id,),
            )
            visits = cur.fetchall()
    finally:
        conn.close()

    return render_template("patient_profile.html", patient=patient, visits=visits, active="patients")


# ---------- Add follow-up ----------

@app.route("/patients/<int:patient_id>/add-followup", methods=["GET", "POST"])
def add_followup(patient_id):
    conn = get_dict_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
            patient = cur.fetchone()
            if not patient:
                abort(404)

            if request.method == "POST":
                visit_data = _visit_form_data(request.form, patient_id, visit_type="Follow Up")
                _insert_visit(cur, visit_data)
                conn.commit()
                return redirect(url_for("patient_profile", patient_id=patient_id))
    finally:
        conn.close()

    return render_template(
        "add_followup.html", patient=patient, active="patients",
        consultation_modes=CONSULTATION_MODES, payment_modes=PAYMENT_MODES,
    )


# ---------- Edit visit ----------

@app.route("/visits/<int:visit_id>/edit", methods=["GET", "POST"])
def edit_visit(visit_id):
    conn = get_dict_connection()
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                cur.execute(
                    """
                    UPDATE visits SET
                        visit_date = %s, consultation_mode = %s, notes = %s,
                        medicine_duration_days = %s, charges = %s, payment_mode = %s,
                        next_followup_date = %s, reminder_enabled = %s
                    WHERE id = %s
                    """,
                    (
                        request.form["visit_date"],
                        request.form.get("consultation_mode") or None,
                        request.form.get("notes", "").strip(),
                        request.form.get("medicine_duration_days") or None,
                        request.form.get("charges") or None,
                        request.form.get("payment_mode") or None,
                        request.form.get("next_followup_date") or None,
                        "reminder_enabled" in request.form,
                        visit_id,
                    ),
                )
                cur.execute("SELECT patient_id FROM visits WHERE id = %s", (visit_id,))
                patient_id = cur.fetchone()["patient_id"]
                conn.commit()
                return redirect(url_for("patient_profile", patient_id=patient_id))

            cur.execute("SELECT * FROM visits WHERE id = %s", (visit_id,))
            visit = cur.fetchone()
            if not visit:
                abort(404)
            cur.execute("SELECT * FROM patients WHERE id = %s", (visit["patient_id"],))
            patient = cur.fetchone()
    finally:
        conn.close()

    return render_template(
        "edit_visit.html", visit=visit, patient=patient, active="patients",
        consultation_modes=CONSULTATION_MODES, payment_modes=PAYMENT_MODES,
    )


# ---------- One-click reminder toggle ----------

@app.route("/visits/<int:visit_id>/toggle-reminder", methods=["POST"])
def toggle_reminder(visit_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visits SET reminder_enabled = NOT reminder_enabled WHERE id = %s RETURNING patient_id",
                (visit_id,),
            )
            row = cur.fetchone()
            if not row:
                abort(404)
            patient_id = row[0]
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("patient_profile", patient_id=patient_id))


# ---------- Export / analysis page ----------

def _export_filters_from_request():
    return {
        "search": request.args.get("search", "").strip(),
        "visit_type": request.args.get("visit_type", "").strip(),
        "consultation_mode": request.args.get("consultation_mode", "").strip(),
        "source": request.args.get("source", "").strip(),
        "payment_mode": request.args.get("payment_mode", "").strip(),
        "date_from": request.args.get("date_from", "").strip(),
        "date_to": request.args.get("date_to", "").strip(),
    }


def _build_export_query(filters, limit_clause=""):
    query = """
        SELECT p.registration_no, p.name, p.gender, p.phone_number, p.city, p.country, p.source,
               v.visit_type, v.consultation_mode, v.notes, v.medicine_duration_days,
               v.charges, v.payment_mode, v.visit_date, v.next_followup_date
        FROM visits v
        JOIN patients p ON p.id = v.patient_id
        WHERE 1=1
    """
    params = []

    if filters["search"]:
        query += " AND (p.name ILIKE %s OR p.registration_no ILIKE %s)"
        like = f"%{filters['search']}%"
        params += [like, like]
    if filters["visit_type"]:
        query += " AND v.visit_type = %s"
        params.append(filters["visit_type"])
    if filters["consultation_mode"]:
        query += " AND v.consultation_mode = %s"
        params.append(filters["consultation_mode"])
    if filters["source"]:
        query += " AND p.source = %s"
        params.append(filters["source"])
    if filters["payment_mode"]:
        query += " AND v.payment_mode = %s"
        params.append(filters["payment_mode"])
    if filters["date_from"]:
        query += " AND v.visit_date >= %s"
        params.append(filters["date_from"])
    if filters["date_to"]:
        query += " AND v.visit_date <= %s"
        params.append(filters["date_to"])

    query += " ORDER BY v.visit_date DESC, v.id DESC" + limit_clause
    return query, params


@app.route("/export")
def export_page():
    filters = _export_filters_from_request()
    query, params = _build_export_query(filters, limit_clause=" LIMIT 100")

    conn = get_dict_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return render_template(
        "export.html", rows=rows, filters=filters, active="export",
        visit_types=VISIT_TYPES, consultation_modes=CONSULTATION_MODES,
        sources=SOURCES, payment_modes=PAYMENT_MODES,
    )


@app.route("/export/download")
def export_download():
    filters = _export_filters_from_request()
    query, params = _build_export_query(filters)

    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Visits")
    buffer.seek(0)

    filename = f"clinic_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        buffer, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------- helpers ----------

def _visit_form_data(form, patient_id, visit_type):
    return {
        "patient_id": patient_id,
        "visit_type": visit_type,
        "consultation_mode": form.get("consultation_mode") or None,
        "notes": form.get("notes", "").strip(),
        "medicine_duration_days": form.get("medicine_duration_days") or None,
        "charges": form.get("charges") or None,
        "payment_mode": form.get("payment_mode") or None,
        "visit_date": form["visit_date"],
        "next_followup_date": form.get("next_followup_date") or None,
    }


def _insert_visit(cur, data):
    cur.execute(
        """
        INSERT INTO visits
            (patient_id, visit_type, consultation_mode, notes, medicine_duration_days,
             charges, payment_mode, visit_date, next_followup_date)
        VALUES
            (%(patient_id)s, %(visit_type)s, %(consultation_mode)s, %(notes)s, %(medicine_duration_days)s,
             %(charges)s, %(payment_mode)s, %(visit_date)s, %(next_followup_date)s)
        """,
        data,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
