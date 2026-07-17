from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username", "timezone")


class WaitlistForm(forms.Form):
    email = forms.EmailField()


class EnrollmentRequestForm(forms.Form):
    gmail_address = forms.EmailField(help_text="The Google account whose inbox you'll scan.")
