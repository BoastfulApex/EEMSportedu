"""
Tashqi tizim (LMS) bilan server-to-server aloqa uchun permission klasslar.
"""
import hashlib
import secrets

from django.utils import timezone
from rest_framework.permissions import BasePermission


class HasIntegrationScope(BasePermission):
    """
    `Authorization: Api-Key <prefix>.<secret>` sarlavhasini tekshiradi.

    View'da kerakli scope shunday belgilanadi:
        required_scope = 'attendance:read'
    """
    message = "Integratsiya kaliti yaroqsiz."

    def has_permission(self, request, view):
        from apps.superadmin.models import IntegrationClient

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Api-Key '):
            return False
        token = auth[len('Api-Key '):].strip()
        if '.' not in token:
            return False
        prefix, raw = token.split('.', 1)

        try:
            client = IntegrationClient.objects.get(key_prefix=prefix, is_active=True)
        except IntegrationClient.DoesNotExist:
            return False

        expected = client.key_hash
        actual   = hashlib.sha256(raw.encode()).hexdigest()
        if not secrets.compare_digest(expected, actual):
            return False

        # IP cheklovi (ro'yxat bo'sh bo'lsa — tekshirilmaydi)
        if client.allowed_ips:
            ip = self._client_ip(request)
            if ip not in client.allowed_ips:
                return False

        # Scope
        required = getattr(view, 'required_scope', None)
        if required and required not in (client.scopes or []):
            return False

        client.last_used = timezone.now()
        client.save(update_fields=['last_used'])
        request.integration_client = client
        return True

    @staticmethod
    def _client_ip(request):
        # Nginx orqasida ishlaydi — X-Forwarded-For ning BIRINCHI qiymati.
        # Nginx'siz to'g'ridan-to'g'ri ochiq bo'lsa bu sarlavha qalbakilashtirilishi
        # mumkin — u holda `allowed_ips` ni bo'sh qoldiring, faqat kalitga tayaning.
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
