import httpx
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import UserCertification
from .forms import (UserCertificationForm, ActivityForm, CredlyImportForm,
                    MSLearnImportForm, AccredibleImportForm, OpenBadgeUploadForm,
                    LinkedInCSVForm)
from .credly import fetch_credly_badges, match_badges
from . import importers

User = get_user_model()

# Non-Credly import sources (spec 5.3-5.5), all sharing importers.confirm_import.
# kind "url" fetches a pasted link; kind "file" parses an upload.
IMPORT_SOURCES = {
    "microsoft": {"label": "Microsoft Learn", "kind": "url",
                  "form": MSLearnImportForm, "fetch": importers.microsoft_fetch},
    "accredible": {"label": "Accredible", "kind": "url",
                   "form": AccredibleImportForm, "fetch": importers.accredible_fetch},
    "openbadges": {"label": "Open Badges", "kind": "file",
                   "form": OpenBadgeUploadForm, "fetch": importers.openbadge_parse},
    "linkedin": {"label": "LinkedIn", "kind": "file",
                 "form": LinkedInCSVForm, "fetch": importers.linkedin_parse},
}


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
def import_source(request, source):
    """Generic import flow for spec 5.3-5.5 sources. Lookup/upload renders a preview of
    catalog matches; confirm writes matched rows and queues unmatched (importers.py)."""
    cfg = IMPORT_SOURCES.get(source)
    if cfg is None:
        raise Http404
    if request.method == "POST" and "confirm" in request.POST:
        created, queued = importers.confirm_import(request)
        msg = f"Imported {created} certification(s)."
        if queued:
            msg += f" Queued {queued} unmatched credential(s) for research."
        messages.success(request, msg)
        return redirect("dashboard")
    form = cfg["form"](request.POST or None, request.FILES or None)
    matches = None
    if request.method == "POST" and form.is_valid():
        try:
            matches = importers.match_catalog(cfg["fetch"](form))
        except (httpx.HTTPError, ValueError, KeyError) as e:
            messages.error(request, f"Couldn't read that {cfg['label']} credential: {e}")
    return render(request, "dashboard/import_preview.html",
                  {"form": form, "matches": matches, "label": cfg["label"],
                   "source": source, "kind": cfg["kind"]})


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


@login_required
def plan_toggle(request, cert_id):
    """Favorite/unfavorite a catalog cert as a planned certification (UserGoal).
    POST-only; bounces back to where the user was."""
    from apps.catalog.models import Certification
    from .models import UserGoal
    if request.method != "POST":
        return redirect("catalog_providers")
    cert = Certification.objects.filter(pk=cert_id).first()
    if cert is None:
        raise Http404
    goal, created = UserGoal.objects.get_or_create(user=request.user, certification=cert)
    if not created:
        goal.delete()
        messages.info(request, f"Removed {cert.name} from your planned certifications.")
    else:
        messages.success(request, f"Added {cert.name} to your planned certifications.")
    return redirect(request.POST.get("next")
                    or reverse("catalog_cert", args=[cert.provider.slug, cert.slug]))


@login_required
def gmail_scan_run(request):
    """Kick off the consent round-trip for the user's APPROVED scan (SEC-013: only an
    approved request gets this far; SEC-020: token handled inside one request cycle)."""
    from apps.research.models import GmailScanRequest
    from . import gmail
    if not gmail.is_configured():
        messages.error(request, "Inbox scanning isn't configured on this server.")
        return redirect("dashboard")
    scan = (GmailScanRequest.objects
            .filter(user=request.user, status=GmailScanRequest.Status.APPROVED)
            .order_by("-created_at").first())
    if scan is None:
        messages.error(request, "No approved scan to run — request one first.")
        return redirect("dashboard")
    return redirect(gmail.auth_url(request, scan))


@login_required
def gmail_scan_callback(request):
    """Google redirects here with ?code=&state=. The token is exchanged, used for one
    bounded pass, and discarded within this request (never stored, SEC-003). GET renders
    the preview; the confirm POST reuses the shared importer confirm handler."""
    from django.core import signing as _signing
    from apps.research.models import GmailScanRequest
    from . import gmail
    if request.method == "POST" and "confirm" in request.POST:
        created, queued = importers.confirm_import(request)
        msg = f"Imported {created} certification(s) from your inbox."
        if queued:
            msg += f" Queued {queued} unmatched credential(s) for research."
        messages.success(request, msg)
        return redirect("dashboard")
    code, state = request.GET.get("code"), request.GET.get("state")
    if not code or not state:
        messages.error(request, "Google didn't complete the consent hand-off.")
        return redirect("dashboard")
    try:
        scan_pk = gmail.read_state(state, request.user)
        scan = GmailScanRequest.objects.get(pk=scan_pk, user=request.user)
        token = gmail.exchange_code(
            code, request.build_absolute_uri(reverse("gmail_scan_callback")))
        items = gmail.run_scan(scan, token)
        del token                                   # one pass, then gone (SEC-003)
    except _signing.BadSignature:
        messages.error(request, "That consent link is stale or not yours — start again.")
        return redirect("dashboard")
    except (httpx.HTTPError, gmail.GmailNotConfigured, ValueError,
            GmailScanRequest.DoesNotExist) as e:
        messages.error(request, f"Scan failed before reading any mail: {e}")
        return redirect("dashboard")
    matches = importers.match_catalog(items)
    return render(request, "dashboard/import_preview.html",
                  {"form": None, "matches": matches, "label": "Gmail",
                   "source": "gmail", "kind": "gmail"})


def ics_feed(request, token):
    """D5: tokenized read-only calendar of expirations. Token IS the auth (unguessable)."""
    try:
        user = User.objects.get(ics_token=token)
    except User.DoesNotExist:
        raise Http404
    # RLS-safety (SEC-008): this view is anonymous, so RLSSessionMiddleware sets no
    # certsleuth.user_id. Under the non-owner app role the cert query would then return
    # nothing — scope it to the token's user here. No-op on sqlite / owner connections.
    from django.db import connection
    if connection.vendor == "postgresql":
        with connection.cursor() as cur:
            cur.execute("SELECT set_config('certsleuth.user_id', %s, false)", [str(user.pk)])
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
