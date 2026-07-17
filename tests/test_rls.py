"""RLS second-layer isolation (SEC-008). Postgres-only: policies live in a raw-SQL
migration; sqlite dev runs skip. A cross-tenant SELECT under the app role must return 0."""
import pytest
from django.db import connection

pytestmark = pytest.mark.skipif(connection.vendor != "postgresql",
                                reason="RLS requires Postgres")


def test_rls_blocks_cross_tenant(db, user, django_user_model):
    other = django_user_model.objects.create_user(username="eve", email="eve@example.com",
                                                  password="a-long-test-password")
    from apps.catalog.models import Provider, Certification
    p = Provider.objects.create(name="X", slug="x")
    c = Certification.objects.create(provider=p, name="Y", slug="y")
    from apps.tracker.models import UserCertification
    UserCertification.objects.create(user=user, certification=c)
    with connection.cursor() as cur:
        cur.execute("SET certsleuth.user_id = %s", [other.pk])
        cur.execute("SELECT count(*) FROM tracker_usercertification")
        # Under the app role with RLS enforced, eve sees nothing of boris's rows.
        assert cur.fetchone()[0] == 0
