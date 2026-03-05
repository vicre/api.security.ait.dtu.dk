from django.urls import path
from django.views.generic import RedirectView

from .views import MFAResetPageView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="mfa-reset", permanent=False), name="frontpage"),
    path("mfa-reset/", MFAResetPageView.as_view(), name="mfa-reset"),
    path(
        "mfa-reset/user/<str:user_principal_id>/delete-authentication/<str:authentication_id>/",
        MFAResetPageView.as_view(),
        name="delete-auth-method",
    ),
]
