from django.http import HttpResponse
from django.template import loader


def index(request):
    context = {
    }

    html_template = loader.get_template('main/web_app_page.html')
    return HttpResponse(html_template.render(context, request))
    