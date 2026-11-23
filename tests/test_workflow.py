import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import database
from app import app


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(database, 'DB_PATH', str(Path(self.temp.name) / 'test.db'))
        self.patch.start()
        database.init_db()
        app.config['TESTING'] = True
        self.owner = database.create_user('Owner', 'owner@example.com', 'hash')
        self.staff_id = database.create_user('Staff', 'staff@example.com', 'hash', 'staff')
        self.other = database.create_user('Other', 'other@example.com', 'hash')
        database.add_vehicle(self.owner, 'Honda', 'Civic', 2020, 'VIN')
        vehicle = database.get_vehicles_for_user(self.owner)[0]
        database.create_appointment(vehicle['vehicle_id'], '2026-12-01', 'Lock repair', 'Broken lock')
        self.id = database.get_staff_appointments()[0]['appointment_id']
        self.staff = self.client(self.staff_id, 'staff')
        self.customer = self.client(self.owner, 'customer')

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def client(self, user_id, role):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=user_id, role=role, name=role, staff_csrf='token')
        return client

    def update(self, action, **values):
        return self.staff.post(f'/staff/appointments/{self.id}/{action}', data=dict(csrf_token='token', **values))

    def test_shared_workflow(self):
        self.assertIn(b'Broken lock', self.staff.get('/staff').data)
        self.assertEqual(self.update('appointment', appointment_date='2026-12-02', status='Confirmed').status_code, 303)
        page = self.customer.get('/customer').data
        self.assertIn(b'2026-12-02', page)
        self.assertIn(b'Confirmed', page)
        self.assertEqual(self.update('status', status='In Progress', estimated_cost='125.50').status_code, 303)
        self.assertIn(b'125.50', self.customer.get('/customer').data)
        estimate = database.get_pending_estimates_for_user(self.owner)[0]
        self.customer.post(f"/customer/estimates/{estimate['estimate_id']}/respond", data={'decision': 'Approved'})
        self.assertIn(b'Approved', self.staff.get('/staff').data)
        self.update('status', status='In Progress')
        self.assertIn(b'In Progress', self.customer.get('/customer').data)
        self.update('status', status='Completed', work_performed='Replaced lock', notes='New keys provided', final_cost='120.00')
        completed_page = self.customer.get('/customer').data
        self.assertIn(b'Completed', completed_page)
        self.assertIn(b'120.00', completed_page)
        history = self.customer.get('/customer/history').data
        self.assertIn(b'Replaced lock', history)
        self.assertIn(b'120.00', history)
        self.assertEqual(database.get_active_appointments_for_user(self.owner)[0]['status'], 'Completed')

    def test_permissions_validation_and_ownership(self):
        path = f'/staff/appointments/{self.id}/status'
        self.customer.post(path, data={'csrf_token': 'token', 'status': 'In Progress'})
        self.assertEqual(database.get_staff_appointments()[0]['status'], 'Requested')
        self.assertEqual(self.staff.post(path, data={'status': 'In Progress'}).status_code, 400)
        self.update('estimate', estimated_cost='NaN')
        self.assertIsNone(database.get_staff_appointments()[0]['estimated_cost'])
        self.update('status', status='Completed', work_performed='', final_cost='10')
        self.assertEqual(database.get_service_history_for_user(self.owner), [])
        self.update('estimate', estimated_cost='0')
        estimate = database.get_pending_estimates_for_user(self.owner)[0]
        other = self.client(self.other, 'customer')
        response = other.post(f"/customer/estimates/{estimate['estimate_id']}/respond", data={'decision': 'Declined'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(database.get_staff_appointments()[0]['status'], 'Requested')
        self.assertNotIn(b'Broken lock', other.get('/customer').data)
        self.assertEqual(self.update('appointment', appointment_date='invalid', status='Confirmed').status_code, 303)
        self.assertEqual(database.get_staff_appointments()[0]['status'], 'Requested')
