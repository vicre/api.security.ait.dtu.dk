import json
import os
from urllib.parse import quote

from django.test import SimpleTestCase
from dotenv import dotenv_values

from graph.scripts._graph_get_bearertoken import _generate_new_token
from graph.scripts._http import graph_request


class ProductionGraphRegistrationReadOnlyTests(SimpleTestCase):
    """Optional live test to validate the app registration against Graph."""

    @staticmethod
    def _as_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _discover_env_file() -> str | None:
        candidates = [
            os.getenv("APP_ENV_FILE"),
            "/workspace/backend/.env",
            os.path.join(os.getcwd(), ".env"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _token_for_test(self) -> str | None:
        """Acquire a token, preferring explicit test credentials."""

        env_file_values = {}
        if self._as_bool(os.getenv("GRAPH_PRODUCTION_TEST_USE_DOTENV_CREDENTIALS"), True):
            env_file = self._discover_env_file()
            if env_file:
                env_file_values = {k: v for k, v in dotenv_values(env_file).items() if v}

        tenant_id = (
            os.getenv("GRAPH_PRODUCTION_TEST_TENANT_ID")
            or env_file_values.get("AZURE_TENANT_ID")
            or os.getenv("AZURE_TENANT_ID")
        )
        client_id = (
            os.getenv("GRAPH_PRODUCTION_TEST_CLIENT_ID")
            or env_file_values.get("GRAPH_CLIENT_ID")
            or os.getenv("GRAPH_CLIENT_ID")
        )
        client_secret = (
            os.getenv("GRAPH_PRODUCTION_TEST_CLIENT_SECRET")
            or env_file_values.get("GRAPH_CLIENT_SECRET")
            or os.getenv("GRAPH_CLIENT_SECRET")
        )
        graph_resource = (
            os.getenv("GRAPH_PRODUCTION_TEST_RESOURCE")
            or env_file_values.get("GRAPH_RESOURCE")
            or os.getenv("GRAPH_RESOURCE")
            or "https://graph.microsoft.com"
        ).rstrip("/")

        explicit_creds_available = all([tenant_id, client_id, client_secret])
        if not explicit_creds_available:
            return _generate_new_token()

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        response = graph_request(
            "POST",
            token_url,
            data={
                "resource": graph_resource,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=20,
        )
        if response.status_code != 200:
            return None

        try:
            payload = response.json()
        except ValueError:
            return None
        return payload.get("access_token")

    def test_graph_registration_supports_get_requests(self):
        if os.getenv("RUN_PRODUCTION_GRAPH_READ_TEST") != "1":
            self.skipTest("Set RUN_PRODUCTION_GRAPH_READ_TEST=1 to run live production Graph checks.")

        target_url = (os.getenv("GRAPH_PRODUCTION_TEST_GET_URL") or "").strip()
        if not target_url:
            test_user = (os.getenv("GRAPH_PRODUCTION_TEST_USER_PRINCIPAL_NAME") or "").strip()
            self.assertTrue(
                test_user,
                "Set GRAPH_PRODUCTION_TEST_USER_PRINCIPAL_NAME or GRAPH_PRODUCTION_TEST_GET_URL.",
            )
            target_url = (
                "https://graph.microsoft.com/v1.0/users/"
                f"{quote(test_user, safe='@')}/authentication/methods"
            )

        token = self._token_for_test()
        self.assertTrue(token, "Failed to acquire a Graph access token from app registration credentials.")

        response = graph_request(
            "GET",
            target_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=20,
        )

        body_preview = response.text[:1000]
        self.assertEqual(
            response.status_code,
            200,
            (
                f"Graph GET failed with status {response.status_code} for {target_url}. "
                f"Response preview: {body_preview}"
            ),
        )

        payload = response.json()
        self.assertIsInstance(payload, dict)
        # The default MFA-read URL returns {'value': [...]}
        if target_url.endswith("/authentication/methods"):
            self.assertIn("value", payload)
            self.assertIsInstance(payload["value"], list)
        else:
            # For custom GET URLs, at least ensure JSON parsing worked.
            json.dumps(payload)
