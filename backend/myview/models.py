from __future__ import annotations

import logging

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def bug_report_attachment_upload_to(instance, filename):  # pragma: no cover - kept for migration compatibility
    _ = instance
    return str(filename or "")


class BaseModel(models.Model):
    datetime_created = models.DateTimeField(auto_now_add=True)
    datetime_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserActivityLog(BaseModel):
    class EventType(models.TextChoices):
        LOGIN = "login", _("Login")
        API_REQUEST = "api_request", _("API request")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    username = models.CharField(max_length=150, blank=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    was_successful = models.BooleanField(default=False)
    request_method = models.CharField(max_length=16, blank=True)
    request_path = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    extra = models.JSONField(blank=True, null=True, default=dict)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "User activity log entry"
        verbose_name_plural = "User activity log entries"

    def __str__(self):
        label = self.get_event_type_display()
        if self.username:
            username = self.username
        elif self.user and hasattr(self.user, "get_username"):
            username = self.user.get_username()
        else:
            username = "unknown"
        return f"{label} for {username} at {self.datetime_created:%Y-%m-%d %H:%M:%S}"

    @staticmethod
    def _extract_ip_address(request):
        if not request:
            return None

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        return request.META.get("REMOTE_ADDR") or None

    @classmethod
    def _build_common_payload(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        status_code=None,
        message="",
        extra=None,
    ):
        payload = {
            "user": user if getattr(user, "is_authenticated", False) else None,
            "username": username
            or (user.get_username() if getattr(user, "is_authenticated", False) else ""),
            "was_successful": was_successful,
            "status_code": status_code,
            "message": message or "",
        }

        if request is not None:
            payload["request_method"] = getattr(request, "method", "")[:16]
            payload["request_path"] = getattr(request, "path", "")[:512]
            payload["ip_address"] = cls._extract_ip_address(request)

        if extra is not None:
            payload["extra"] = extra

        return payload

    @classmethod
    def log_login(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        message="",
        extra=None,
    ):
        payload = cls._build_common_payload(
            user=user,
            username=username,
            request=request,
            was_successful=was_successful,
            message=message,
            extra=extra,
        )
        payload["event_type"] = cls.EventType.LOGIN
        return cls.objects.create(**payload)

    @classmethod
    def log_api_request(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        status_code=None,
        message="",
        extra=None,
    ):
        if request is None and user is None and not username:
            return None

        payload = cls._build_common_payload(
            user=user,
            username=username,
            request=request,
            was_successful=was_successful,
            status_code=status_code,
            message=message,
            extra=extra,
        )
        payload["event_type"] = cls.EventType.API_REQUEST
        return cls.objects.create(**payload)


class MFAResetAttempt(BaseModel):
    """Audit trail for individual and bulk MFA reset attempts."""

    class ResetType(models.TextChoices):
        INDIVIDUAL = "individual", _("Individual")
        BULK = "bulk", _("Bulk")

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="mfa_reset_attempts",
        null=True,
        blank=True,
    )
    performed_by_username = models.CharField(max_length=150, blank=True)
    target_user_principal_name = models.EmailField(max_length=255)
    reset_type = models.CharField(max_length=32, choices=ResetType.choices)
    was_successful = models.BooleanField(default=False)
    method_id = models.CharField(max_length=255, blank=True)
    method_type = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "MFA reset attempt"
        verbose_name_plural = "MFA reset attempts"

    @classmethod
    def log_attempt(
        cls,
        *,
        performed_by,
        target_user_principal_name,
        reset_type,
        was_successful,
        method_id="",
        method_type="",
        details="",
    ):
        user = performed_by if getattr(performed_by, "is_authenticated", False) else None
        username = user.get_username() if user else str(performed_by or "")
        return cls.objects.create(
            performed_by=user,
            performed_by_username=username[:150],
            target_user_principal_name=target_user_principal_name,
            reset_type=reset_type,
            was_successful=was_successful,
            method_id=method_id or "",
            method_type=method_type or "",
            details=details or "",
        )


class MFAResetRecord(BaseModel):
    """High-level audit log for successful MFA resets."""

    attempt = models.ForeignKey(
        MFAResetAttempt,
        on_delete=models.SET_NULL,
        related_name="reset_records",
        null=True,
        blank=True,
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="mfa_reset_records",
        null=True,
        blank=True,
    )
    performed_by_username = models.CharField(max_length=150, blank=True)
    performed_by_display_name = models.CharField(max_length=255, blank=True)
    performed_by_user_principal_name = models.EmailField(max_length=255, blank=True)
    target_user_principal_name = models.EmailField(max_length=255)
    reset_type = models.CharField(max_length=32, choices=MFAResetAttempt.ResetType.choices)
    was_successful = models.BooleanField(default=False)
    client_label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "MFA reset record"
        verbose_name_plural = "MFA reset records"

    def __str__(self):
        performer = self.performed_by_display_name or self.performed_by_username or "unknown"
        return f"{self.get_reset_type_display()} by {performer} for {self.target_user_principal_name}"

    @classmethod
    def log_success(
        cls,
        *,
        performed_by,
        target_user_principal_name,
        reset_type,
        attempt=None,
        client_label="",
    ):
        user = performed_by if getattr(performed_by, "is_authenticated", False) else None
        username = ""
        display_name = ""
        user_principal_name = ""

        if user:
            username = user.get_username() or ""
            display_name = user.get_full_name() or ""
            user_principal_name = getattr(user, "email", "") or username
        elif performed_by:
            username = str(performed_by)

        return cls.objects.create(
            attempt=attempt,
            performed_by=user,
            performed_by_username=username,
            performed_by_display_name=display_name,
            performed_by_user_principal_name=user_principal_name,
            target_user_principal_name=target_user_principal_name,
            reset_type=reset_type,
            was_successful=True,
            client_label=client_label or "",
        )


class APIRequestLog(BaseModel):
    """Records metadata about inbound API calls for auditing in the admin."""

    AUTH_TYPE_SESSION = "session"
    AUTH_TYPE_TOKEN = "token"
    AUTH_TYPE_ANONYMOUS = "anonymous"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_request_logs",
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    query_string = models.TextField(blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.FloatField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    auth_type = models.CharField(max_length=32, blank=True, default="")
    auth_token = models.CharField(max_length=128, blank=True, default="")
    action = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-datetime_created"]
        indexes = [
            models.Index(fields=["datetime_created"]),
            models.Index(fields=["path"]),
            models.Index(fields=["status_code"]),
        ]
        verbose_name = "API request log"
        verbose_name_plural = "API request logs"

    def __str__(self):
        status = self.status_code if self.status_code is not None else "-"
        return f"{self.method} {self.path} [{status}]"


class UserLoginLog(BaseModel):
    """Tracks MSAL login events for auditing."""

    AUTH_METHOD_MSAL = "msal"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_events",
    )
    user_principal_name = models.CharField(max_length=255, blank=True, default="")
    auth_method = models.CharField(max_length=32, default=AUTH_METHOD_MSAL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    session_key = models.CharField(max_length=40, blank=True, default="")
    additional_info = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "User login"
        verbose_name_plural = "User logins"
        indexes = [
            models.Index(fields=["datetime_created"]),
            models.Index(fields=["user_principal_name"]),
        ]

    def __str__(self):
        username = self.user_principal_name or getattr(self.user, "username", "unknown")
        timestamp = timezone.localtime(self.datetime_created)
        return f"{username} via {self.auth_method} at {timestamp:%Y-%m-%d %H:%M:%S}"
