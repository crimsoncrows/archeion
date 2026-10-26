from django.urls import path
from . import views

app_name = 'papers'

urlpatterns = [
    path('browse/', views.browse, name='browse'),
    path('document/<int:paper_id>/', views.document_info, name='document_info'),
    path('paper/<int:paper_id>/view/', views.view_paper, name='view_paper'),
    path('paper/<int:paper_id>/stream/', views.stream_paper_pdf, name='stream_paper_pdf'),
]