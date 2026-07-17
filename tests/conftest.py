import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="boris", email="boris@example.com", password="a-long-test-password")


@pytest.fixture
def approver(db):
    return get_user_model().objects.create_user(
        username="rev", email="rev@example.com", password="a-long-test-password",
        role="approver", is_staff=True)
