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

    # Сброс пароля по email
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/accounts/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/accounts/password-reset/complete/',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
]
