from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.response import Response

from leads.models import Lead
from leads.serializers import LeadCreateSerializer, LeadDetailSerializer


class LeadCreateView(CreateAPIView):
    """
    POST /api/leads/

    Creates a lead and triggers async qualification via Celery.
    Returns the created lead (status: "new") immediately.

    Production note: protect this endpoint with authentication and rate
    limiting before deploying publicly — each request triggers LLM usage.
    """
    serializer_class = LeadCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        return Response(LeadDetailSerializer(lead).data, status=status.HTTP_201_CREATED)


class LeadDetailView(RetrieveAPIView):
    """
    GET /api/leads/:id/

    Returns the full lead with qualification result and per-tool-call audit log.
    """
    serializer_class = LeadDetailSerializer
    queryset = Lead.objects.prefetch_related("audit_logs")
    lookup_field = "id"
