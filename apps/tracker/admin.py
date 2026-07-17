from django.contrib import admin
from .models import UserCertification, UserGoal, Activity, CreditMapping

admin.site.register([UserCertification, UserGoal, Activity, CreditMapping])
