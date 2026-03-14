from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import Administrator


def _get_admin(request):
    """Foydalanuvchidan Administrator ni qaytaradi yoki None"""
    if not request.user.is_authenticated:
        return None
    return Administrator.objects.filter(user=request.user).first()


def _require_role(role_check_fn, fail_redirect='/login/'):
    """
    Umumiy decorator factory.
    role_check_fn — Administrator obyektini olib, True/False qaytaradi.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Avval tizimga kiring.")
                return redirect('/login/')
            admin_user = _get_admin(request)
            if not admin_user:
                messages.error(request, "Siz administrator emassiz.")
                return redirect('/login/')
            if not role_check_fn(admin_user):
                messages.error(request, "Sizda bu sahifaga kirish huquqi yo'q.")
                return redirect('/')
            request.admin_user = admin_user
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ============================================================
# TAYYOR DECORATOR LAR
# ============================================================

# Faqat org_admin
org_admin_required = _require_role(lambda a: a.is_org_admin)

# Xodimlar bo'limi: org_admin + hr_admin
hr_admin_required = _require_role(lambda a: a.is_hr_admin)

# O'quv bo'limi: org_admin + edu_admin
edu_admin_required = _require_role(lambda a: a.is_edu_admin)

# Monitoring: org_admin + monitoring
monitoring_required = _require_role(lambda a: a.is_monitoring)

# Istalgan admin (login bo'lgan har qanday administrator)
any_admin_required = _require_role(lambda a: True)

# Faqat filial_admin roli
filial_admin_required = _require_role(lambda a: a.role == 'filial_admin')
