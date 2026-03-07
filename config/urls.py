from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/',     admin.site.urls),
    path('api/',       include('apps.api.urls')),
    path('accounts/',  include('apps.accounts.urls', namespace='accounts')),
    path('employees/', include('apps.employees.urls', namespace='employees')),
    path('works/',     include('apps.works.urls',     namespace='works')),
    # Корень → дашборд
    path('', RedirectView.as_view(url='/accounts/dashboard/', permanent=False)),
]
