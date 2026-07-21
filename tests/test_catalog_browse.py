"""User-facing catalog browse + compatibility (spec: browse by provider; renewal
interaction, shared CEU pool, tier relation vs the user's own certs)."""
import pytest

from apps.catalog.compat import compatibility, tier_rank
from apps.catalog.models import Certification, Provider, RenewalRule, UpgradePath
from apps.tracker.models import UserCertification

pytestmark = pytest.mark.django_db


@pytest.fixture
def scrum(db):
    p = Provider.objects.create(name="Scrum Alliance", slug="scrum-alliance",
                                ceu_currency="SEU")
    csm = Certification.objects.create(provider=p, name="Certified ScrumMaster",
                                       slug="csm", level="Foundational")
    acsm = Certification.objects.create(provider=p, name="Advanced CSM",
                                        slug="a-csm", level="Advanced")
    RenewalRule.objects.create(certification=csm, ceu_required=20, cycle_years=2,
                               renewal_fee_usd=100)
    RenewalRule.objects.create(certification=acsm, ceu_required=30, cycle_years=2)
    UpgradePath.objects.create(from_cert=csm, to_cert=acsm, effect="renews")
    return p, csm, acsm


def _hold(user, cert):
    return UserCertification.objects.create(user=user, certification=cert)


# --- compat unit -------------------------------------------------------------

def test_tier_rank_keywords():
    assert tier_rank("Foundational") == 0
    assert tier_rank("Associate") == 1
    assert tier_rank("Professional") == 2
    assert tier_rank("Advanced") == 2
    assert tier_rank("Specialty") is None      # orthogonal, never ranked
    assert tier_rank("") is None


def test_earning_higher_cert_renews_held_lower(user, scrum):
    _, csm, acsm = scrum
    _hold(user, csm)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert compat["renews_yours"] == [csm]
    assert compat["lower_level_than"] == []
    # tier is its own independent axis: A-CSM ranks above the held CSM
    assert compat["tiers"] == [{"cert": csm, "relation": "higher"}]


def test_viewing_lower_cert_reads_as_tier_not_renewal(user, scrum):
    # Holding A-CSM and viewing CSM: the note is "lower level than one you already
    # have" (from levels), NOT "your A-CSM renews this" (outbound edges don't display).
    _, csm, acsm = scrum
    _hold(user, acsm)
    compat = compatibility(csm, UserCertification.objects.filter(user=user))
    assert compat["lower_level_than"] == [acsm]
    assert compat["renews_yours"] == []
    assert compat["covered_other"] == []
    assert compat["tiers"] == []


def test_multi_cert_renewal_combines_into_one_statement(user, scrum):
    # Holding CSM + CSPO, viewing A-CSPO: one combined "renews your CSM + CSPO".
    p, csm, acsm = scrum
    cspo = Certification.objects.create(provider=p, name="Certified Scrum Product Owner",
                                        slug="cspo", level="Foundational")
    acspo = Certification.objects.create(provider=p, name="Advanced CSPO",
                                         slug="a-cspo", level="Advanced")
    UpgradePath.objects.create(from_cert=csm, to_cert=acspo, effect="renews")
    UpgradePath.objects.create(from_cert=cspo, to_cert=acspo, effect="renews")
    _hold(user, csm)
    _hold(user, cspo)
    compat = compatibility(acspo, UserCertification.objects.filter(user=user))
    assert set(c.slug for c in compat["renews_yours"]) == {"csm", "cspo"}


