from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.staleness import staleness
from apps.tracker.models import UserCertification, Activity
from apps.offers.models import FreeOffer


@login_required
def dashboard(request):
    held = (UserCertification.objects.filter(user=request.user)
            .select_related("certification__provider").order_by("expiry_date"))
    for uc in held:
        rule = uc.certification.current_rule
        uc.rule = rule
        uc.chip = staleness(rule.last_verified_at) if rule else "red"
    offers = FreeOffer.objects.filter(status="active").order_by("-created_at")[:5]
    recent = Activity.objects.filter(user=request.user).order_by("-date")[:5]
    from apps.research.models import GmailScanRequest
    has_approved_scan = GmailScanRequest.objects.filter(
        user=request.user, status=GmailScanRequest.Status.APPROVED).exists()
    # Planned certs (UserGoal) with their compatibility against current holdings.
    from apps.catalog.compat import compatibility
    from apps.tracker.models import UserGoal
    planned = []
    goals = (UserGoal.objects.filter(user=request.user)
             .select_related("certification__provider"))
    for g in goals:
        cert = g.certification
        rule = cert.current_rule
        planned.append({"goal": g, "cert": cert, "rule": rule,
                        "compat": compatibility(cert, held)})
    return render(request, "dashboard/index.html",
                  {"held": held, "offers": offers, "recent": recent,
                   "has_approved_scan": has_approved_scan, "planned": planned})
