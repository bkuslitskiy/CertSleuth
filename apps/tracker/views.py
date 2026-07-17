import httpx
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from .models import UserCertification, Activity
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
        created = 0
        for raw in request.POST.getlist("import_badge"):
            b = _json.loads(raw)
            if not b.get("cert_id"):
                continue
            _, was_new = UserCertification.objects.get_or_create(
                user=request.user, certification_id=b["cert_id"],
                defaults={"earned_date": b.get("issued") or None,
                          "expiry_date": b.get("expires") or None,
                          "import_source": "credly"})
            created += was_new
        messages.success(request, f"Imported {created} certification(s).")
        return redirect("dashboard")
    if request.method == "POST" and form.is_valid():
        try:
            badges = fetch_credly_badges(form.cleaned_data["profile_url"])
            matches = match_badges(badges)
        except httpx.HTTPError:
            messages.error(request, "Couldn't reach Credly. Endpoint is unofficial — "
                                    "try the badge-file upload instead.")
    return render(request, "dashboard/credly_import.html", {"form": form, "matches": matches})


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
