# users/views.py

import logging
import re

import requests as http_requests
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, LoginSerializer

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    """Stricter rate limit applied only to login and register endpoints."""
    scope = 'auth'


def _tokens_for_user(user):
    """Return a dict with JWT access and refresh tokens for a given user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def _user_payload(user):
    """Return the user data dict included in auth responses."""
    phone_number = 'Not provided'
    if hasattr(user, 'profile') and user.profile:
        phone_number = user.profile.phone_number
    return {
        'username': user.username,
        'email': user.email,
        'phone_number': phone_number,
    }


def _verify_firebase_token(id_token: str) -> dict:
    """Call Firebase Identity Toolkit to verify a Firebase ID token.

    Returns the user dict from Firebase on success.
    Raises ValueError on invalid / expired token.
    Does NOT require a service-account key — only the Web API key.
    """
    api_key = settings.FIREBASE_WEB_API_KEY
    if not api_key:
        raise ValueError("FIREBASE_WEB_API_KEY is not configured on the server.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    try:
        resp = http_requests.post(url, json={"idToken": id_token}, timeout=10)
    except http_requests.RequestException as exc:
        logger.error("Firebase token verification HTTP error: %s", exc)
        raise ValueError("Could not reach authentication server. Try again.")

    if resp.status_code != 200:
        raise ValueError("Invalid or expired authentication token.")

    users = resp.json().get("users", [])
    if not users:
        raise ValueError("Authentication token verification failed.")
    return users[0]


def _generate_social_username(email: str, display_name: str = '') -> str:
    """Derive a unique Django username from a display name or email."""
    base = re.sub(r'[^a-z0-9]', '', (display_name or '').lower())[:20]
    if not base:
        base = re.sub(r'[^a-z0-9]', '', email.split('@')[0].lower())[:20]
    if not base:
        base = 'user'
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


class SocialAuthView(APIView):
    """POST /users/social-auth/

    Accepts a Firebase ID token (from Google or Apple sign-in on the frontend),
    verifies it server-side, then returns JWT tokens for the corresponding
    Django user — creating the account on first sign-in.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        id_token = request.data.get('id_token', '').strip()
        if not id_token:
            return Response({'error': 'id_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            firebase_user = _verify_firebase_token(id_token)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        email = firebase_user.get('email', '').lower()
        if not email:
            return Response(
                {'error': 'No email address associated with this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        display_name = firebase_user.get('displayName', '')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': _generate_social_username(email, display_name),
            },
        )

        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
            try:
                from plans.services.subscription_service import create_free_subscription
                create_free_subscription(user)
            except Exception:
                logger.warning("Could not provision free subscription for social user %s", user.id)

        logger.info(
            "Social auth: user=%s email=%s created=%s", user.id, email, created
        )

        return Response(
            {'user': _user_payload(user), **_tokens_for_user(user), 'is_new_user': created},
            status=status.HTTP_200_OK,
        )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer
    throttle_classes = [AuthRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            if settings.DEBUG:
                safe_data = {k: v for k, v in request.data.items() if k != 'password'}
                logger.warning(
                    'Registration validation failed | fields_received=%s | errors=%s',
                    list(safe_data.keys()),
                    serializer.errors,
                )
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)
        user = serializer.instance

        # Provision a free subscription for every new account.
        from plans.services.subscription_service import create_free_subscription
        create_free_subscription(user)

        # Fire-and-forget welcome email — failure must not break registration.
        try:
            from billing.tasks import send_welcome_email_task
            send_welcome_email_task.delay(user.id)
        except Exception:
            logger.warning('Welcome email task failed to queue for user %s', user.id)

        return Response(
            {'user': _user_payload(user), **_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        username_or_email = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        # Resolve email → username so authenticate() can find the user.
        username = username_or_email
        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email=username_or_email)
                username = user_obj.username
            except User.DoesNotExist:
                pass  # authenticate() will fail below with a clean error message

        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response(
                {'error': 'Invalid credentials. Please check your username/email and password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'user': _user_payload(user), **_tokens_for_user(user)},
            status=status.HTTP_200_OK,
        )
