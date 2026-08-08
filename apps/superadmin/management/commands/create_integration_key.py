from django.core.management.base import BaseCommand

from apps.superadmin.models import IntegrationClient


class Command(BaseCommand):
    help = "Yangi integratsiya API kaliti yaratadi"

    def add_arguments(self, parser):
        parser.add_argument('name')
        parser.add_argument('--scopes', nargs='+', default=['attendance:read'])
        parser.add_argument('--ips', nargs='*', default=[])

    def handle(self, *args, **o):
        obj, key = IntegrationClient.generate(o['name'], o['scopes'], o['ips'])
        self.stdout.write(self.style.SUCCESS(f"Kalit yaratildi: {obj.name}"))
        self.stdout.write(self.style.WARNING(
            f"\n  {key}\n\n"
            "  BU KALIT BOSHQA HECH QACHON KO'RSATILMAYDI. Hoziroq nusxalang."
        ))
