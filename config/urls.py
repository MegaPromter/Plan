from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin          # встроенная административная панель Django
from django.urls import path, include     # path — создание маршрута; include — подключение вложенных URLconf
from django.views.generic import RedirectView  # класс-view для HTTP-редиректа без написания функции

# Корневой список URL-маршрутов всего проекта
# Django перебирает маршруты сверху вниз и останавливается на первом совпадении
urlpatterns = [
    # Административная панель Django (/admin/)
    path('admin/',     admin.site.urls),
    # API-маршруты — все эндпоинты в /api/ делегируются в apps.api.urls
    path('api/',       include('apps.api.urls')),
    # Маршруты аутентификации (/accounts/login/, /accounts/register/, /accounts/dashboard/ и т.д.)
    # namespace='accounts' позволяет обращаться к маршрутам как accounts:login и т.д.
    path('accounts/',  include('apps.accounts.urls', namespace='accounts')),
    # Маршруты модуля сотрудников (/employees/...) — справочники: отделы, секторы, НТЦ
    path('employees/', include('apps.employees.urls', namespace='employees')),
    # Маршруты рабочего модуля (/works/...) — план задач, производственный план, проекты
    path('works/',     include('apps.works.urls',     namespace='works')),
    # Корень → дашборд
    # Временный редирект (302) с корневого URL '/' на дашборд; permanent=False → HTTP 302
    path('', RedirectView.as_view(url='/accounts/dashboard/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
