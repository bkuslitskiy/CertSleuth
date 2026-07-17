from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django import forms
from .models import FreeOffer


class OfferForm(forms.ModelForm):
    class Meta:
        model = FreeOffer
        fields = ("title", "description", "url", "provider", "starts", "ends")


@login_required
def offer_list(request):
    offers = FreeOffer.objects.filter(status=FreeOffer.Status.ACTIVE).order_by("ends")
    return render(request, "dashboard/offers.html", {"offers": offers})


@login_required
def submit_offer(request):
    form = OfferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        offer = form.save(commit=False)
        offer.submitted_by = request.user
        offer.priority = request.user.is_approver  # D12
        offer.save()
        messages.success(request, "Offer submitted for review.")
        return redirect("offer_list")
    return render(request, "dashboard/submit_offer.html", {"form": form})
