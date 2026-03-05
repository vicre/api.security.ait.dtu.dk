"""Access control middleware used to protect the myview application."""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from urllib.parse import urlparse

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from rest_framework import exceptions
from rest_framework.authtoken.models import Token

from utils.authentication import AzureAdTokenAuthentication


logger = logging.getLogger(__name__)


class AccessControlMiddleware(MiddlewareMixin):
    """Allow only authenticated sessions or valid Authorization headers."""

    _BASE_WHITELIST = (
        "/",
        "/favicon.ico",
        "/login/",
        "/logout/",
        "/auth/callback",
        "/auth/callback/",
        "/media/",
        "/healthz/",
    )

    def __init__(self, get_response):
        super().__init__(get_response)
        self.whitelist_paths = self._build_whitelist()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalise the request path to ensure consistent matching."""

        clean_path = (path or "/").split("?")[0]
        if not clean_path.endswith("/"):
            clean_path += "/"
        return clean_path

    def _build_whitelist(self) -> Sequence[str]:
        """Collect all paths that should bypass access control."""

        paths = {self._normalise_whitelist_entry(p) for p in self._BASE_WHITELIST}

        default_admin = self._normalise_whitelist_entry("admin/")
        if default_admin:
            paths.add(default_admin)

        custom_admin = self._normalise_whitelist_entry(getattr(settings, "ADMIN_URL_PATH", "admin/"))
        if custom_admin:
            paths.add(custom_admin)

        static_candidates = (
            getattr(settings, "STATIC_URL", ""),
            getattr(settings, "STATICFILES_URL", ""),
        )
        paths.update(filter(None, (self._normalise_whitelist_entry(p) for p in static_candidates)))

        # Normalise and sort to keep logging stable.
        return tuple(sorted(filter(None, paths)))

    @staticmethod
    def _normalise_whitelist_entry(path: Optional[str]) -> Optional[str]:
        """Ensure whitelist prefixes start with a slash and end with a trailing slash."""

        if not path:
            return None

        parsed = urlparse(path)
        candidate = parsed.path if parsed.scheme else path
        if not candidate.startswith("/"):
            candidate = "/" + candidate
        if not candidate.endswith("/"):
            candidate += "/"
        return candidate

    def _is_whitelisted_path(self, normalised_path: str) -> bool:
        for candidate in self.whitelist_paths:
            if normalised_path == candidate:
                return True
            if candidate == "/" or normalised_path == "/":
                continue
            if normalised_path.startswith(candidate):
                return True
        return False

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _authenticate_by_token(self, request, token_key: str) -> bool:
        token_key = (token_key or "").strip()
        if not token_key:
            return False

        try:
            user = Token.objects.get(key=token_key).user
        except Token.DoesNotExist:
            logger.info("Invalid token access attempt path=%s", request.path)
            return False

        request.user = user
        setattr(request, "_cached_user", user)
        return True

    def _authenticate_by_bearer(self, request) -> bool:
        authenticator = getattr(self, "_azure_ad_authenticator", None)
        if authenticator is None:
            authenticator = AzureAdTokenAuthentication()
            self._azure_ad_authenticator = authenticator

        try:
            result = authenticator.authenticate(request)
        except exceptions.AuthenticationFailed as exc:
            logger.info("Azure AD bearer token rejected path=%s reason=%s", request.path, exc)
            return False
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Unexpected Azure AD token validation failure path=%s", request.path)
            return False

        if not result:
            logger.info("Azure AD bearer authentication returned no user path=%s", request.path)
            return False

        user, _claims = result
        request.user = user
        setattr(request, "_cached_user", user)
        return True

    def _authenticate_authorization_header(self, request, header_value: str) -> tuple[bool, int, str]:
        """Authenticate request using the HTTP Authorization header."""

        header_value = (header_value or "").strip()
        if not header_value:
            return False, 401, "Authorization header is empty."

        scheme, _, credentials = header_value.partition(" ")
        scheme_lower = scheme.lower().strip()
        token_value = credentials.strip() if credentials else ""

        # Raw token header without explicit scheme.
        if not credentials:
            if scheme_lower == "bearer":
                return False, 401, "Invalid bearer token header."
            if self._authenticate_by_token(request, scheme):
                return True, 200, ""
            return False, 403, "Invalid API token."

        if scheme_lower == "bearer":
            if self._authenticate_by_bearer(request):
                return True, 200, ""
            return False, 401, "Invalid bearer token provided."

        if scheme_lower in {"token", "apikey", "api-key"}:
            if self._authenticate_by_token(request, token_value):
                return True, 200, ""
            return False, 403, "Invalid API token."

        return False, 401, "Unsupported authorization scheme."

    # ------------------------------------------------------------------
    # Middleware entry point
    # ------------------------------------------------------------------
    def __call__(self, request):
        normalised_path = self.normalize_path(request.path)

        if self._is_whitelisted_path(normalised_path):
            return self.get_response(request)

        header_value = request.META.get("HTTP_AUTHORIZATION")
        if header_value:
            authenticated, status_code, message = self._authenticate_authorization_header(request, header_value)
            if not authenticated:
                logger.info(
                    "Authorization failed path=%s status=%s reason=%s",
                    request.path,
                    status_code,
                    message,
                )
                return JsonResponse({"error": message}, status=status_code)

        if request.user.is_authenticated:
            return self.get_response(request)

        return redirect("/login/")
