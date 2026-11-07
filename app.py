from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    init_db, get_user_by_email, create_user,
    get_vehicles_for_user, add_vehicle,
    create_appointment, get_active_appointments_for_user,
    get_pending_estimates_for_user, respond_to_estimate,
    get_service_history_for_user
)
import functools

app = Flask(__name__)
app.secret_key = 'lockservice-dev-secret'


def login_required(role=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('You do not have permission to access that page.', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('customer_dashboard') if session['role'] == 'customer'
                        else url_for('staff_dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user     = get_user_by_email(email)

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['name']    = user['name']
            session['role']    = user['role']
            return redirect(url_for('customer_dashboard') if user['role'] == 'customer'
                            else url_for('staff_dashboard'))

        flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', 'customer')

        errors = []
        if not name:
            errors.append('Full name is required.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if get_user_by_email(email):
            errors.append('An account with that email already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('login.html', register_mode=True,
                                   form_name=name, form_email=email)

        create_user(name, email, generate_password_hash(password), role)
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('login.html', register_mode=True)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Customer dashboard ────────────────────────────────────────────────────────

@app.route('/customer')
@login_required(role='customer')
def customer_dashboard():
    user_id      = session['user_id']
    vehicles     = get_vehicles_for_user(user_id)
    appointments = get_active_appointments_for_user(user_id)
    estimates    = get_pending_estimates_for_user(user_id)
    return render_template('customer_dashboard.html',
                           vehicles=vehicles,
                           appointments=appointments,
                           estimates=estimates)


# ── Vehicles (FR-02) ──────────────────────────────────────────────────────────

@app.route('/customer/vehicles/add', methods=['GET', 'POST'])
@login_required(role='customer')
def add_vehicle_view():
    if request.method == 'POST':
        make  = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        year  = request.form.get('year', '').strip()
        vin   = request.form.get('vin', '').strip()

        errors = []
        if not make:
            errors.append('Vehicle make is required.')
        if not model:
            errors.append('Vehicle model is required.')
        if not year or not year.isdigit() or not (1900 <= int(year) <= 2100):
            errors.append('Please enter a valid 4-digit year.')
        if not vin:
            errors.append('VIN is required.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('add_vehicle.html',
                                   form_make=make, form_model=model,
                                   form_year=year, form_vin=vin)

        add_vehicle(session['user_id'], make, model, int(year), vin)
        flash(f'Your {year} {make} {model} has been registered.', 'success')
        return redirect(url_for('customer_dashboard') + '#vehicles')

    return render_template('add_vehicle.html')


# ── Service requests (FR-03) ──────────────────────────────────────────────────

@app.route('/customer/service/request', methods=['GET', 'POST'])
@login_required(role='customer')
def request_service():
    vehicles = get_vehicles_for_user(session['user_id'])

    if not vehicles:
        flash('Please register a vehicle before submitting a service request.', 'warning')
        return redirect(url_for('add_vehicle_view'))

    if request.method == 'POST':
        vehicle_id   = request.form.get('vehicle_id', '')
        date         = request.form.get('appointment_date', '').strip()
        service_type = request.form.get('service_type', '').strip()
        description  = request.form.get('problem_description', '').strip()

        errors = []
        if not vehicle_id:
            errors.append('Please select a vehicle.')
        if not date:
            errors.append('Preferred appointment date is required.')
        if not service_type:
            errors.append('Service type is required.')
        if not description:
            errors.append('Problem description is required.')

        owned_ids = [str(v['vehicle_id']) for v in vehicles]
        if vehicle_id not in owned_ids:
            errors.append('Invalid vehicle selection.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('request_service.html', vehicles=vehicles,
                                   form_vehicle=vehicle_id, form_date=date,
                                   form_type=service_type, form_desc=description)

        create_appointment(int(vehicle_id), date, service_type, description)
        flash('Your service request has been submitted. We will be in touch to confirm your appointment.', 'success')
        return redirect(url_for('customer_dashboard') + '#appointments')

    return render_template('request_service.html', vehicles=vehicles)


# ── Estimates (FR-12) ─────────────────────────────────────────────────────────

@app.route('/customer/estimates/<int:estimate_id>/respond', methods=['POST'])
@login_required(role='customer')
def respond_estimate(estimate_id):
    decision = request.form.get('decision', '')
    if decision not in ('Approved', 'Declined'):
        flash('Invalid response.', 'danger')
        return redirect(url_for('customer_dashboard') + '#estimates')

    respond_to_estimate(estimate_id, decision, session['user_id'])

    if decision == 'Approved':
        flash('You approved the estimate. The service team has been notified.', 'success')
    else:
        flash('You declined the estimate. The service request has been canceled.', 'info')

    return redirect(url_for('customer_dashboard') + '#estimates')


# ── Service history (FR-13) ───────────────────────────────────────────────────

@app.route('/customer/history')
@login_required(role='customer')
def service_history():
    history = get_service_history_for_user(session['user_id'])
    return render_template('service_history.html', history=history)


# ── Staff dashboard (Diego's area — stub only) ────────────────────────────────

@app.route('/staff')
@login_required(role='staff')
def staff_dashboard():
    return render_template('staff_dashboard.html')


# ── App entry point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
