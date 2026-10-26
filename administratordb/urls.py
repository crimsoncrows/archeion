from django.urls import path
from . import views

app_name = 'administratordb'

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('research/', views.admin_research, name='admin_research'),
    path('research/papers/', views.admin_research_papers, name='admin_research_papers'),
    path('research/papers/add/', views.admin_add_research_paper, name='admin_add_research_paper'),
    path('research/papers/<int:paper_id>/edit/',views.admin_edit_research_paper,name='admin_edit_research_paper',),
    path(
        'research/papers/<int:paper_id>/delete/',
        views.admin_delete_research_paper,
        name='admin_delete_research_paper',
    ),
    path('research/categories/', views.admin_research_categories, name='admin_research_categories'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/add/', views.admin_add_user, name='admin_add_user'),
    path(
        'users/<int:user_id>/edit/',
        views.admin_edit_user,
        name='admin_edit_user',
    ),
    path(
        'users/<int:user_id>/deactivate/',
        views.admin_deactivate_user,
        name='admin_deactivate_user',
    ),
    path('feedback/', views.admin_feedback, name='admin_feedback'),
    #Feedback Viewing/Deleting
    path('feedback/delete/<int:feedback_id>/', views.admin_delete_feedback, name='admin_delete_feedback'),
path('research/categories/add/', views.admin_add_category, name='admin_add_category'),
path('research/categories/<int:category_id>/edit/', views.admin_edit_category, name='admin_edit_category'),
path('research/categories/<int:category_id>/delete/', views.admin_delete_category, name='admin_delete_category'),
]
