import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'lockservice.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL DEFAULT 'customer'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            make       TEXT    NOT NULL,
            model      TEXT    NOT NULL,
            year       INTEGER NOT NULL,
            vin        TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id          INTEGER NOT NULL,
            staff_id            INTEGER,
            appointment_date    TEXT    NOT NULL,
            service_type        TEXT    NOT NULL,
            problem_description TEXT    NOT NULL,
            status              TEXT    NOT NULL DEFAULT 'Requested',
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (staff_id)   REFERENCES users(user_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS estimates (
            estimate_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id   INTEGER NOT NULL UNIQUE,
            estimated_cost   REAL    NOT NULL,
            approval_status  TEXT    NOT NULL DEFAULT 'Pending',
            date_created     TEXT    NOT NULL,
            FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS service_records (
            service_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id  INTEGER NOT NULL UNIQUE,
            work_performed  TEXT    NOT NULL,
            notes           TEXT,
            final_cost      REAL,
            completion_date TEXT,
            FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
        )
    ''')

    conn.commit()
    conn.close()


# ── Vehicle helpers ──────────────────────────────────────────────────────────

def get_vehicles_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM vehicles WHERE user_id = ?', (user_id,)
    ).fetchall()
    conn.close()
    return rows


def add_vehicle(user_id, make, model, year, vin):
    conn = get_db()
    conn.execute(
        'INSERT INTO vehicles (user_id, make, model, year, vin) VALUES (?,?,?,?,?)',
        (user_id, make, model, year, vin)
    )
    conn.commit()
    conn.close()


# ── Appointment helpers ──────────────────────────────────────────────────────

def create_appointment(vehicle_id, appointment_date, service_type, problem_description):
    conn = get_db()
    conn.execute(
        '''INSERT INTO appointments
           (vehicle_id, appointment_date, service_type, problem_description, status)
           VALUES (?,?,?,?,?)''',
        (vehicle_id, appointment_date, service_type, problem_description, 'Requested')
    )
    conn.commit()
    conn.close()


def get_active_appointments_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        '''SELECT a.*, v.make, v.model, v.year,
                  e.estimated_cost, e.approval_status, sr.final_cost
           FROM appointments a
           JOIN vehicles v ON a.vehicle_id = v.vehicle_id
           LEFT JOIN estimates e ON a.appointment_id = e.appointment_id
           LEFT JOIN service_records sr ON sr.appointment_id = a.appointment_id
           WHERE v.user_id = ?
           ORDER BY a.appointment_date''',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


# ── Estimate helpers ─────────────────────────────────────────────────────────

def get_pending_estimates_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        '''SELECT e.*, a.service_type, a.appointment_date,
                  v.make, v.model, v.year
           FROM estimates e
           JOIN appointments a ON e.appointment_id = a.appointment_id
           JOIN vehicles v ON a.vehicle_id = v.vehicle_id
           WHERE v.user_id = ?
             AND e.approval_status = 'Pending'
             AND a.status NOT IN ('Completed', 'Canceled')
           ORDER BY e.date_created DESC''',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def respond_to_estimate(estimate_id, decision, user_id):
    conn = get_db()
    try:
        with conn:
            estimate = conn.execute("""SELECT e.* FROM estimates e
                JOIN appointments a ON a.appointment_id=e.appointment_id
                JOIN vehicles v ON v.vehicle_id=a.vehicle_id
                WHERE e.estimate_id=? AND v.user_id=? AND e.approval_status='Pending'
                AND a.status NOT IN ('Completed','Canceled')""", (estimate_id, user_id)).fetchone()
            if not estimate:
                return False
            conn.execute('UPDATE estimates SET approval_status=? WHERE estimate_id=?', (decision, estimate_id))
            if decision == 'Declined':
                conn.execute("UPDATE appointments SET status='Canceled' WHERE appointment_id=?", (estimate['appointment_id'],))
            return True
    finally:
        conn.close()


# ── Service history helpers ──────────────────────────────────────────────────

def get_service_history_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        '''SELECT sr.*, a.service_type, a.appointment_date,
                  v.make, v.model, v.year
           FROM service_records sr
           JOIN appointments a ON sr.appointment_id = a.appointment_id
           JOIN vehicles v ON a.vehicle_id = v.vehicle_id
           WHERE v.user_id = ?
           ORDER BY sr.completion_date DESC''',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


# ── User helpers (minimal — Denzel owns full auth) ───────────────────────────

def get_user_by_email(email):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email = ? COLLATE NOCASE', (email,)).fetchone()
    conn.close()
    return row


def create_user(name, email, password_hash, role='customer'):
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)',
                (name, email.strip().lower(), password_hash, role)
            )
            return cursor.lastrowid
    finally:
        conn.close()


# Shared staff/customer workflow. Each mutation is committed as one transaction.
def get_staff_appointments():
    conn = get_db()
    try:
        return conn.execute('''SELECT a.*, v.make, v.model, v.year, v.vin,
            u.name AS customer_name, u.email AS customer_email,
            e.estimated_cost, e.approval_status, sr.work_performed, sr.notes, sr.final_cost
            FROM appointments a JOIN vehicles v ON v.vehicle_id=a.vehicle_id
            JOIN users u ON u.user_id=v.user_id
            LEFT JOIN estimates e ON e.appointment_id=a.appointment_id
            LEFT JOIN service_records sr ON sr.appointment_id=a.appointment_id
            ORDER BY a.appointment_date, a.appointment_id''').fetchall()
    finally:
        conn.close()


def update_staff_appointment(appointment_id, staff_id, action, values):
    conn = get_db()
    try:
        with conn:
            appt = conn.execute('SELECT * FROM appointments WHERE appointment_id=?', (appointment_id,)).fetchone()
            if not appt:
                raise LookupError('Appointment not found.')
            if appt['status'] in ('Completed', 'Canceled'):
                raise ValueError('Completed or canceled appointments cannot be changed.')
            if action == 'appointment':
                conn.execute('UPDATE appointments SET appointment_date=?, status=?, staff_id=? WHERE appointment_id=?',
                             (values['date'], values['status'], staff_id, appointment_id))
            elif action == 'estimate':
                # A revised estimate always requires fresh customer approval.
                conn.execute('''INSERT INTO estimates(appointment_id,estimated_cost,approval_status,date_created)
                    VALUES(?,?,'Pending',date('now')) ON CONFLICT(appointment_id) DO UPDATE SET
                    estimated_cost=excluded.estimated_cost, approval_status='Pending', date_created=excluded.date_created''',
                             (appointment_id, values['cost']))
            elif action == 'status':
                if 'estimate_cost' in values:
                    conn.execute('''INSERT INTO estimates(appointment_id,estimated_cost,approval_status,date_created)
                        VALUES(?,?,'Pending',date('now')) ON CONFLICT(appointment_id) DO UPDATE SET
                        estimated_cost=excluded.estimated_cost, approval_status='Pending', date_created=excluded.date_created''',
                                 (appointment_id, values['estimate_cost']))
                if values['status'] == 'Completed':
                    conn.execute('''INSERT INTO service_records(appointment_id,work_performed,notes,final_cost,completion_date)
                        VALUES(?,?,?,?,date('now'))''',
                                 (appointment_id, values['work'], values['notes'], values['cost']))
                conn.execute('UPDATE appointments SET status=?,staff_id=? WHERE appointment_id=?',
                             (values['status'], staff_id, appointment_id))
    finally:
        conn.close()
