# LockService

## Start

```sh
source .venv/bin/activate
pip install Flask
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

```sh
python -m unittest discover -s tests -v
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
