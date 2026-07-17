"""SEC-012: role confers the review surfaces; plain users get nothing extra."""


def test_approver_can_open_review_admin_pages(client, approver):
    client.force_login(approver)
    for url in ("/admin/research/stagedchange/", "/admin/research/sourcesubmission/",
                "/admin/research/gmailscanrequest/", "/admin/catalog/source/",
                "/admin/offers/freeoffer/", "/admin/accounts/enrollmenttask/"):
        assert client.get(url).status_code == 200, url


def test_approver_cannot_manage_users(client, approver):
    client.force_login(approver)
    resp = client.get("/admin/accounts/user/")
    assert resp.status_code == 403


def test_plain_user_has_no_admin_perms(user):
    assert not user.has_perm("research.view_stagedchange")
    assert not user.has_module_perms("research")


def test_superuser_counts_as_approver(db):
    """createsuperuser leaves role='user'; the review-queue nav link keys on is_approver."""
    from django.contrib.auth import get_user_model
    su = get_user_model().objects.create_superuser(
        username="root", email="root@example.com", password="a-long-test-password")
    assert su.is_approver
