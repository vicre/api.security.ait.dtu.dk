import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from hubcert.services import HubCertServiceResponse
from hubcert.views import HubCertShareEventsView
from myview.models import ADGroupAssociation, IPLimiter


class HubCertViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(username="tester", password="pass")
        self.allowed_ip = "130.225.91.231"

    def _create_response(self, payload) -> HubCertServiceResponse:
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        response.headers["Content-Type"] = "application/json"
        return HubCertServiceResponse(response=response)

    def _setup_ip_limiter(self):
        with patch.object(ADGroupAssociation, "sync_ad_group_members", return_value=None):
            group = ADGroupAssociation.objects.create(
                canonical_name="win.dtu.dk/Test/Group",
                distinguished_name="CN=Test,DC=win,DC=dtu,DC=dk",
            )
        group.members.add(self.user)
        limiter = IPLimiter.objects.create(ip_address=self.allowed_ip)
        limiter.ad_groups.add(group)
        return limiter

    def test_share_events_filtered_by_ip_limiters(self):
        self._setup_ip_limiter()
        payload = [
            {"ip": self.allowed_ip, "uuid": "keep"},
            {"ip": "192.0.2.1", "uuid": "drop"},
        ]
        service_response = self._create_response(payload)

        request = self.factory.get("/hub.cert.dk/shares/v2/test-share")
        force_authenticate(request, user=self.user)

        with patch("hubcert.views.HubCertClient.get_share_events", return_value=service_response):
            response = HubCertShareEventsView.as_view()(request, share_id="test-share")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["ip"], self.allowed_ip)

