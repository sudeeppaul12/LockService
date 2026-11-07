import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
from app import app
from werkzeug.security import check_password_hash


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_patch = patch.object(database, 'DB_PATH', str(Path(self.temp.name) / 'test.db'))
        self.database_patch.start()
        database.init_db()
        app.config.update(TESTING=True, STAFF_INVITE_CODE='test-invite')
        self.client = app.test_client()

    def tearDown(self):
        self.database_patch.stop()
        self.temp.cleanup()

    def register(self, **changes):
        values = dict(name='Test Customer', email='Customer@example.com',
                      password='password123', confirm_password='password123', role='customer')
        values.update(changes)
        return self.client.post('/register', data=values)

    def test_persisted_account_logs_in_with_database_key(self):
        self.assertEqual(self.register().status_code, 302)
        database.init_db()  # Startup preserves saved accounts.
        user = database.get_user_by_email('CUSTOMER@example.com')
        self.assertIsInstance(user['user_id'], int)
        self.assertNotEqual(user['password_hash'], 'password123')
        self.assertTrue(check_password_hash(user['password_hash'], 'password123'))
        response = self.client.post('/login', data={'email': 'CUSTOMER@example.com', 'password': 'password123'})
        self.assertEqual(response.location, '/customer')
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], user['user_id'])
        self.assertEqual(self.client.get('/customer').status_code, 200)

    def test_invalid_duplicate_and_staff_accounts(self):
        self.register()
        self.assertIn(b'already exists', self.register(email='CUSTOMER@example.com').data)
        self.assertIn(b'Passwords do not match', self.register(email='other@example.com', confirm_password='wrong').data)
        self.assertIsNone(database.get_user_by_email('other@example.com'))
        self.assertIn(b'invitation code', self.register(email='staff@example.com', role='staff').data)
        self.assertIsNone(database.get_user_by_email('staff@example.com'))
        self.assertEqual(self.register(email='staff@example.com', role='staff', invite_code='test-invite').status_code, 302)
        self.assertIn(b'Invalid email or password', self.client.post('/login', data={'email': 'customer@example.com', 'password': 'wrong'}).data)
        self.assertEqual(self.client.post('/login', data={'email': 'staff@example.com', 'password': 'password123'}).location, '/staff')

    def test_create_user_returns_primary_key(self):
        key = database.create_user('Customer', 'key@example.com', 'test-hash')
        self.assertEqual(key, database.get_user_by_email('key@example.com')['user_id'])
