from .base import *

DEBUG = True

# Safety net: this file must never be loaded in a non-debug environment.
assert DEBUG, "store.settings.dev loaded with DEBUG=False — use store.settings.prod instead."

ALLOWED_HOSTS = ['*']

# Trust GitHub Codespaces forwarded domains for CSRF
CSRF_TRUSTED_ORIGINS = [
    'https://*.app.github.dev',
    'https://localhost:8000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# CODESPACES ONLY — GitHub Codespaces serves the dev server behind an HTTPS proxy on a
# different origin, so the browser treats requests as cross-site. SameSite=None is required
# to allow the CSRF and session cookies to be sent in that context.
# ⚠️  These two settings MUST NOT appear in prod.py. Production uses the default SameSite=Lax.
CSRF_COOKIE_SAMESITE = 'None'   # dev/Codespaces only
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'  # dev/Codespaces only
SESSION_COOKIE_SECURE = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Alpine CSP build — no unsafe-inline or unsafe-eval needed for scripts.
# unsafe-inline kept for style-src only (inline style= attributes in templates).
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-eval'", 'https://cdn.jsdelivr.net',)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", 'https://fonts.googleapis.com',)
CSP_FONT_SRC = ("'self'", 'https://fonts.gstatic.com',)
CSP_IMG_SRC = ("'self'", 'data:', 'https://res.cloudinary.com',)
CSP_CONNECT_SRC = ("'self'", 'https://cdn.jsdelivr.net',)
