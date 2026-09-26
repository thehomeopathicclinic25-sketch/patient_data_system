-- Run this once in Supabase's SQL Editor to create the tables.
-- (Supabase dashboard -> SQL Editor -> New query -> paste this -> Run)

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    registration_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    dob DATE,
    gender TEXT,
    phone_number TEXT,           -- include country code, e.g. 91XXXXXXXXXX
    city TEXT,
    country TEXT,
    source TEXT,                 -- Google My Business, Walk-in, Instagram, Referral, Other
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS visits (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_type TEXT NOT NULL,             -- 'New Case' or 'Follow Up'
    consultation_mode TEXT,               -- 'In Clinic' or 'Online'
    notes TEXT,
    medicine_duration_days INTEGER,
    charges NUMERIC(10, 2),
    payment_mode TEXT,                    -- Cash, Card, UPI, Netbanking, Other
    visit_date DATE NOT NULL,
    next_followup_date DATE,
    reminder_enabled BOOLEAN DEFAULT TRUE,  -- one-click toggle to silence a reminder
    reminder_sent BOOLEAN DEFAULT FALSE,    -- prevents double-sending
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visits_followup_date ON visits (next_followup_date);
CREATE INDEX IF NOT EXISTS idx_visits_patient_id ON visits (patient_id);
