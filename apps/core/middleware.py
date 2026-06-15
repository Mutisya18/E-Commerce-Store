import re
import uuid
import time
import hashlib
import logging
import threading

logger = logging.getLogger('journey')

# Thread-local so views can access current request IDs without passing them around
_local = threading.local()


def get_trace_id():
    return getattr(_local, 'trace_id', None)


def get_request_id():
    return getattr(_local, 'request_id', None)


def get_client_ip(group, request):
    """Proxy-aware IP extraction for use as django-ratelimit's key callable."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _hash_session(key):
    """Return first 12 chars of SHA-256 of the session key — safe to log."""
    return hashlib.sha256(key.encode()).hexdigest()[:12] if key else 'no-session'


class JourneyLoggingMiddleware:
    """
    Attaches traceId, requestId, userId, sessionId to every request.
    Logs request_received and response_sent with duration.
    Propagates traceId from X-Trace-Id header (frontend → backend link).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Accept traceId from frontend — sanitise to alphanumeric+hyphen, max 32 chars
        raw = request.headers.get('X-Trace-Id', '')
        sanitised = re.sub(r'[^A-Za-z0-9\-]', '', raw)[:32]
        trace_id = sanitised or f'T{uuid.uuid4().hex[:8].upper()}'
        request_id = f'R{uuid.uuid4().hex[:8].upper()}'
        session_id = _hash_session(request.session.session_key)

        # Store on thread-local for use in views/signals
        _local.trace_id = trace_id
        _local.request_id = request_id

        # Attach to request object for template access
        request.trace_id = trace_id
        request.request_id = request_id

        start = time.monotonic()

        logger.info('request_received', extra={
            'traceId': trace_id,
            'requestId': request_id,
            'userId': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
            'sessionId': session_id,
            'method': request.method,
            'path': request.path,
            'step': 'request_received',
        })

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Only expose internal IDs to staff or in debug mode
        from django.conf import settings as _settings
        if _settings.DEBUG or (hasattr(request, 'user') and request.user.is_staff):
            response['X-Trace-Id'] = trace_id
            response['X-Request-Id'] = request_id

        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        logger.info('response_sent', extra={
            'traceId': trace_id,
            'requestId': request_id,
            'userId': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
            'sessionId': session_id,
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'duration_ms': duration_ms,
            'step': 'response_sent',
        })

        return response
