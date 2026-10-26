"""
URL configuration for archeion project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from . import views

handler403 = 'archeion.views.access_denied'
handler404 = 'archeion.views.page_not_found'
handler500 = 'archeion.views.server_error'

urlpatterns = [
    path('archeion2026_djangoadmin_dashboard/', admin.site.urls), #do not change to generic url name like admin, for security

    path('', views.landing, name='landing'),
    path('coming-soon/', views.coming_soon, name='coming_soon'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.tos, name='tos'),
    path('administratordb/', include('administratordb.urls')),
    path('users/', include('users.urls', namespace='users')),
    path('similarity/', include('similarity.urls', namespace='similarity')),
    path('papers/', include('papers.urls', namespace='papers')),
]