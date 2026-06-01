from django.http import HttpResponse
from django.template import loader


def index(request):
    html_template = loader.get_template('main/web_app_page.html')
    return HttpResponse(html_template.render({}, request))


def hr_admin_web_app(request):
    """HR admin xodim davomat web sahifasi (Telegram WebApp orqali ochiladi)"""
    html_template = loader.get_template('main/hr_admin_web_app.html')
    response = HttpResponse(html_template.render({}, request))
    response['X-Frame-Options'] = 'ALLOWALL'
    return response
    