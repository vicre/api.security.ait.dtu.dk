from .settings import *
import os





# CAS_SERVER_URL = 'https://auth.dtu.dk/dtu/' # no multifactor




CSRF_COOKIE_DOMAIN = 'localhost'

# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False


# Localhost profile defaults to SQLite so the app can boot without Docker Postgres.
if os.getenv("LOCALHOST_USE_SQLITE", "1").strip().lower() in {"1", "true", "yes", "on"}:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
