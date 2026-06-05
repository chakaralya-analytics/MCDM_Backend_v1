from django.urls import path
from . import views

urlpatterns = [
    # Criteria calculation
    path('calculate/', views.AHPCalculateView.as_view(), name='calculate_criteria'),

    # Alternative scoring (note: hyphenated to match REST conventions)
    path('calculate-alternatives/', views.AHPCalculateAlternativesView.as_view(), name='calculate_alternatives'),

    # Project management
    path('projects/criteria-only/', views.CriteriaOnlyProjectsView.as_view(), name='criteria_only_projects'),
    path('projects/all/', views.AllProjectsView.as_view(), name='all_projects'),
    path('projects/<int:id>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:id>/criteria-weights/', views.ProjectCriteriaWeightsView.as_view(), name='project_criteria_weights'),

    # Alternative history — calc_id (int) replaces timestamp string
    path('projects/<int:project_id>/history/', views.AlternativeHistoryListView.as_view(), name='alternative_history_list'),
    path('projects/<int:project_id>/history/<int:calc_id>/', views.AlternativeHistoryDetailView.as_view(), name='alternative_history_detail'),

    # Health check
    path('health/', views.health_check, name='health_check'),
]
