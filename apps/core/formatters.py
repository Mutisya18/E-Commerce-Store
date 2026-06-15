import json
import logging
import datetime


class JourneyJsonFormatter(logging.Formatter):
    """
    Outputs every log record as a single JSON line matching the spec format:
    {
      "timestamp": "...",
      "traceId": "...",
      "journey": "...",
      "step": "...",
      "userId": ...,
      "sessionId": "...",
      "requestId": "...",
      "level": "INFO",
      "logger": "journey",
      "metadata": { ...extra fields }
    }
    """

    # Fields promoted to top-level in the spec
    TOP_LEVEL = {'traceId', 'requestId', 'journey', 'step', 'userId', 'sessionId'}
    # Fields that are stdlib logging internals — exclude from metadata
    SKIP = {
        'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
        'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
        'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
        'processName', 'process', 'message', 'asctime',
    }

    def format(self, record):
        ts = datetime.datetime.utcfromtimestamp(record.created).strftime('%Y-%m-%dT%H:%M:%S.') + \
             f'{int(record.msecs):03d}Z'

        out = {
            'timestamp': ts,
            'level': record.levelname,
            'logger': record.name,
            'traceId': getattr(record, 'traceId', None),
            'requestId': getattr(record, 'requestId', None),
            'journey': getattr(record, 'journey', None),
            'step': getattr(record, 'step', record.getMessage()),
            'userId': getattr(record, 'userId', None),
            'sessionId': getattr(record, 'sessionId', None),
        }

        # Everything else goes into metadata
        metadata = {
            k: v for k, v in record.__dict__.items()
            if k not in self.TOP_LEVEL and k not in self.SKIP
        }
        if metadata:
            out['metadata'] = metadata

        if record.exc_info:
            out['exception'] = self.formatException(record.exc_info)

        return json.dumps(out, default=str)
