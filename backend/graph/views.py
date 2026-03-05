"""Graph endpoints required for MFA reset workflows."""

from __future__ import annotations

import logging
from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response

from utils.api import SecuredAPIView

from .services import (
    execute_delete_software_mfa_method,
    execute_get_user,
    execute_list_user_authentication_methods,
    execute_microsoft_authentication_method,
    execute_phone_authentication_method,
)

logger = logging.getLogger(__name__)


def _extract_graph_error(response: Optional[Any]) -> str:
    if response is None:
        return "No response received from Microsoft Graph."

    try:
        data = response.json()
    except ValueError:
        text = getattr(response, "text", "")
        return text or "Microsoft Graph returned an error without a body."

    if not isinstance(data, dict):
        return str(data)

    error = data.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
        if code and message:
            return f"{code}: {message}"
        if message:
            return message
        if code:
            return code

    return str(data)


class GetUserView(SecuredAPIView):
    """Return information about a Microsoft Entra ID user."""

    def get(self, request, user: str) -> Response:
        select_param = request.GET.get("$select")
        payload, status_code = execute_get_user(user, select_param)
        return Response(payload, status=status_code)


class ListUserAuthenticationMethodsView(SecuredAPIView):
    """List all authentication methods configured for a user."""

    def get(self, request, user_id__or__user_principalname: str) -> Response:
        payload, status_code = execute_list_user_authentication_methods(
            user_id__or__user_principalname
        )
        return Response(payload, status=status_code)


class _BaseGraphDeleteView(SecuredAPIView):
    def _error_response(self, response: Optional[Any], message: str, status_code: Optional[int]) -> Response:
        detail = _extract_graph_error(response)
        return Response(
            {
                "status": "error",
                "message": message,
                "details": detail,
            },
            status=status_code or status.HTTP_502_BAD_GATEWAY,
        )


class DeleteSoftwareMfaView(_BaseGraphDeleteView):
    """Delete a software based MFA method for a user."""

    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        software_oath_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_delete_software_mfa_method(
                user_id__or__user_principalname,
                software_oath_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete software MFA for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {"status": "error", "message": "Failed to delete software MFA."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )


class DeleteMfaView(_BaseGraphDeleteView):
    """Delete a Microsoft Authenticator method for a user."""

    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        microsoft_authenticator_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_microsoft_authentication_method(
                user_id__or__user_principalname,
                microsoft_authenticator_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete Microsoft authenticator method for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {"status": "error", "message": "Failed to delete authentication method."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )


class DeletePhoneView(_BaseGraphDeleteView):
    """Delete a phone based MFA method for a user."""

    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        phone_authenticator_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_phone_authentication_method(
                user_id__or__user_principalname,
                phone_authenticator_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete phone authentication method for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {
                    "status": "error",
                    "message": "Failed to delete phone authentication method.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )
