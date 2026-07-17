import httpx
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from .models import UserCertification
from .forms import UserCertificationForm, ActivityForm, CredlyImportForm
from .credly import fetch_credly_badges, match_badges

User = get_user_model()


@login_required
def add_cert(request):
    form = UserCertificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        uc = form.save(commit=False)
        uc.user = request.user
        uc.save()
        messages.success(request, "Certification added.")
        return redirect("dashboard")
    return render(request, "dashboard/add_cert.html", {"form": form})


@login_required
def add_activity(request):
    form = ActivityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        act = form.save(commit=False)
        act.user = request.user
        act.save()
        messages.success(request, "Activity logged. Map its credits from the ledger.")
        return redirect("dashboard")
    return render(request, "dashboard/add_activity.html", {"form": form})


@login_required
def credly_import(request):
    """5.2: paste profile URL -> public badges.json -> user ticks matches -> rows created."""
    form = CredlyImportForm(request.POST or None)
    matches = None
    if request.method == "POST" and "confirm" in request.POST:
        import json as _json
        from apps.research.models import SourceSubmission
        created = queued = 0
        for raw in request.POST.getlist("import_badge"):
            try:
                b = _json.loads(raw)
            except ValueError:
                continue
            if not b.get("cert_id"):
                continue
            _, was_new = UserCertification.objects.get_or_create(
                user=request.user, certification_id=b["cert_id"],
                defaults={"earned_date": b.get("issued") or None,
                          "expiry_date": b.get("expires") or None,
                          "import_source": "credly"})
            created += was_new
        # Badges with no catalog match become inert research submissions (D16):
        # an Approver decides whether the cert is worth adding to the catalog.
        for raw in request.POST.getlist("queue_badge"):
            try:
                b = _json.loads(raw)
            except ValueError:
                continue
            name = (b.get("badge") or "").strip()
            if not name:
                continue
            _, was_new = SourceSubmission.objects.get_or_create(
                url=(b.get("template_url") or form.data.get("profile_url", ""))[:500],
                description=f"Credly badge with no catalog match: {name}"[:300],
                defaults={"submitted_by": request.user})
            queued += was_new
        msg = f"Imported {created} certification(s)."
        if queued:
            msg += f" Queued {queued} unmatched badge(s) for research."
        messages.success(request, msg)
        return redirect("dashboard")
    if request.method == "POST" and form.is_valid():
        try:
            badges = fetch_credly_badges(form.cleaned_data["profile_url"])
            matches = match_badges(badges)
        except httpx.HTTPError:
            messages.error(request, "Couldn't reach Credly. Endpoint is unofficial — "
                                    "try the badge-file upload instead.")
    return render(request, "dashboard/credly_import.html", {"form": form, "matches": matches})


@login_required
def request_gmail_scan(request):
    """SEC-013: the click queues; an Approver approves before anything runs."""
    from apps.research.models import GmailScanRequest
    if request.method != "POST":
        return redirect("dashboard")
    if not request.user.gmail_scan_enabled:
        messages.error(request, "Inbox scanning isn't enabled for your account yet.")
        return redirect("gmail_enrollment")
    open_states = (GmailScanRequest.Status.PENDING, GmailScanRequest.Status.APPROVED)
    if GmailScanRequest.objects.filter(user=request.user, status__in=open_states).exists():
        messages.info(request, "You already have a scan awaiting approval or execution.")
    else:
        GmailScanRequest.objects.create(user=request.user)
        messages.success(request, "Scan requested — it runs after an approver signs off.")
    return redirect("dashboard")


def ics_feed(request, token):
    """D5: tokenized read-only calendar of expirations. Token IS the auth (unguessable)."""
    try:
        user = User.objects.get(ics_token=token)
    except User.DoesNotExist:
        raise Http404
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CertSleuth//EN",
             "X-WR-CALNAME:CertSleuth expirations"]
    for uc in user.certs.select_related("certification").filter(expiry_date__isnull=False):
        d = uc.expiry_date.strftime("%Y%m%d")
        lines += ["BEGIN:VEVENT", f"UID:certsleuth-{uc.pk}@certsleuth.com",
                  f"DTSTART;VALUE=DATE:{d}", f"SUMMARY:{uc.certification} expires",
                  "BEGIN:VALARM", "TRIGGER:-P30D", "ACTION:DISPLAY",
                  f"DESCRIPTION:{uc.certification} expires in 30 days", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return HttpResponse("\r\n".join(lines), content_type="text/calendar")
