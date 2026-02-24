from django.db import models
import logging
import threading
import ipaddress
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.conf import settings
from active_directory.scripts.active_directory_query import active_directory_query
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from .constants import NO_LIMIT_LIMITER_NAME

logger = logging.getLogger(__name__)


def bug_report_attachment_upload_to(instance, filename):
    """Return a deterministic storage path for uploaded bug report files."""

    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base_name = slugify(Path(filename).stem) or "attachment"
    extension = Path(filename).suffix
    report_identifier = instance.bug_report_id or "unassigned"
    return f"bug_reports/{report_identifier}/{timestamp}_{base_name}{extension}"

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
            "username": username or (user.get_username() if getattr(user, "is_authenticated", False) else ""),
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

class MFAResetRecord(BaseModel):
    """High level audit log for successful MFA resets."""

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
    client = models.ForeignKey(
        "ADOrganizationalUnitLimiter",
        on_delete=models.SET_NULL,
        related_name="mfa_reset_records",
        null=True,
        blank=True,
    )
    client_label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "MFA reset record"
        verbose_name_plural = "MFA reset records"

    def __str__(self):
        performer = self.performed_by_display_name or self.performed_by_username or "unknown"
        return (
            f"{self.get_reset_type_display()} by {performer} for {self.target_user_principal_name}"
        )

    @classmethod
    def log_success(
        cls,
        *,
        performed_by,
        target_user_principal_name,
        reset_type,
        client=None,
        client_label="",
        attempt=None,
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
            client=client,
            client_label=client_label or "",
        )

class BugReportAttachment(BaseModel):
    """Files attached to bug reports."""

    bug_report = models.ForeignKey(
        BugReport,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=bug_report_attachment_upload_to)
    original_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["datetime_created"]
        verbose_name = "Bug report attachment"
        verbose_name_plural = "Bug report attachments"

    def __str__(self):
        return self.original_name or Path(self.file.name).name

