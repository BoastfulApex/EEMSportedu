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

    Rad etilganda javob tanasida mashina o'qiy oladigan `code` qaytadi:
        invalid_key | inactive_client | ip_denied | scope_denied
    Barcha rad etish holatlari HTTP 403 bilan qaytadi (`authentication_classes = []`
    bo'lgani uchun DRF 401 emas, 403 beradi) — mijoz kodni `code` bo'yicha ajratadi.
    """
    message = "Integratsiya kaliti yaroqsiz."

    def _deny(self, code, detail):
        # DRF `message` dict bo'lsa uni javob tanasi sifatida to'g'ridan-to'g'ri chiqaradi.
        # Har so'rovga yangi permission nusxasi yaratiladi — bu xavfsiz.
        self.message = {'detail': detail, 'code': code}
        return False

    def has_permission(self, request, view):
        from apps.superadmin.models import IntegrationClient

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Api-Key '):
            return self._deny('invalid_key', "Api-Key sarlavhasi yuborilmagan.")
        token = auth[len('Api-Key '):].strip()
        if '.' not in token:
            return self._deny('invalid_key', "Kalit formati noto'g'ri (<prefix>.<secret> kutiladi).")
        prefix, raw = token.split('.', 1)

        try:
            client = IntegrationClient.objects.get(key_prefix=prefix)
        except IntegrationClient.DoesNotExist:
            return self._deny('invalid_key', "Kalit topilmadi.")

        expected = client.key_hash
        actual   = hashlib.sha256(raw.encode()).hexdigest()
        if not secrets.compare_digest(expected, actual):
            return self._deny('invalid_key', "Kalit mos kelmadi.")

        # Kalit to'g'ri, lekin mijoz o'chirilgan — sabab alohida ko'rsatiladi
        if not client.is_active:
            return self._deny('inactive_client', "Bu integratsiya kaliti o'chirilgan.")

        # IP cheklovi (ro'yxat bo'sh bo'lsa — tekshirilmaydi)
        if client.allowed_ips:
            ip = self._client_ip(request)
            if ip not in client.allowed_ips:
                return self._deny('ip_denied', "So'rov ruxsat etilmagan IP dan keldi.")

        # Scope
        required = getattr(view, 'required_scope', None)
        if required and required not in (client.scopes or []):
            return self._deny(
                'scope_denied', f"Kalitda «{required}» ruxsati yo'q."
            )

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
