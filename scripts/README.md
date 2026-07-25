# Development scripts

Run these utilities from the project root:

```powershell
python scripts/check_user.py
python scripts/list_data.py
```

The scripts use the same Django settings and database as `manage.py`.

Some utilities modify local data:

- `add_lecture.py`
- `reset_mama.py`
- `reset_pass.py`

Review their hard-coded test values before running them. They are development
helpers, not automated tests or production commands.
