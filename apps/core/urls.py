from django.urls import path
from . import views

# Name stays "dashboard" (LOGIN_REDIRECT_URL + every redirect("dashboard") resolves here);
# the view now branches to the public landing for anonymous visitors.
urlpatterns = [path("", views.home, name="dashboard")]