class IPLimiter(BaseModel):
    """Restricts IT Staff API access to specific IP addresses."""

    ip_address = models.CharField(max_length=15)
    description = models.TextField(blank=True, default='')
    ad_groups = models.ManyToManyField('ADStaffSyncGroup', related_name='ip_limiters', blank=True)

    class Meta:
        verbose_name = "IP Limiter"
        verbose_name_plural = "IP Limiters"

    def __str__(self):
        return self.ip_address

    @staticmethod
    def _normalize_ip(ip_value):
        try:
            return str(ipaddress.IPv4Address(str(ip_value).strip()))
        except Exception:
            return None

    def clean(self):
        super().clean()
        normalized_ip = self._normalize_ip(self.ip_address)
        if not normalized_ip:
            raise ValidationError({"ip_address": _("Enter a valid IPv4 address.")})
        self.ip_address = normalized_ip

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class ADOrganizationalUnitLimiter(BaseModel):
    """This model represents an AD organizational unit limiter."""
    canonical_name = models.CharField(max_length=1024)
    distinguished_name = models.CharField(max_length=1024)
    ad_groups = models.ManyToManyField('ADStaffSyncGroup', related_name='ad_organizational_unit_limiters', blank=True)

    class Meta:
        verbose_name = "AD Organizational Unit Limiter"
        verbose_name_plural = "AD Organizational Unit Limiters"


    def save(self, *args, **kwargs):
        if not self.distinguished_name.startswith('OU=') or not self.distinguished_name.endswith(',DC=win,DC=dtu,DC=dk'):
            raise ValidationError("distinguished_name must start with 'OU=' and end with ',DC=win,DC=dtu,DC=dk'")
        if not self.canonical_name.startswith('win.dtu.dk/'):
            raise ValidationError("canonical_name must start with 'win.dtu.dk/'")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.canonical_name

    @classmethod
    def _normalize_canonical_prefixes(cls, prefixes):
        if not prefixes:
            return []

        normalized = []
        for prefix in prefixes:
            if not prefix:
                continue
            prefix = str(prefix).strip()
            if not prefix:
                continue
            normalized.append(prefix.rstrip('/'))

        # Preserve order while removing duplicates
        return list(dict.fromkeys(normalized))

    @classmethod
    def sync_default_limiters(cls, canonical_prefixes=None, *, delete_missing=None):
        """Synchronise OU limiters from Active Directory.

        - Enumerates all organizational units beneath the configured canonical prefixes.
        - Ensures each OU has a corresponding limiter entry.
        - Optionally removes database entries that no longer exist in AD.
        """

        if delete_missing is None:
            delete_missing = getattr(settings, 'AD_OU_LIMITER_DELETE_MISSING', True)

        if canonical_prefixes is None:
            canonical_prefixes = getattr(settings, 'AD_OU_LIMITER_BASES', ())

        canonical_prefixes = cls._normalize_canonical_prefixes(canonical_prefixes)
        if not canonical_prefixes:
            logger.info('No canonical prefixes configured for AD OU limiter sync.')
            return []

        from active_directory.services import execute_active_directory_query

        synced_limiters = []

        for canonical_prefix in canonical_prefixes:
            if not canonical_prefix:
                continue

            try:
                base_dn = ADStaffSyncGroup._canonical_to_distinguished_name(canonical_prefix)
            except Exception:
                logger.exception('Failed to convert canonical prefix %s to distinguished name', canonical_prefix)
                continue

            if not base_dn:
                logger.warning('Unable to derive distinguished name for canonical prefix %s', canonical_prefix)
                continue

            seen_dns = set()

            # Ensure the base OU itself is represented.
            try:
                with transaction.atomic():
                    limiter, _ = cls.objects.update_or_create(
                        distinguished_name=base_dn,
                        defaults={'canonical_name': canonical_prefix},
                    )
                synced_limiters.append(limiter)
                seen_dns.add(base_dn)
            except Exception:
                logger.exception('Failed to persist base OU limiter for %s', canonical_prefix)

            try:
                query_results = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter='(objectClass=organizationalUnit)',
                    search_attributes=['distinguishedName'],
                )
            except Exception:
                logger.exception('Failed to query Active Directory for OUs under %s', base_dn)
                continue

            for entry in query_results or []:
                dn_values = entry.get('distinguishedName') or entry.get('distinguishedname')
                if isinstance(dn_values, list):
                    distinguished_name = dn_values[0]
                else:
                    distinguished_name = dn_values

                if not distinguished_name:
                    continue

                distinguished_name = str(distinguished_name).strip()
                if not distinguished_name:
                    continue

                try:
                    canonical_name = ADStaffSyncGroup._dn_to_canonical(distinguished_name)
                except Exception:
                    logger.exception('Failed to convert distinguished name %s to canonical form', distinguished_name)
                    continue

                if not canonical_name or not canonical_name.startswith(f'{canonical_prefix}'):
                    continue

                try:
                    with transaction.atomic():
                        limiter, _ = cls.objects.update_or_create(
                            distinguished_name=distinguished_name,
                            defaults={'canonical_name': canonical_name},
                        )
                    synced_limiters.append(limiter)
                    seen_dns.add(distinguished_name)
                except IntegrityError:
                    logger.exception('Failed to persist OU limiter for %s', distinguished_name)
                except Exception:
                    logger.exception('Unexpected error while persisting OU limiter for %s', distinguished_name)

            if delete_missing:
                prefix_with_sep = f'{canonical_prefix}/'
                queryset = cls.objects.filter(canonical_name__startswith=prefix_with_sep)
                if seen_dns:
                    queryset = queryset.exclude(distinguished_name__in=seen_dns)

                removed_count, _ = queryset.delete()
                if removed_count:
                    logger.info('Removed %s OU limiters no longer present under %s', removed_count, canonical_prefix)

        return synced_limiters

class ADStaffSyncGroup(BaseModel):
    """
    This model represents an association between an AD group and a Django user.
    """
    canonical_name = models.CharField(max_length=255, unique=True, null=False)
    distinguished_name = models.CharField(max_length=255, unique=True, null=False)
    name = models.CharField(max_length=255, blank=True, default="")
    members = models.ManyToManyField(User, related_name='ad_group_members')

    def __str__(self):
        return self.name or self.canonical_name

    class Meta:
        verbose_name = "IT Staff API Permission (Django Data Model is ADStaffSyncGroup)"
        verbose_name_plural = "IT Staff API Permissions"


    def save(self, *args, **kwargs):
        if not self.distinguished_name.startswith('CN=') or not self.distinguished_name.endswith(',DC=win,DC=dtu,DC=dk'):
            raise ValidationError("distinguished_name must start with 'CN=' and end with ',DC=win,DC=dtu,DC=dk'")

        # if the canonical_name is empty or None, create it from the distinguished_name
        if not self.canonical_name:
            self.canonical_name = self._dn_to_canonical(self.distinguished_name)
            # CN=AIT-ADM-employees-29619,OU=SecurityGroups,OU=AIT,OU=DTUBasen,DC=win,DC=dtu,DC=dk
            # >> win.dtu.dk/DTUBasen/AIT/SecurityGroups/AIT-ADM-employees-29619

        if not self.canonical_name.startswith('win.dtu.dk/'):
            raise ValidationError("canonical_name must start with 'win.dtu.dk/'")

        derived_name = self._extract_name_from_canonical(self.canonical_name)
        if not self.name or self.name == self.canonical_name:
            self.name = derived_name

        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            # Ensure that newly created associations immediately reflect the current
            # membership of the backing AD group inside Django.
            self.sync_ad_group_members()

    @staticmethod
    def delete_unused_groups():
        unused_ad_groups = ADStaffSyncGroup.objects.filter(endpoints__isnull=True)
        unused_ad_groups.delete()

    def _create_or_update_django_users_if_not_exists(self, users):
        for user in users:
            # Defensive defaults
            user_principal_name = user.get('userPrincipalName', [''])
            user_principal_name = user_principal_name[0] if isinstance(user_principal_name, list) else user_principal_name
            sam_accountname = user.get('sAMAccountName', [''])
            sam_accountname = sam_accountname[0] if isinstance(sam_accountname, list) else sam_accountname

            try:
                if not user_principal_name or not user_principal_name.endswith('@dtu.dk'):
                    logger.debug("Skipping non-DTU or missing UPN: %s", user_principal_name)
                    continue

                username = (sam_accountname or '').lower()
                if not username:
                    logger.warning("Missing sAMAccountName for %s; cannot create user", user_principal_name)
                    continue

                first_name = user.get('givenName', [''])
                first_name = first_name[0] if isinstance(first_name, list) else first_name
                last_name = user.get('sn', [''])
                last_name = last_name[0] if isinstance(last_name, list) else last_name
                email = user_principal_name

                from app.scripts.create_or_update_django_user import create_or_update_django_user
                create_or_update_django_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    update_existing_user=False,
                )

            except Exception:
                logger.exception("Unexpected error while ensuring Django user for %s", user_principal_name)

