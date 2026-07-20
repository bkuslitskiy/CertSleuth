"""SEC-021: login brute-force lockout via django-axes.

The test that would have caught the pre-SEC-021 gap: before axes, unlimited wrong-password
POSTs to /accounts/login/ were all accepted (200, form error) forever.
"""
import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

GOOD = "a-long-test-password"  # matches conftest.user fixture


def _login(client, email, password):
    return client.post(reverse("login"), {"username": email, "password": password})


def test_repeated_failures_lock_out_even_a_valid_login(client, user):
    limit = settings.AXES_FAILURE_LIMIT
    for i in range(limit):
        resp = _login(client, user.email, "wrong-password")
        # The first limit-1 attempts re-render the form (200); the limit-th trips the lock.
        expected = 200 if i < limit - 1 else settings.AXES_HTTP_RESPONSE_CODE
        assert resp.status_code == expected

    # Still locked: even the correct password is refused, proving the block is attempt-based,
    # not credential-based.
    resp = _login(client, user.email, GOOD)
    assert resp.status_code == settings.AXES_HTTP_RESPONSE_CODE  # 429
    assert b"Too many sign-in attempts" in resp.content


def test_success_before_the_limit_logs_in_and_resets(client, user):
    _login(client, user.email, "wrong-password")          # one failure
    resp = _login(client, user.email, GOOD)               # then a good login
    assert resp.status_code == 302                         # redirected to the dashboard
    assert resp.headers["Location"] == reverse("dashboard")
