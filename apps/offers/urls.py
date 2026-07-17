from django.urls import path
from . import views

urlpatterns = [
    path("", views.offer_list, name="offer_list"),
    path("submit/", views.submit_offer, name="submit_offer"),
]
