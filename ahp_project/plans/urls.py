# plans/urls.py
# Relative paths only — the api/v1/plans/ prefix is owned by ahp_project/urls.py.

from django.urls import path
from . import views

urlpatterns = [
    path('', views.PlanListView.as_view(), name='plan_list'),                          # GET  /api/v1/plans/
    path('subscription/', views.MySubscriptionView.as_view(), name='my_subscription'), # GET  /api/v1/plans/subscription/
    path('subscription/change/', views.ChangePlanView.as_view(), name='change_plan'),  # POST /api/v1/plans/subscription/change/
    path('subscription/cancel/', views.CancelSubscriptionView.as_view(), name='cancel_subscription'), # POST /api/v1/plans/subscription/cancel/
    path('usage/', views.UsageView.as_view(), name='usage'),                           # GET  /api/v1/plans/usage/
]
