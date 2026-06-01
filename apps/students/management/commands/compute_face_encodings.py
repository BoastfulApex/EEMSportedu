"""
Management command: mavjud tinglovchi rasmlari uchun face encoding hisoblash.

Foydalanish:
    python manage.py compute_face_encodings            # barcha encoding yo'qlar
    python manage.py compute_face_encodings --all      # barchasini qayta hisoblash
    python manage.py compute_face_encodings --dry-run  # faqat hisobot, o'zgarish yo'q

Bu command bir marta ishga tushirilsa yetarli.
Keyingi rasmlarda encoding avtomatik hisoblanadi (save_student_face_photo / save_student_face_by_id).
"""
import os

from django.core.management.base import BaseCommand

from apps.students.models import Student
from utils.face_recognition_util import compute_face_encoding


class Command(BaseCommand):
    help = "Tinglovchi rasmlari uchun face encoding hisoblash va DB ga saqlash"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Encoding mavjud bo\'lsalar ham barchasini qayta hisoblash',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Faqat hisobot — DB ga yozmaslik',
        )

    def handle(self, *args, **options):
        recompute_all = options['all']
        dry_run       = options['dry_run']

        qs = Student.objects.filter(face_image__isnull=False).exclude(face_image='')
        if not recompute_all:
            qs = qs.filter(face_encoding__isnull=True)

        total   = qs.count()
        success = 0
        failed  = 0
        skipped = 0

        self.stdout.write(f"Topildi: {total} ta tinglovchi")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN rejimi — DB ga yozilmaydi"))

        for student in qs.iterator():
            try:
                path = student.face_image.path
                if not os.path.exists(path):
                    self.stdout.write(f"  ⚠ {student.full_name} — rasm fayli topilmadi: {path}")
                    skipped += 1
                    continue

                encoding = compute_face_encoding(path)
                if encoding is None:
                    self.stdout.write(f"  ✗ {student.full_name} — rasmda yuz topilmadi yoki kutubxona yo'q")
                    failed += 1
                    continue

                if not dry_run:
                    student.face_encoding = encoding
                    student.save(update_fields=['face_encoding'])

                success += 1
                self.stdout.write(f"  ✓ {student.full_name}")

            except Exception as ex:
                self.stdout.write(f"  ✗ {student.full_name} — xato: {ex}")
                failed += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Muvaffaqiyatli: {success}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"Xato: {failed}"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"O'tkazib yuborildi: {skipped}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Hech narsa saqlanmadi (dry-run)"))