def test_cross_track_lower_tier_cert_still_shows_renewal(user, scrum):
    # The CSPO scenario: holding CSM + A-CSM, browsing CSPO. Separate track, lower
    # Scrum Alliance tier than A-CSM — but earning it renews both held certs
    # (symmetric edges). Renewal and tier must BOTH display; neither wins.
    p, csm, acsm = scrum
    cspo = Certification.objects.create(provider=p, name="Certified Scrum Product Owner",
                                        slug="cspo", level="Foundational")
    # Scrum Alliance renewal is symmetric across tracks: edges exist in both directions.
    UpgradePath.objects.create(from_cert=csm, to_cert=cspo, effect="renews")
    UpgradePath.objects.create(from_cert=acsm, to_cert=cspo, effect="renews")
    UpgradePath.objects.create(from_cert=cspo, to_cert=acsm, effect="renews")
    _hold(user, csm)
    _hold(user, acsm)
    compat = compatibility(cspo, UserCertification.objects.filter(user=user))
    assert set(c.slug for c in compat["renews_yours"]) == {"csm", "a-csm"}   # renewal axis
    assert compat["lower_level_than"] == [acsm]                             # tier axis
    assert compat["tiers"] == [{"cert": csm, "relation": "same"}]
    assert compat["covered_other"] == []      # the reverse renews edge displays nothing


def test_shared_ceu_same_provider_only(user, scrum):
    p, csm, acsm = scrum
    other = Provider.objects.create(name="Other", slug="other")
    oc = Certification.objects.create(provider=other, name="X", slug="x")
    RenewalRule.objects.create(certification=oc, ceu_required=10, cycle_years=1)
    _hold(user, csm)
    _hold(user, oc)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert compat["shared_ceu"] == [csm]        # cross-provider cert not claimed
    assert compat["ceu_currency"] == "SEU"


def test_partial_credit_shows_toward_held_cert(user, scrum):
    # earning the browsed cert grants fixed CEUs toward a cert the user already holds
    p, csm, acsm = scrum
    UpgradePath.objects.create(from_cert=csm, to_cert=acsm, effect="partial_credit",
                               ceu_amount=15)
    _hold(user, csm)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert compat["partial_credit_toward_yours"] == [{"cert": csm, "ceu_amount": 15}]
    assert compat["renews_yours"] == [csm]  # the fixture's separate renews edge, unaffected


def test_partial_credit_does_not_read_as_full_renewal(user, scrum):
    # a held cert that only grants partial credit toward the browsed cert must not
    # appear in the full-renewal list — that would overstate what was actually earned
    p, csm, acsm = scrum
    other = Certification.objects.create(provider=p, name="CSPO", slug="cspo")
    UpgradePath.objects.create(from_cert=other, to_cert=acsm, effect="partial_credit",
                               ceu_amount=10)
    _hold(user, other)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert other not in compat["renews_yours"]
    assert compat["partial_credit_toward_yours"] == [{"cert": other, "ceu_amount": 10}]


def test_exam_based_cert_shares_no_ceu_pool(user, scrum):
    # a cert with a rule but no CEU requirement (e.g. AWS re-exam) claims no shared pool
    p, csm, _ = scrum
    exam = Certification.objects.create(provider=p, name="Examy", slug="examy")
    RenewalRule.objects.create(certification=exam, cycle_years=3)   # no ceu_required
    _hold(user, csm)
    compat = compatibility(exam, UserCertification.objects.filter(user=user))
    assert compat["shared_ceu"] == []


def test_prereq_held_cert_makes_lower_cert_redundant(user, scrum):
    # Scrum Alliance shape: A-CSM REQUIRES CSM. Holding A-CSM and viewing CSM should say
    # "your A-CSM already required this", not merely "lower level" — you cannot hold
    # A-CSM without having had CSM, so earning CSM now is moot.
    _, csm, acsm = scrum
    UpgradePath.objects.create(from_cert=csm, to_cert=acsm, effect="requires")
    _hold(user, acsm)
    compat = compatibility(csm, UserCertification.objects.filter(user=user))
    assert compat["required_by_yours"] == [acsm]
    assert compat["lower_level_than"] == []     # prereq statement replaces the tier note
    assert compat["renews_yours"] == []


def test_lower_tier_without_prereq_stays_a_tier_note(user, scrum):
    # CompTIA shape: Security+ does NOT require Network+. Holding Security+ and viewing
    # Network+ is a plain lower-tier note (pursuable, rarely sensible) — no redundancy claim.
    comptia = Provider.objects.create(name="CompTIA", slug="comptia", ceu_currency="CEU")
    netplus = Certification.objects.create(provider=comptia, name="Network+",
                                           slug="network", level="Entry")
    secplus = Certification.objects.create(provider=comptia, name="Security+",
                                           slug="security", level="Professional")
    _hold(user, secplus)
    compat = compatibility(netplus, UserCertification.objects.filter(user=user))
    assert compat["lower_level_than"] == [secplus]
    assert compat["required_by_yours"] == []


