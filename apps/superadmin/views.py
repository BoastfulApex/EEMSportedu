from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.template import loader
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.generic.edit import DeleteView
from django.urls import reverse_lazy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

from apps.superadmin.models import Administrator, Filial, Organization
from apps.main.models import Location
from apps.superadmin.forms import FilialForm, AdminUserForm, FilialSubAdminForm
from apps.main.forms import LocationForm
from apps.superadmin.decorators import org_admin_required, filial_admin_required, location_admin_required


# ============================================================
# FILIALLAR
# ============================================================

@org_admin_required
def filials(request):
    admin_user = Administrator.objects.get(user=request.user)
    all_filials = Filial.objects.filter(organization=admin_user.organization)
    search_query = request.GET.get('q')
    request.session['selected_filial_id'] = 'super_admin'
    if search_query:
        all_filials = all_filials.filter(Q(filial_name__icontains=search_query))
    paginator = Paginator(all_filials, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    data = {'filials': all_filials}
    context = {'page_obj': page_obj, 'segment': 'filials', 'data': data}
    return HttpResponse(loader.get_template('home/superuser/filials.html').render(context, request))


@org_admin_required
def filial_create(request):
    admin_user = Administrator.objects.get(user=request.user)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    request.session['selected_filial_id'] = 'super_admin'
    if request.method == 'POST':
        form = FilialForm(request.POST)
        if form.is_valid():
            filial = form.save(commit=False)
            filial.organization = admin_user.organization
            filial.save()
            return redirect('admin_filials')
    else:
        form = FilialForm()
    return render(request, 'home/superuser/filial_create.html',
                  {'form': form, 'segment': 'filials', 'data': data})


@org_admin_required
def filial_detail(request, pk):
    admin_user = Administrator.objects.get(user=request.user)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    request.session['selected_filial_id'] = 'super_admin'
    filial = Filial.objects.get(id=pk)
    if request.method == 'POST':
        form = FilialForm(request.POST, instance=filial)
        if form.is_valid():
            form.save()
            return redirect('admin_filials')
    else:
        form = FilialForm(instance=filial)
    return render(request, 'home/superuser/filial_detail.html',
                  {'form': form, 'segment': 'filials', 'filial': filial, 'data': data})


class FilialDelete(DeleteView):
    model = Filial
    fields = '__all__'
    success_url = reverse_lazy('admin_filials')


# ============================================================
# ADMINISTRATORLAR
# ============================================================

@org_admin_required
def admin_list(request):
    admin_user = Administrator.objects.get(user=request.user)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    request.session['selected_filial_id'] = 'super_admin'

    # org_admin o'zini ro'yxatda ko'rmasin
    admins = Administrator.objects.select_related('user', 'filial').filter(
        organization=admin_user.organization
    ).exclude(role='org_admin')

    search_query = request.GET.get('q')
    if search_query:
        admins = admins.filter(
            Q(full_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    paginator = Paginator(admins, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'home/superuser/adminstrators.html',
                  {'page_obj': page_obj, 'segment': 'admins', 'data': data})


@org_admin_required
def admin_create(request):
    admin_user = Administrator.objects.get(user=request.user)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    request.session['selected_filial_id'] = 'super_admin'

    # URL dan rol olish: ?role=hr_admin / edu_admin / monitoring
    role_param = request.GET.get('role', '')
    ROLE_LABELS = {
        'filial_admin': "Filial admini",
        'hr_admin':     "Xodimlar bo'limi admini",
        'edu_admin':    "O'quv bo'limi admini",
        'monitoring':   "Monitoring admini",
    }
    role_label = ROLE_LABELS.get(role_param, '')

    if request.method == 'POST':
        # role_param ni POST ga qo'shib yuboramiz (template hidden input orqali)
        post_data = request.POST.copy()
        if role_param and not post_data.get('role'):
            post_data['role'] = role_param
        form = AdminUserForm(post_data, admin_user=admin_user)
        if form.is_valid():
            admin = form.save(commit=False)
            admin.organization = admin_user.organization
            admin.save()
            return redirect('admin_adminstrators')
    else:
        form = AdminUserForm(admin_user=admin_user)
        if role_param and 'role' in form.fields:
            form.fields['role'].initial = role_param

    return render(request, 'home/superuser/adminstrator_create.html', {
        'form': form,
        'segment': 'admins',
        'data': data,
        'role_label': role_label,
        'role_param': role_param,
    })


@org_admin_required
def admin_detail(request, pk):
    admin_user = Administrator.objects.get(user=request.user)
    admin = Administrator.objects.get(id=pk)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    request.session['selected_filial_id'] = 'super_admin'
    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=admin, admin_user=admin_user)
        if form.is_valid():
            form.save()
            return redirect('admin_adminstrators')
    else:
        form = AdminUserForm(instance=admin, admin_user=admin_user)
    return render(request, 'home/superuser/adminstrator_detail.html',
                  {'form': form, 'segment': 'admins', 'admin': admin, 'data': data})


class AdminstratorDeleteView(DeleteView):
    model = Administrator
    success_url = reverse_lazy('admin_adminstrators')
    template_name = 'superadmin/administrator_confirm_delete.html'


# ============================================================
# FILIAL TANLASH (session)
# ============================================================

@org_admin_required
def select_filial(request, filial_id):
    request.session['selected_filial_id'] = filial_id
    return redirect('home')


# ============================================================
# LOKATSIYALAR
# ============================================================

def get_location_name(lat, lon):
    geolocator = Nominatim(user_agent="kpiproject_bot")
    try:
        location = geolocator.reverse((lat, lon), timeout=10)
        return location.address if location else "Noma'lum manzil"
    except GeocoderTimedOut:
        return "Geocoding vaqti tugadi"


@location_admin_required
def locations(request):
    admin_user = Administrator.objects.get(user=request.user)
    all_filials = Filial.objects.filter(organization=admin_user.organization)
    data = {'filials': all_filials}
    if admin_user.is_org_admin:
        request.session['selected_filial_id'] = 'super_admin'
    locs = Location.objects.filter(organization=admin_user.organization).order_by('name')
    # edu_admin faqat o'z filialining lokatsiyalarini ko'radi
    if not admin_user.is_org_admin and admin_user.filial_id:
        locs = locs.filter(filial_id=admin_user.filial_id)
    search_query = request.GET.get('q')
    if search_query:
        locs = locs.filter(Q(address__icontains=search_query))
    paginator = Paginator(locs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {'page_obj': page_obj, 'segment': 'locations', 'data': data}
    return HttpResponse(loader.get_template('home/superuser/locations.html').render(context, request))


def create_location_ajax(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'errors': form.errors.as_text()})
    return JsonResponse({'success': False, 'errors': "Noto'g'ri so'rov"})


@location_admin_required
def create_location(request):
    admin_user = Administrator.objects.get(user=request.user)
    data = {'filials': Filial.objects.filter(organization=admin_user.organization)}
    if request.method == 'POST':
        form = LocationForm(request.POST, admin_user=admin_user)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.address = form.cleaned_data.get('address') or ''
            instance.organization = admin_user.organization
            instance.save()
            return redirect('admin_locations')
    else:
        form = LocationForm(admin_user=admin_user)
    return render(request, 'home/superuser/location_create.html',
                  {'form': form, 'data': data, 'segment': 'locations'})


class LocationDeleteView(DeleteView):
    model = Location
    success_url = reverse_lazy('admin_locations')
    template_name = 'main/location_confirm_delete.html'


# ============================================================
# FILIAL ADMIN — o'z filiali uchun sub-adminlar boshqaruvi
# ============================================================

@filial_admin_required
def filial_admin_list(request):
    """filial_admin o'z filialining hr/edu/monitoring adminlarini ko'radi."""
    admin_user = request.admin_user
    admins = Administrator.objects.select_related('user').filter(
        filial=admin_user.filial
    ).exclude(role__in=['org_admin', 'filial_admin'])
    search_query = request.GET.get('q', '')
    if search_query:
        admins = admins.filter(
            Q(full_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    paginator = Paginator(admins, 50)
    page_obj  = paginator.get_page(request.GET.get('page'))
    return render(request, 'home/filial_admin/admins.html', {
        'page_obj':     page_obj,
        'segment':      'filial_admins',
        'search_query': search_query,
        'filial':       admin_user.filial,
    })


@filial_admin_required
def filial_admin_create(request):
    """filial_admin o'z filiali uchun yangi hr/edu/monitoring admin yaratadi."""
    admin_user  = request.admin_user
    role_param  = request.GET.get('role', '')
    ROLE_LABELS = {
        'hr_admin':   "Xodimlar bo'limi admini",
        'edu_admin':  "O'quv bo'limi admini",
        'monitoring': "Monitoring admini",
    }
    role_label = ROLE_LABELS.get(role_param, '')

    if request.method == 'POST':
        form = FilialSubAdminForm(request.POST)
        if form.is_valid():
            form.save(
                filial=admin_user.filial,
                organization=admin_user.organization
            )
            return redirect('filial_admin_list')
    else:
        form = FilialSubAdminForm()
        if role_param and 'role' in form.fields:
            form.fields['role'].initial = role_param

    return render(request, 'home/filial_admin/admin_create.html', {
        'form':       form,
        'segment':    'filial_admins',
        'role_label': role_label,
        'role_param': role_param,
        'filial':     admin_user.filial,
    })


@filial_admin_required
def filial_admin_detail(request, pk):
    """filial_admin o'z filialidagi adminni tahrirlaydi."""
    admin_user = request.admin_user
    target = Administrator.objects.get(id=pk, filial=admin_user.filial)

    if request.method == 'POST':
        form = FilialSubAdminForm(request.POST, instance=target)
        if form.is_valid():
            form.save(
                filial=admin_user.filial,
                organization=admin_user.organization
            )
            return redirect('filial_admin_list')
    else:
        form = FilialSubAdminForm(instance=target)

    return render(request, 'home/filial_admin/admin_detail.html', {
        'form':    form,
        'segment': 'filial_admins',
        'admin':   target,
        'filial':  admin_user.filial,
    })


class FilialSubAdminDeleteView(DeleteView):
    model         = Administrator
    success_url   = reverse_lazy('filial_admin_list')
    template_name = 'home/filial_admin/admin_confirm_delete.html'


# ============================================================
# REFERAL LINKLAR
# ============================================================

@org_admin_required
def referral_links(request):
    """Tashkilot filiallari uchun Telegram taklif havolalarini ko'rsatish."""
    from data.config import BOT_USERNAME
    from apps.main.models import InviteToken

    admin_user = request.admin_user
    org = admin_user.organization
    filials = Filial.objects.filter(organization=org)

    # Har bir filial uchun faol token bo'lmasa — avtomatik yaratamiz
    for filial in filials:
        if not filial.invite_tokens.filter(is_active=True).exists():
            InviteToken.objects.create(filial=filial)

    filial_data = []
    for filial in filials:
        token_obj = filial.invite_tokens.filter(is_active=True).order_by('-created_at').first()
        link = f"https://t.me/{BOT_USERNAME}?start={token_obj.token}" if BOT_USERNAME and token_obj else None
        filial_data.append({
            'filial': filial,
            'token': token_obj.token if token_obj else None,
            'link': link,
        })

    return render(request, 'home/referral_links.html', {
        'segment': 'referral',
        'org': org,
        'filial_data': filial_data,
        'bot_username': BOT_USERNAME,
    })


@org_admin_required
def regenerate_invite_token(request, filial_id):
    """Filial uchun yangi token yaratish (eskilarini o'chiradi)."""
    from apps.main.models import InviteToken
    admin_user = request.admin_user

    filial = Filial.objects.filter(id=filial_id, organization=admin_user.organization).first()
    if not filial:
        return HttpResponseForbidden("Bu filial sizga tegishli emas.")

    # Eski tokenlarni o'chirish
    filial.invite_tokens.all().delete()
    # Yangi token yaratish
    InviteToken.objects.create(filial=filial)

    return redirect('referral_links')
