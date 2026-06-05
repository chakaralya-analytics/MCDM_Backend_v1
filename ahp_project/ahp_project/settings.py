"""
Django settings for ahp_project project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Sentry — initialise early so it captures startup errors too.
# Set SENTRY_DSN in Cloud Run env vars to enable; omit to disable silently.
_sentry_dsn = os.getenv('SENTRY_DSN', '')
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        send_default_pii=False,
    )


# Crash loudly if SECRET_KEY is not set — no silent fallback in any environment.
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Copy .env.example to .env and fill in a strong secret key."
    )
SECRET_KEY = _secret_key

# Default to False — opt-in to debug mode explicitly via env var.
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# ALLOWED_HOSTS must be set in production (ALLOWED_HOSTS env var, comma-separated).
# Default covers local dev only.  Cloud Run: set to your *.run.app domain.
_allowed = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

# Application definition
DJANGO_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'rest_framework.authtoken',   # kept so existing migrations don't break; no longer used for API auth
    'django_extensions',          # python manage.py show_urls for route debugging
]

LOCAL_APPS = [
    'ahp_api',
    'users',
    'plans',
    'billing',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'ahp_project.middleware.RequestIDMiddleware',        # must be first
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'ahp_project.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ahp_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ahp_project.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Use SQLite only when USE_SQLITE=True is explicitly set (local dev shortcut).
# Production always requires PostgreSQL env vars to be present.
use_sqlite = os.getenv('USE_SQLITE', 'False').lower() == 'true'
if use_sqlite:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # All DB vars are required — no hardcoded fallbacks.
    _db_host = os.environ.get('DB_HOST')
    _db_name = os.environ.get('DB_NAME')
    _db_user = os.environ.get('DB_USER')
    _db_password = os.environ.get('DB_PASSWORD')
    if not all([_db_host, _db_name, _db_user, _db_password]):
        raise RuntimeError(
            "PostgreSQL environment variables DB_HOST, DB_NAME, DB_USER, and "
            "DB_PASSWORD must all be set when USE_SQLITE is not True."
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db_name,
            'USER': _db_user,
            'PASSWORD': _db_password,
            'HOST': _db_host,
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 60,
                'sslmode': 'prefer',
                'application_name': 'ahp_django_app',
            },
            'CONN_MAX_AGE': 300,
            'CONN_HEALTH_CHECKS': True,
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': True,
            'TIME_ZONE': None,
        }
    }

# ✅ Add these additional database settings
DATABASE_ROUTERS = []
DATABASE_CONNECTION_RETRY_DELAY = 2
DATABASE_CONNECTION_MAX_RETRIES = 3



# Cache Configuration
REDIS_URL = os.getenv('REDIS_URL')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 50,
                    'retry_on_timeout': True,
                },
                # Keep API available even if Redis is unavailable.
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'ahp',
            'TIMEOUT': int(os.getenv('CACHE_TTL', 3600)),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ahp-local-cache',
            'TIMEOUT': int(os.getenv('CACHE_TTL', 3600)),
        }
    }

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = os.getenv('STATIC_URL', '/static/')
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = os.getenv('MEDIA_URL', '/media/')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Settings for React Frontend
# Never allow all origins — always enumerate explicitly, even in development.
CORS_ALLOW_ALL_ORIGINS = False

if DEBUG:
    # All common Vite / CRA / custom local ports.
    # To add more without editing code, set CORS_DEV_ORIGINS in .env:
    #   CORS_DEV_ORIGINS=http://localhost:3002,http://localhost:4000
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    _extra = os.getenv('CORS_DEV_ORIGINS', '')
    if _extra:
        CORS_ALLOWED_ORIGINS += [o.strip() for o in _extra.split(',') if o.strip()]
else:
    # Production: CORS_ALLOWED_ORIGINS must be set explicitly — no safe default.
    _cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
    if not _cors_origins:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be set in production (comma-separated list of allowed origins)."
        )
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]

# Required for JWT in Authorization header — browser must include credentials on
# cross-origin requests.  Overridable via env var if needed.
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'True').lower() == 'true'

CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # JWT-only. DRF Token auth has been removed — tokens never expire.
        # SessionAuthentication is kept solely for the Django admin panel.
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_ANON_RATE', '100/day'),
        'user': os.getenv('THROTTLE_USER_RATE', '1000/day'),
        'burst': os.getenv('THROTTLE_BURST_RATE', '60/min'),
        'auth': os.getenv('THROTTLE_AUTH_RATE', '10/min'),
        # Payment-specific — tighter limits to prevent abuse.
        'payment_create': os.getenv('THROTTLE_PAYMENT_CREATE', '10/hour'),
        'payment_verify': os.getenv('THROTTLE_PAYMENT_VERIFY', '20/hour'),
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', 15))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', 7))),
    'ROTATE_REFRESH_TOKENS': True,
    # Blacklisting requires rest_framework_simplejwt.token_blacklist in INSTALLED_APPS (already added).
    # Run `python manage.py migrate` after adding the app to create the blacklist tables.
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    # Use a dedicated JWT secret if provided; falls back to SECRET_KEY.
    'SIGNING_KEY': os.getenv('JWT_SECRET_KEY', SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# Enhanced Security Settings for Production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Django was forcing HTTPS: turn that off
    SECURE_SSL_REDIRECT = False

    # trust the LB’s X-Forwarded-Proto and Host headers
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST    = True

    SECURE_HSTS_SECONDS           = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD           = True
    SESSION_COOKIE_SECURE         = True
    CSRF_COOKIE_SECURE            = True

    # Required by Django 4.0+ for cross-origin requests that touch CSRF
    # (admin panel, session-auth views).  Falls back to CORS origins when
    # CSRF_TRUSTED_ORIGINS is not set explicitly — they share the same format.
    _csrf_trusted = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
    CSRF_TRUSTED_ORIGINS = (
        [o.strip() for o in _csrf_trusted.split(',') if o.strip()]
        if _csrf_trusted
        else CORS_ALLOWED_ORIGINS
    )

    DATABASES['default']['CONN_MAX_AGE'] = 60

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Logging Configuration
# --- Feature limits (Phase 3: these will be driven by subscription plans) ----
# Override via env vars so ops can adjust per-environment without code changes.
DEFAULT_MAX_PROJECTS = int(os.getenv('DEFAULT_MAX_PROJECTS', '2'))
DEFAULT_ALTERNATIVE_LIMIT = int(os.getenv('DEFAULT_ALTERNATIVE_LIMIT', '3'))

# --- Razorpay payment gateway -------------------------------------------
# Key ID and Key Secret: from Razorpay Dashboard → Settings → API Keys.
# Webhook Secret: from Razorpay Dashboard → Settings → Webhooks.
# Use TEST keys locally, LIVE keys only in production (behind env vars).
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
RAZORPAY_CURRENCY = os.getenv('RAZORPAY_CURRENCY', 'INR')

# Firebase Web API Key — used to verify ID tokens via the Identity Toolkit REST API.
# No service account required; this is the public web key from Firebase Console.
FIREBASE_WEB_API_KEY = os.getenv('FIREBASE_WEB_API_KEY', '')

# --- Celery -------------------------------------------------------
# Broker + result backend both point to Redis when available; otherwise the
# worker simply won't start (acceptable — Celery is opt-in for now).
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
# Retry tasks on connection errors; safe for idempotent jobs (webhooks, email).
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Task time limits — enforce them so runaway tasks don't block workers.
CELERY_TASK_SOFT_TIME_LIMIT = 60   # seconds — raises SoftTimeLimitExceeded
CELERY_TASK_TIME_LIMIT = 120       # hard kill after this many seconds

_LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')

# In production use structured JSON; in debug use readable text.
_console_formatter = 'json' if not DEBUG else 'simple'
_file_formatter = 'json' if not DEBUG else 'verbose'

# LOG_TO_FILE=False by default in production — Cloud Run has an ephemeral
# filesystem and Cloud Logging captures stdout/stderr automatically.
# Set LOG_TO_FILE=True locally or in any environment that has persistent disk.
_log_to_file = os.getenv('LOG_TO_FILE', 'True' if DEBUG else 'False').lower() == 'true'
_active_handlers = ['console', 'file'] if _log_to_file else ['console']

_handlers: dict = {
    'console': {
        'level': _LOG_LEVEL,
        'class': 'logging.StreamHandler',
        'formatter': _console_formatter,
        'filters': ['request_id'],
    },
}
if _log_to_file:
    _handlers['file'] = {
        'level': _LOG_LEVEL,
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': os.path.join(LOGS_DIR, 'django.log'),
        'maxBytes': 1024 * 1024 * 5,  # 5 MB
        'backupCount': 5,
        'formatter': _file_formatter,
        'filters': ['request_id'],
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'ahp_project.logging_formatters.JSONFormatter',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'request_id': {
            '()': 'ahp_project.middleware.RequestIDFilter',
        },
    },
    'handlers': _handlers,
    'root': {
        'handlers': _active_handlers,
        'level': _LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': _active_handlers,
            'level': _LOG_LEVEL,
            'propagate': False,
        },
        'ahp_api': {
            'handlers': _active_handlers,
            'level': _LOG_LEVEL,
            'propagate': False,
        },
        'billing': {
            'handlers': _active_handlers,
            'level': _LOG_LEVEL,
            'propagate': False,
        },
        'plans': {
            'handlers': _active_handlers,
            'level': _LOG_LEVEL,
            'propagate': False,
        },
        'users': {
            'handlers': _active_handlers,
            'level': _LOG_LEVEL,
            'propagate': False,
        },
    },
}

# --- Email -------------------------------------------------------------------
# Switch EMAIL_BACKEND in .env for different environments:
#   console (default/dev): logs to stdout
#   smtp: configure EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

APP_NAME = os.getenv('APP_NAME', 'MCDM Platform')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
