from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .forms import SignupForm, WaitlistForm, EnrollmentRequestForm
from .models import Invite, RegistrationMode, WaitlistEntry, EnrollmentTask

User = get_user_model()


def signup(request, token=None):
    """Invite-token signup always works; open signup only when toggled and under cap (D1)."""
    invite = get_object_or_404(Invite, token=token, accepted_at__isnull=True) if token else None
    mode = RegistrationMode.current()
    under_cap = User.objects.filter(is_active=True).count() < settings.WAITLIST_THRESHOLD
    if invite is None:
        if not mode.open_registration:
            return render(request, "registration/closed.html")
        if not under_cap:
            return _waitlist(request)
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if invite:
                user.email = invite.email
            user.save()
            if invite:
                invite.accepted_at = timezone.now()
                invite.save(update_fields=["accepted_at"])
            login(request, user)
            return redirect("dashboard")
    else:
        form = SignupForm(initial={"email": invite.email} if invite else None)
    return render(request, "registration/signup.html", {"form": form, "invite": invite})


def _waitlist(request):
    form = WaitlistForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        WaitlistEntry.objects.get_or_create(email=form.cleaned_data["email"])
        messages.success(request, "You're on the waitlist. We'll email you when a spot opens.")
        return redirect("login")
    return render(request, "registration/waitlist.html", {"form": form})


@login_required
def request_gmail_enrollment(request):
    """D25 flow: capture Gmail address -> admin console queue. Scan stays locked until done."""
    task = EnrollmentTask.objects.filter(user=request.user).first()
    form = EnrollmentRequestForm(request.POST or None, initial={"gmail_address": request.user.email})
    if request.method == "POST" and form.is_valid() and task is None:
        EnrollmentTask.objects.create(user=request.user, gmail_address=form.cleaned_data["gmail_address"])
        messages.success(request, "Request received. Inbox scanning unlocks once enrollment is confirmed.")
        return redirect("dashboard")
    return render(request, "registration/enrollment.html", {"form": form, "task": task})
