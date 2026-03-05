"""DRF API helpers."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView


class SecuredAPIView(APIView):
    """Base API view requiring an authenticated user."""

    permission_classes = (IsAuthenticated,)
