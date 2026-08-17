# Release 1 security audit

Audit date: **2026-08-15**

## Scope

- tracked files and Git history for common private-key, token and credential
  signatures;
- Django environment, CORS, CSRF, JWT cookie and production security flags;
- pinned Python dependencies against the Python Packaging Advisory Database;
- migration consistency and critical authentication/configuration tests.

## Results

- No private keys, access tokens or high-confidence production credentials were
  found in tracked files or Git history.
- `.env` has never been tracked and is ignored by Git. `.env.example`, CI and
  Docker contain development-only placeholders.
- `SECRET_KEY` has no source-code fallback and must be provided by environment.
  Examples require a value of at least 50 random characters.
- CORS credentials use explicit origins; wildcard origins are disabled. CSRF
  middleware and trusted origins are configured. JWT cookies are HttpOnly,
  SameSite=Lax, rotated and blacklisted on logout.
- HTTPS redirect, secure cookies and HSTS can be configured entirely through
  environment variables. HSTS subdomain/preload flags remain opt-in because
  enabling them before every subdomain supports HTTPS can be harmful.
- Vulnerable packages identified by `pip-audit` were upgraded. The unused
  `xhtml2pdf` dependency, which had no published fixed version, was removed.
  The final dependency audit reports no known vulnerabilities.
- Django was upgraded from 4.2.20 to the patched 5.2 LTS line. The obsolete
  Django 4.2 template monkeypatch was removed and legacy password generation
  now uses Python's cryptographically secure `secrets` module.

## Accepted deployment warning

`manage.py check --deploy` reports `security.W019` because
`X_FRAME_OPTIONS=SAMEORIGIN`. This is intentional: same-origin framing is
required for Release 1 SCORM content. Cross-origin framing remains blocked, and
SCORM content responses additionally apply the configured frame-ancestor
policy.

## Repeatable checks

```powershell
python -m pip_audit -r requirements.txt --progress-spinner off
python -m pip check
python manage.py check
python manage.py check --deploy
python manage.py test config.tests api.tests accounts.tests
```

Production deployment must provide a unique random `SECRET_KEY`, HTTPS-only
origins and secure-cookie/HSTS flags appropriate for its verified domains.
