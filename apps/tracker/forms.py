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


class MSLearnImportForm(forms.Form):
    transcript_url = forms.URLField(
        label="Microsoft Learn transcript share URL",
        help_text="On Learn: Profile → Transcript → Share link. Your public profile "
                  "does not list certifications, so the share link is required.")


class AccredibleImportForm(forms.Form):
    credential_url = forms.URLField(
        label="Credential URL",
        help_text="A credential.net link (or a branded Accredible domain, e.g. "
                  "credentials.databricks.com). Covers Google Cloud, Databricks, and more.")


class OpenBadgeUploadForm(forms.Form):
    badge_file = forms.FileField(
        label="Open Badge file",
        help_text="A .json, .png, or .svg Open Badge (2.0 or 3.0). Works for private "
                  "profiles — Badgr, Canvas Credentials, and any Open Badges issuer.")


class LinkedInCSVForm(forms.Form):
    csv_file = forms.FileField(
        label="LinkedIn Certifications.csv",
        help_text="From your LinkedIn data export (Settings → Data privacy → Get a copy "
                  "of your data). Upload the Certifications.csv file.")