class LimiterType(models.Model):
    """This model represents a type of limiter, associated only with the model type."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True, 
                                     limit_choices_to={'model__in': ['iplimiter', 'adorganizationalunitlimiter']})

    def __str__(self):
        return self.name

    @property
    def is_no_limit(self) -> bool:
        return (
            self.content_type_id is None
            and (self.name or "").strip().lower() == NO_LIMIT_LIMITER_NAME.lower()
        )

class Endpoint(BaseModel):
    path = models.CharField(max_length=255, unique=True)
    method = models.CharField(max_length=6, blank=True, default='')
    ad_groups = models.ManyToManyField('ADStaffSyncGroup', related_name='endpoints', blank=True)
    limiter_type = models.ForeignKey(LimiterType, on_delete=models.CASCADE, null=True, blank=True)
    

    def __str__(self):
        return f"{self.method} {self.path}" if self.method else self.path

    @property
    def allows_unrestricted_access(self) -> bool:
        limiter = self.limiter_type
        return limiter.is_no_limit if limiter else False

    def validate_and_get_ad_groups_for_user_access(self, user, endpoint_path):
        # Fetch the endpoint instance based on the provided path.
        try:
            endpoint = Endpoint.objects.get(path=endpoint_path)
        except Endpoint.DoesNotExist:
            return False, None  # No access since the endpoint does not exist.

        # Check if the user is in any group that is associated with the endpoint.
        user_groups = user.ad_group_members.all()
        access_granting_groups = []
        for group in user_groups:
            if endpoint.ad_groups.filter(pk=group.pk).exists():
                access_granting_groups.append(group)

        if access_granting_groups:
            return True, access_granting_groups  # Return True and the groups that grant access
        else:
            return False, None  # No access granted

class APIRequestLog(BaseModel):
    """Records metadata about inbound API calls for auditing in the admin."""

    AUTH_TYPE_SESSION = 'session'
    AUTH_TYPE_TOKEN = 'token'
    AUTH_TYPE_ANONYMOUS = 'anonymous'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_request_logs',
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    query_string = models.TextField(blank=True, default='')
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.FloatField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    auth_type = models.CharField(max_length=32, blank=True, default='')
    auth_token = models.CharField(max_length=128, blank=True, default='')
    action = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['datetime_created']),
            models.Index(fields=['path']),
            models.Index(fields=['status_code']),
        ]
        verbose_name = "API request log"
        verbose_name_plural = "API request logs"

    def __str__(self):
        status = self.status_code if self.status_code is not None else '—'
        return f"{self.method} {self.path} [{status}]"

class UserLoginLog(BaseModel):
    """Tracks MSAL login events for auditing."""

    AUTH_METHOD_MSAL = 'msal'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_events',
    )
    user_principal_name = models.CharField(max_length=255, blank=True, default='')
    auth_method = models.CharField(max_length=32, default=AUTH_METHOD_MSAL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    session_key = models.CharField(max_length=40, blank=True, default='')
    additional_info = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-datetime_created']
        verbose_name = "User login"
        verbose_name_plural = "User logins"
        indexes = [
            models.Index(fields=['datetime_created']),
            models.Index(fields=['user_principal_name']),
        ]

    def __str__(self):
        username = self.user_principal_name or getattr(self.user, 'username', 'unknown')
        return f"{username} via {self.auth_method} at {self.datetime_created:%Y-%m-%d %H:%M:%S}"

