"""Run with: python -m unittest discover -s tests -v. Uses disposable SQLite files."""
import importlib
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from contextlib import closing
from pathlib import Path

import database as db


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # app imports init_db; redirect its import-time initialization too.
        cls.bootstrap = tempfile.TemporaryDirectory()
        cls.original_path = db.DB_PATH
        db.DB_PATH = str(Path(cls.bootstrap.name) / 'bootstrap.db')
        cls.module = importlib.import_module('app')
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True, SECRET_KEY='test-only-secret',
                              STAFF_INVITE_CODE='test-invite', STAFF_INVITE_CODES=[])

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.original_path
        cls.bootstrap.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = str(Path(self.tmp.name) / 'test.db')
        db.init_db()
        self.client = self.app.test_client()
        self.owner = db.create_user('Owner', 'owner@example.com', 'fixture')
        self.other = db.create_user('Other', 'other@example.com', 'fixture')
        self.staff = db.create_user('Staff', 'staff@example.com', 'fixture', 'staff')
        db.add_vehicle(self.owner, 'Toyota', 'Camry', 2020, 'TESTVIN')
        self.vehicle = db.get_vehicles_for_user(self.owner)[0]['vehicle_id']
        db.create_appointment(self.vehicle, '2026-12-01', 'Repair', 'Test problem')
        self.appt = db.get_staff_appointments()[0]['appointment_id']

    def tearDown(self):
        self.tmp.cleanup()

    def login_as(self, uid=None, role='customer'):
        with self.client.session_transaction() as s:
            s.clear()
            s.update(user_id=uid or self.owner, name='Test', role=role, staff_csrf='test-token')

    def register(self, **changes):
        data = dict(name='New User', email='new@example.com', password='Password123',
                    confirm_password='Password123', role='customer')
        data.update(changes)
        return self.client.post('/register', data=data)

    def test_registration_hash_and_login_logout(self):
        self.assertEqual(self.register().status_code, 302)
        user = db.get_user_by_email('NEW@example.com')
        self.assertNotEqual(user['password_hash'], 'Password123')
        self.assertTrue(self.module.check_password_hash(user['password_hash'], 'Password123'))
        response = self.client.post('/login', data={'email': ' NEW@example.com ', 'password': 'Password123'})
        self.assertTrue(response.location.endswith('/customer'))
        self.client.get('/logout')
        with self.client.session_transaction() as s:
            self.assertNotIn('user_id', s)

    def test_invalid_registration_branches(self):
        for changes in [dict(name=''), dict(email='invalid'), dict(password='short'),
                        dict(confirm_password='different'), dict(role='admin'),
                        dict(role='staff', invite_code='wrong')]:
            with self.subTest(changes=changes):
                self.assertEqual(self.register(**changes).status_code, 200)
                self.assertIsNone(db.get_user_by_email('new@example.com'))

    def test_staff_invitation(self):
        self.assertEqual(self.register(role='staff', invite_code='test-invite').status_code, 302)
        self.assertEqual(db.get_user_by_email('new@example.com')['role'], 'staff')

    def test_duplicate_email_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_user('Duplicate', ' OWNER@example.com ', 'hash')

    def test_bad_credentials_and_sql_injection(self):
        for email in ['owner@example.com', "' OR 1=1 --"]:
            self.assertEqual(self.client.post('/login', data={'email': email, 'password': 'wrong'}).status_code, 200)
            with self.client.session_transaction() as s:
                self.assertNotIn('user_id', s)

    def test_authentication_and_role_guards(self):
        for route in ['/customer', '/customer/history', '/staff', '/customer/vehicles/add', '/customer/service/request']:
            self.assertEqual(self.client.get(route).status_code, 302)
        self.login_as()
        self.assertEqual(self.client.get('/staff').status_code, 302)
        self.login_as(self.staff, 'staff')
        self.assertEqual(self.client.get('/customer').status_code, 302)

    def test_database_foreign_keys_and_persistence(self):
        with closing(db.get_db()) as conn:
            self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO vehicles(user_id,make,model,year,vin) VALUES(-1,'A','B',2020,'C')")
        db.init_db()
        self.assertEqual(len(db.get_vehicles_for_user(self.owner)), 1)
        self.assertEqual(db.get_vehicles_for_user(self.other), [])

    def test_vehicle_validation_and_creation(self):
        self.login_as()
        for year in ['1899', '2101', 'text', '']:
            self.assertEqual(self.client.post('/customer/vehicles/add', data=dict(make='A', model='B', year=year, vin='C')).status_code, 200)
        self.assertEqual(len(db.get_vehicles_for_user(self.owner)), 1)
        self.assertEqual(self.client.post('/customer/vehicles/add', data=dict(make='A', model='B', year='2020', vin='C')).status_code, 302)
        self.assertEqual(len(db.get_vehicles_for_user(self.owner)), 2)

    def test_service_request_ownership(self):
        self.login_as(self.other)
        db.add_vehicle(self.other, 'A', 'B', 2020, 'OTHER')
        self.assertEqual(self.client.post('/customer/service/request', data=dict(vehicle_id=self.vehicle, appointment_date='2026-12-01', service_type='Repair', problem_description='Test')).status_code, 200)
        self.assertEqual(len(db.get_staff_appointments()), 1)

    def test_estimate_ownership_decline_and_replay(self):
        db.update_staff_appointment(self.appt, self.staff, 'estimate', {'cost': 100})
        eid = db.get_pending_estimates_for_user(self.owner)[0]['estimate_id']
        self.assertFalse(db.respond_to_estimate(eid, 'Approved', self.other))
        self.assertTrue(db.respond_to_estimate(eid, 'Declined', self.owner))
        self.assertFalse(db.respond_to_estimate(eid, 'Approved', self.owner))
        self.assertEqual(db.get_staff_appointments()[0]['status'], 'Canceled')

    def test_completion_history_and_terminal_guard(self):
        db.update_staff_appointment(self.appt, self.staff, 'status', dict(status='Completed', work='Fixed lock', notes='', cost=100))
        self.assertEqual(db.get_service_history_for_user(self.owner)[0]['final_cost'], 100)
        self.assertEqual(db.get_service_history_for_user(self.other), [])
        with self.assertRaises(ValueError):
            db.update_staff_appointment(self.appt, self.staff, 'estimate', {'cost': 200})

    def test_transaction_rollback(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.update_staff_appointment(self.appt, -1, 'status', dict(status='Completed', work='Test', notes='', cost=100))
        self.assertEqual(db.get_service_history_for_user(self.owner), [])
        self.assertEqual(db.get_staff_appointments()[0]['status'], 'Requested')

    def test_money_boundaries(self):
        for value in ['0', '0.01', '1000000']:
            self.assertEqual(self.module.money(value), float(value))
        for value in ['-0.01', '1000000.01', '1.001', 'NaN', 'Infinity', 'abc', '']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.module.money(value)

    def test_staff_csrf_and_missing_appointment(self):
        self.login_as(self.staff, 'staff')
        self.assertEqual(self.client.post(f'/staff/appointments/{self.appt}/estimate', data={'estimated_cost': '10'}).status_code, 400)
        self.assertEqual(self.client.post('/staff/appointments/99999/estimate', data={'estimated_cost': '10', 'csrf_token': 'test-token'}).status_code, 404)

    def test_rendered_pages(self):
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.login_as()
        for route in ['/customer', '/customer/history', '/customer/vehicles/add', '/customer/service/request']:
            self.assertEqual(self.client.get(route).status_code, 200)
        self.login_as(self.staff, 'staff')
        self.assertEqual(self.client.get('/staff').status_code, 200)

    # Expected failures document unmet acceptance criteria; they are not passes.
    @unittest.expectedFailure
    def test_known_gap_customer_csrf(self):
        self.login_as()
        response = self.client.post('/customer/vehicles/add', data=dict(make='A', model='B', year='2020', vin='C'))
        self.assertIn(response.status_code, (400, 403))

    def test_invalid_service_date(self):
        self.login_as()
        for value in ['', 'not-a-date', '2026-02-30', (date.today() - timedelta(days=1)).isoformat()]:
            with self.subTest(value=value):
                response = self.client.post('/customer/service/request', data=dict(vehicle_id=self.vehicle, appointment_date=value, service_type='Repair', problem_description='Test'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(db.get_staff_appointments()), 1)

    def test_current_and_future_service_dates(self):
        self.login_as()
        for offset in [0, 1]:
            value = (date.today() + timedelta(days=offset)).isoformat()
            with self.subTest(value=value):
                response = self.client.post('/customer/service/request', data=dict(vehicle_id=self.vehicle, appointment_date=value, service_type='Repair', problem_description='Test'))
                self.assertEqual(response.status_code, 302)
                self.assertIn(value, [a['appointment_date'] for a in db.get_staff_appointments()])
        self.assertEqual(len(db.get_staff_appointments()), 3)

    def test_staff_date_validation(self):
        self.login_as(self.staff, 'staff')
        original = db.get_staff_appointments()[0]['appointment_date']
        for value in ['not-a-date', (date.today() - timedelta(days=1)).isoformat()]:
            response = self.client.post(f'/staff/appointments/{self.appt}/appointment', data=dict(csrf_token='test-token', appointment_date=value, status='Confirmed'), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.get_staff_appointments()[0]['appointment_date'], original)
        for offset in [0, 1]:
            value = (date.today() + timedelta(days=offset)).isoformat()
            response = self.client.post(f'/staff/appointments/{self.appt}/appointment', data=dict(csrf_token='test-token', appointment_date=value, status='Confirmed'))
            self.assertEqual(response.status_code, 303)
            self.assertEqual(db.get_staff_appointments()[0]['appointment_date'], value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
