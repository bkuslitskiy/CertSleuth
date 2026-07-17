"""Offer submission (D12) + verification crawl queueing (SEC-007: inert until Approver)."""
from apps.offers.models import FreeOffer
from apps.research.models import SourceSubmission


def test_submit_offer_pends_and_queues_verification(client, user):
    client.force_login(user)
    resp = client.post("/offers/submit/", {
        "title": "Free CISSP exam voucher week",
        "url": "https://example.com/promo", "description": "Limited time."})
    assert resp.status_code == 302
    offer = FreeOffer.objects.get()
    assert offer.status == FreeOffer.Status.PENDING       # not live until reviewed
    assert offer.priority is False                        # plain user, no D12 priority
    sub = SourceSubmission.objects.get(url="https://example.com/promo")
    assert sub.status == SourceSubmission.Status.QUEUED   # inert until approver triggers
    assert "Verify free offer" in sub.description


def test_resubmitting_same_url_does_not_duplicate_queue(client, user):
    client.force_login(user)
    for title in ("Promo A", "Promo B"):
        client.post("/offers/submit/", {"title": title,
                                        "url": "https://example.com/promo"})
    assert FreeOffer.objects.count() == 2                 # both offers pend for review
    assert SourceSubmission.objects.count() == 1          # one verification entry per URL


def test_approver_submission_gets_priority(client, approver):
    client.force_login(approver)
    client.post("/offers/submit/", {"title": "ISC2 free training",
                                    "url": "https://example.com/isc2"})
    assert FreeOffer.objects.get().priority is True       # D12
