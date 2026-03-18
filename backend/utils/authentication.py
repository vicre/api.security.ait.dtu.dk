"""Azure AD bearer token authentication for DRF."""

from __future__ import annotations

import os
from functools import lru_cache

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AzureAdTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()
        if not auth_header:
            return None

        if auth_header[0].lower() != self.keyword.lower().encode("utf-8"):
            return None

        if len(auth_header) != 2:
            raise exceptions.AuthenticationFailed("Invalid bearer token header.")

        try:
            token = auth_header[1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise exceptions.AuthenticationFailed("Invalid token encoding.") from exc

        claims = self._decode_claims(token)
        user = self._get_or_create_user(claims)
        return user, claims

    def _decode_claims(self, token: str) -> dict:
        audiences = tuple(getattr(settings, "AZURE_AD_ALLOWED_AUDIENCES", ()) or ())
        issuers = tuple(getattr(settings, "AZURE_AD_ALLOWED_ISSUERS", ()) or ())
        tenant_id = (getattr(settings, "AZURE_AD", {}) or {}).get("TENANT_ID") or os.getenv("AZURE_TENANT_ID")

        if _as_bool(os.getenv("AZURE_AD_BEARER_SKIP_SIGNATURE_VALIDATION")):
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                },
                algorithms=["RS256", "HS256"],
            )
        else:
            if not tenant_id:
                raise exceptions.AuthenticationFailed("Azure tenant configuration is missing.")

            signing_key = _get_jwk_client(tenant_id).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=list(audiences) if audiences else None,
                options={"verify_aud": bool(audiences)},
                leeway=leeway,
            )

        if issuers:
            issuer = claims.get("iss")
            if issuer not in issuers:
                raise exceptions.AuthenticationFailed("Bearer token issuer is not allowed.")

        return claims

    @staticmethod
    def _get_username_from_claims(claims: dict) -> str:
        candidate = (
            claims.get("preferred_username")
            or claims.get("upn")
            or claims.get("email")
            or claims.get("sub")
            or ""
        )
        candidate = str(candidate).strip()
        if not candidate:
            return ""
        if "@" in candidate:
            return candidate.split("@", 1)[0].lower()
        return candidate.lower()

    def _get_or_create_user(self, claims: dict):
        username = self._get_username_from_claims(claims)
        if not username:
            raise exceptions.AuthenticationFailed("Bearer token missing username claims.")

        email = str(
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
            or ""
        ).strip()
        first_name = str(claims.get("given_name") or "").strip()
        last_name = str(claims.get("family_name") or "").strip()

        user_model = get_user_model()
        user, _created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email[:254],
                "first_name": first_name[:150],
                "last_name": last_name[:150],
            },
        )
        return user


@lru_cache(maxsize=4)
def _get_jwk_client(tenant_id: str) -> jwt.PyJWKClient:
    jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    return jwt.PyJWKClient(jwks_url)
