"""Views exposing hub.cert.dk shares endpoints behind our security stack."""

from __future__ import annotations

import logging
from typing import Any, Dict

from django.http import HttpResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response

from utils.api import SecuredAPIView

from .services import HubCertClient, HubCertConfigurationError, HubCertRequestError

logger = logging.getLogger(__name__)

SHARE_ID_PARAM = openapi.Parameter(
    "share_id",
    in_=openapi.IN_PATH,
    description="Hub CERT share identifier (UUID).",
    type=openapi.TYPE_STRING,
    required=True,
)

QUERY_LIMIT_PARAM = openapi.Parameter(
    "limit",
    in_=openapi.IN_QUERY,
    description="Maximum number of events to return.",
    type=openapi.TYPE_INTEGER,
    required=False,
)

QUERY_FILTER_PARAM = openapi.Parameter(
    "filter",
    in_=openapi.IN_QUERY,
    description="Hub CERT filter expression for narrowing down events.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_START_PARAM = openapi.Parameter(
    "start",
    in_=openapi.IN_QUERY,
    description="ISO-8601 start timestamp.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_END_PARAM = openapi.Parameter(
    "end",
    in_=openapi.IN_QUERY,
    description="ISO-8601 end timestamp.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_FORMAT_PARAM = openapi.Parameter(
    "format",
    in_=openapi.IN_QUERY,
    description="Requested upstream format (json or csv).",
    type=openapi.TYPE_STRING,
    required=False,
)


class HubCertShareEventsView(SecuredAPIView):
    """Proxy hub.cert.dk share events behind the authentication middleware."""

    query_parameters = [
        QUERY_LIMIT_PARAM,
        QUERY_FILTER_PARAM,
        QUERY_START_PARAM,
        QUERY_END_PARAM,
        QUERY_FORMAT_PARAM,
    ]

    def _build_params(self, request) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if not hasattr(request, "query_params"):
            return params
        for key, value in request.query_params.items():
            if value is None or value == "":
                continue
            params[key] = value
        return params

    def _proxy_request(self, request, share_id: str) -> Response:
        params = self._build_params(request)
        try:
            service_response = HubCertClient.get_share_events(str(share_id), params=params)
        except HubCertConfigurationError as exc:
            logger.error("Hub CERT configuration error: %s", exc)
            return Response(
                {"detail": "Hub CERT integration is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except HubCertRequestError as exc:
            logger.warning("Hub CERT upstream failure share_id=%s error=%s", share_id, exc)
            return Response(
                {"detail": "Unable to contact hub.cert.dk."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        upstream = service_response.response
        content_type = upstream.headers.get("Content-Type", "")

        if "json" in content_type:
            try:
                data = upstream.json()
            except ValueError:
                data = {"detail": upstream.text or ""}
            return Response(data, status=upstream.status_code)

        # Default to returning the upstream payload untouched for non-JSON content.
        return HttpResponse(
            upstream.content,
            status=upstream.status_code,
            content_type=content_type or "text/plain",
        )

    @swagger_auto_schema(manual_parameters=[SHARE_ID_PARAM, *query_parameters])
    def get(self, request, share_id: str, *args: Any, **kwargs: Any) -> Response:  # type: ignore[override]
        return self._proxy_request(request, share_id)
