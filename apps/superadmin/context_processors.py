from .models import Administrator


def admin_context(request):
    """
    Barcha template larga admin rol ma'lumotlarini uzatadi.
    Sidebar, ruxsat tekshiruvlari uchun ishlatiladi.
    """
    if not request.user.is_authenticated:
        return {}

    admin_user = Administrator.objects.filter(user=request.user).first()
    if not admin_user:
        return {}

    return {
        'admin_user':      admin_user,
        'admin_role':      admin_user.role,
        'is_org_admin':    admin_user.is_org_admin,
        'is_filial_admin': admin_user.is_filial_admin,
        'is_hr_admin':     admin_user.is_hr_admin,
        'is_edu_admin':    admin_user.is_edu_admin,
        'is_monitoring':   admin_user.is_monitoring,
    }
