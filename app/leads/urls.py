from django.urls import path
from leads.views import LeadCreateView, LeadDetailView

urlpatterns = [
    path("leads/", LeadCreateView.as_view(), name="lead-create"),
    path("leads/<uuid:id>/", LeadDetailView.as_view(), name="lead-detail"),
]
