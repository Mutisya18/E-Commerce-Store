"""
Journey logger — call log_step() from any view to emit a structured journey event.
All events share the traceId injected by JourneyLoggingMiddleware.
"""
import logging
import time
import hashlib
from apps.core.middleware import get_trace_id, get_request_id

logger = logging.getLogger('journey')


def log_step(journey: str, step: str, request=None, **metadata):
    """
    Emit one journey step.

    Usage:
        log_step('checkout', 'order_created', request, order_number='ORD-00001', total=4500)
    """
    trace_id = get_trace_id() or (request.trace_id if request and hasattr(request, 'trace_id') else 'unknown')
    request_id = get_request_id() or (request.request_id if request and hasattr(request, 'request_id') else 'unknown')

    user_id = None
    session_id = 'no-session'
    if request:
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
        if hasattr(request, 'session') and request.session.session_key:
            session_id = hashlib.sha256(request.session.session_key.encode()).hexdigest()[:12]

    logger.info(step, extra={
        'traceId': trace_id,
        'requestId': request_id,
        'journey': journey,
        'step': step,
        'userId': user_id,
        'sessionId': session_id,
        **metadata,
    })


class JourneyTimer:
    """Context manager to time a journey step."""
    def __init__(self, journey: str, step: str, request=None, **meta):
        self.journey = journey
        self.step = step
        self.request = request
        self.meta = meta

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, *_):
        duration_ms = round((time.monotonic() - self._start) * 1000, 2)
        result = 'error' if exc_type else 'success'
        log_step(self.journey, self.step, self.request,
                 duration_ms=duration_ms, result=result, **self.meta)
