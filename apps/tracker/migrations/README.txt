Run `python manage.py makemigrations` before first migrate to generate 0001_initial
for every app; 0002_rls here depends on tracker.0001_initial existing.
RLS enforcement additionally requires: (1) app DB role is NOT the table owner/superuser,
(2) a middleware SET of certsleuth.user_id per request — see security.md SEC-008 notes.
