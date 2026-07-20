from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from apps.core.staleness import staleness
from apps.tracker.models import UserCertification, Activity
from apps.offers.models import FreeOffer


def home(request):
    """Root: the personal dashboard for signed-in users, the public landing for everyone else."""
    if request.user.is_authenticated:
        return dashboard(request)
    return landing(request)


def landing(request):
    """Public marketing landing (SEC: no per-user data). Providers + copy + a waitlist form.
    Renders fine with an empty catalog — prod has no providers until one is loaded in."""
    from apps.accounts.forms import WaitlistForm
    from apps.accounts.models import WaitlistEntry
    from apps.catalog.models import Provider
    form = WaitlistForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        WaitlistEntry.objects.get_or_create(email=form.cleaned_data["email"])
        messages.success(request, "You're on the waitlist — we'll email you when a spot opens.")
        return redirect("dashboard")
    providers = (Provider.objects.annotate(n_certs=Count("certifications"))
                 .filter(n_certs__gt=0).order_by("name"))
    return render(request, "landing.html", {"providers": providers, "form": form})


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
