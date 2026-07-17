from django import forms
from .models import UserCertification, Activity


class UserCertificationForm(forms.ModelForm):
    class Meta:
        model = UserCertification
        fields = ("certification", "earned_date", "expiry_date", "cert_number", "evidence_url")
        widgets = {"earned_date": forms.DateInput(attrs={"type": "date"}),
                   "expiry_date": forms.DateInput(attrs={"type": "date"})}


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("title", "kind", "date", "hours", "evidence_url")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class CredlyImportForm(forms.Form):
    profile_url = forms.URLField(label="Credly profile URL",
                                 help_text="Your profile must be public.")
