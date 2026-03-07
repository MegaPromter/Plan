from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',    auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True,
    ), name='login'),
    path('logout/',   auth_views.LogoutView.as_view(), name='logout'),
    path('password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('profile/',   views.ProfileView.as_view(),        name='profile'),
    path('dashboard/', views.DashboardView.as_view(),      name='dashboard'),
    path('admin-spa/', views.AdminSPAView.as_view(),        name='admin_spa'),
    path('stub/<slug:slug>/', views.StubView.as_view(),    name='stub'),
]
