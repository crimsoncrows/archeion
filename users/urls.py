from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('homepage/', views.homepage, name='homepage'),
    path('restricted/', views.restricted, name='restricted'),
    path('validate/', views.validate_signup, name='validate_signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('faculty/reports/', views.faculty_reports, name='faculty_reports'),
    path('password-reset/', views.ArcheionPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.ArcheionPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.ArcheionPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.ArcheionPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]