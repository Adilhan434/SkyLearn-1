# Development scripts

Run these utilities from the project root:

```powershell
python scripts/check_user.py
python scripts/check_auth.py
python scripts/check_login_api.py
python scripts/list_data.py
```

The scripts use the same Django settings and database as `manage.py`.

Some utilities modify local data:

- `add_lecture.py`
- `reset_mama.py`
- `reset_pass.py`

Review their hard-coded test values before running them. They are development
helpers, not automated tests or production commands.

The `check_*.py` files are manual diagnostics. Their names intentionally do
not start with `test_`, so Django's test discovery does not execute them.
