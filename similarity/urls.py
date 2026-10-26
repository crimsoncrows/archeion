from django.urls import path
from . import views

app_name = 'similarity'

urlpatterns = [
    path('sbert/', views.similarity_check, name='sbert'),
    path('results/', views.similarity_result, name='paper_results'),
    path('results/<int:paper_id>/', views.similarity_result, name='past_result'),
    path('trends/', views.trends, name='trends'),
]