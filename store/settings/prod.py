from .base import *
import dj_database_url

DEBUG = False

DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Content Security Policy
# Alpine CSP build eliminates unsafe-eval and unsafe-inline for scripts.
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-eval'", 'https://cdn.jsdelivr.net',)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", 'https://fonts.googleapis.com',)
CSP_FONT_SRC = ("'self'", 'https://fonts.gstatic.com',)
CSP_IMG_SRC = ("'self'", 'data:', 'https://res.cloudinary.com',)
CSP_CONNECT_SRC = ("'self'", 'https://cdn.jsdelivr.net',)
CSP_FRAME_ANCESTORS = ("'none'",)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

REDIS_URL = config('REDIS_URL', default=None)
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