def test_viewing_upgrade_shows_prereq_met(user, scrum):
    # Holding CSM and viewing A-CSM: "this requires your CSM — you qualify", alongside
    # any renewal fact. Orthogonal axes, both display.
    _, csm, acsm = scrum
    UpgradePath.objects.create(from_cert=csm, to_cert=acsm, effect="requires")
    _hold(user, csm)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert compat["prereqs_met"] == [csm]
    assert compat["renews_yours"] == [csm]      # the fixture's renews edge, unaffected


def test_keyword_only_lower_tier_joins_lower_level_statement(user, scrum):
    # No upgrade edge between them, but keyword levels rank: still "lower level than".
    p, csm, _ = scrum
    pro = Certification.objects.create(provider=p, name="Some Professional Thing",
                                       slug="pro-thing", level="Professional")
    _hold(user, pro)
    compat = compatibility(csm, UserCertification.objects.filter(user=user))
    assert compat["lower_level_than"] == [pro]
    assert compat["tiers"] == []


def test_keyword_higher_tier_reported_per_held_cert(user, scrum):
    _, csm, acsm = scrum
    p = csm.provider
    plain = Certification.objects.create(provider=p, name="Plain Foundational",
                                         slug="plain", level="Foundational")
    _hold(user, csm)
    _hold(user, plain)
    compat = compatibility(acsm, UserCertification.objects.filter(user=user))
    assert sorted(t["cert"].slug for t in compat["tiers"]) == ["csm", "plain"]
    assert all(t["relation"] == "higher" for t in compat["tiers"])


def test_holds_it_flag(user, scrum):
    _, csm, _ = scrum
    _hold(user, csm)
    assert compatibility(csm, UserCertification.objects.filter(user=user))["holds_it"]


# --- views -------------------------------------------------------------------

def test_browse_requires_login(client, scrum):
    assert client.get("/catalog/").status_code == 302        # -> login


def test_provider_list_shows_providers_with_certs(client, user, scrum):
    Provider.objects.create(name="Empty Co", slug="empty")   # no certs -> hidden
    client.force_login(user)
    resp = client.get("/catalog/")
    assert b"Scrum Alliance" in resp.content
    assert b"Empty Co" not in resp.content


def test_provider_page_lists_certs_with_rule_summary(client, user, scrum):
    client.force_login(user)
    resp = client.get("/catalog/scrum-alliance/")
    assert b"Certified ScrumMaster" in resp.content
    assert b"20 SEU" in resp.content
    assert b"$100" in resp.content


def test_cert_page_shows_compat_sections(client, user, scrum):
    _, csm, acsm = scrum
    _hold(user, csm)
    client.force_login(user)
    resp = client.get("/catalog/scrum-alliance/a-csm/")
    body = resp.content.decode()
    assert 'data-compat="renews-yours"' in body
    assert "Certified ScrumMaster" in body
    assert 'data-compat="shared-ceu"' in body


def test_cert_page_no_interactions_message(client, user, scrum):
    client.force_login(user)                                  # holds nothing
    resp = client.get("/catalog/scrum-alliance/csm/")
    assert b"No known interactions" in resp.content


def test_unknown_slugs_404(client, user, scrum):
    client.force_login(user)
    assert client.get("/catalog/nope/").status_code == 404
    assert client.get("/catalog/scrum-alliance/nope/").status_code == 404


def test_provider_page_sorts_by_abbreviation_and_shows_column(client, user, scrum):
    p, csm, acsm = scrum
    csm.abbreviation = "CSM"
    csm.save()
    acsm.abbreviation = "A-CSM"
    acsm.save()
    client.force_login(user)
    body = client.get("/catalog/scrum-alliance/").content.decode()
    assert "Abbrev." in body
    assert body.index("A-CSM") < body.index(">CSM<")   # A-CSM alphabetizes first
