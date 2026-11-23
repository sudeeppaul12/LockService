# LockService

## Dependencies

**Python 3.9+** is required. The only third-party packages are:

| Package | Version | Purpose |
|   ---   |   ---   |   ---   |  
| Flask | 3.1.3 | Web framework and session management |
| Werkzeug | 3.1.9 | Password hashing (`generate_password_hash` / `check_password_hash`) |

Everything else (`sqlite3`, `json`, `datetime`, `hmac`, `secrets`, etc.) is part of the Python standard library — no additional installs needed beyond the two above.

Install all dependencies at once:

```sh
pip install -r requirements.txt
```

Or set up an isolated virtual environment first (recommended):

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start

```sh
source .venv/bin/activate
export SECRET_KEY='replace-with-a-long-random-secret'
export STAFF_INVITE_CODE='replace-with-a-private-staff-invitation-code'
flask --app app run --debug
```

Open http://127.0.0.1:5000/register to use Create Account. Customer accounts
require a name, email, password and matching confirmation. Staff accounts also
require the configured invitation code. Keep SECRET_KEY stable between restarts
so signed login sessions remain valid.

Registration saves name, normalized email, password hash and role in the SQLite
`users` table in `lockservice.db`. SQLite generates a unique `user_id` primary key;
`database.create_user()` returns that key. Password confirmation and invitation
codes are validation inputs and are not saved. Plain passwords are never saved.

After registration, sign in with the same email and password. Successful login
stores the saved `user_id` in Flask's signed session and redirects to the correct
dashboard. The key identifies the account internally; it is not a login password.
Tables are initialized on startup with either Flask CLI or `python app.py`;
existing records are preserved. The database is excluded from version control.

## Test

The test suite lives in the `tests/` directory and is split across three files:

- **`test_auth.py`** — covers registration and login: password hashing, email normalization, session creation, and redirect behavior after sign-in.
- **`test_backend.py`** — covers database operations and Flask route logic end-to-end: user creation, vehicle management, appointment creation, estimate flow, and service completion.
- **`test_workflow.py`** — covers the full staff/customer lifecycle: staff reviewing requests, setting appointments, sending estimates, customers accepting or rejecting, and marking services complete or canceled.

Each test file spins up a disposable SQLite database in a temp directory, so no setup or teardown of a real database is needed. Tests are fully isolated and safe to run repeatedly.

To run the full suite:

```sh
python -m unittest discover -s tests -v
```

To run a single file:

```sh
python -m unittest tests.test_auth -v
python -m unittest tests.test_backend -v
python -m unittest tests.test_workflow -v
```

Staff invitation codes can also be stored as a JSON array in
`instance/staff_invites.json` (excluded from Git). Each code is reusable; remove
a code from the file and restart Flask to revoke it. Restart after adding codes.
The STAFF_INVITE_CODE environment variable remains supported.

## Staff/customer workflow

On `/staff`, review incoming requests, save appointment dates and confirmations,
send or revise estimates, and mark services In Progress or Completed. Completing
service requires work performed and final cost; a service-history record and the
Completed status are saved together. Completed/canceled requests cannot be edited.
Revised estimates return to Pending for fresh customer approval.

Customers refresh `/customer` to see staff updates, including canceled/completed
appointments. Completed work, notes and final costs appear on `/customer/history`.
Staff refresh `/staff` to see new requests and customer estimate decisions.
Updates are saved immediately; dashboards do not automatically refresh.
