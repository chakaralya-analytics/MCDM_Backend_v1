from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, LoginView, SocialAuthView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('social-auth/', SocialAuthView.as_view(), name='social_auth'),
    # JWT refresh endpoint — frontend posts { refresh } to get a new access token.
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
