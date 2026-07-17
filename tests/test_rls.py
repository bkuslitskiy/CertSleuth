"""RLS second-layer isolation (SEC-008). Postgres-only: the policies live in a raw-SQL
migration (tracker/0002_rls); sqlite dev runs skip. Django connects as the table owner,
which bypasses RLS — so, exactly like production (SEC-008: the app uses a NON-owner role),
these tests SET LOCAL ROLE to a privilege-granted non-owner role before asserting.

Run locally against a throwaway Postgres:
    DATABASE_URL=postgres://test:test@localhost:5433/test DJANGO_SECRET_KEY=x \
        pytest tests/test_rls.py
"""
import pytest
from django.db import connection

pytestmark = pytest.mark.skipif(connection.vendor != "postgresql",
                                reason="RLS requires Postgres")

NON_OWNER = "rls_test_role"


def _as_non_owner(cur):
    """Create + assume a non-owner role subject to RLS (rolled back with the test txn)."""
    cur.execute(f"DROP ROLE IF EXISTS {NON_OWNER}")
    cur.execute(f"CREATE ROLE {NON_OWNER}")
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON tracker_usercertification "
                f"TO {NON_OWNER}")
    cur.execute(f"SET LOCAL ROLE {NON_OWNER}")


def _set_user(cur, pk):
    cur.execute("SELECT set_config('certsleuth.user_id', %s, true)", [str(pk)])


def _count(cur):
    cur.execute("SELECT count(*) FROM tracker_usercertification")
    return cur.fetchone()[0]


def test_rls_isolates_by_user(db, user, django_user_model):
    eve = django_user_model.objects.create_user(
        username="eve", email="eve@example.com", password="a-long-test-password")
    from apps.catalog.models import Provider, Certification
    from apps.tracker.models import UserCertification
    p = Provider.objects.create(name="X", slug="x")
    c = Certification.objects.create(provider=p, name="Y", slug="y")
    UserCertification.objects.create(user=user, certification=c)  # boris owns one row

    with connection.cursor() as cur:
        _as_non_owner(cur)
        try:
            _set_user(cur, eve.pk)
            assert _count(cur) == 0        # eve sees none of boris's rows (isolation)
            _set_user(cur, user.pk)
            assert _count(cur) == 1        # boris sees his own (not blanket denial)
        finally:
            cur.execute("RESET ROLE")
