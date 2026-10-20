"""Bounded retries for public, unauthenticated WeChat discovery requests."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time

import requests


class TemporaryFailure(ValueError):
    pass


def retry(call, *, attempts=3, sleep=time.sleep):
    for attempt in range(attempts):
        try:
            return call()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, TemporaryFailure) as exc:
            response = getattr(exc, 'response', None)
            code = response.status_code if response is not None else None
            if code is not None and code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == attempts - 1:
                raise
            delay = ((15, 45) if code == 429 or isinstance(exc, TemporaryFailure) else (2, 8))[min(attempt, 1)]
            if response is not None:
                hint = response.headers.get('Retry-After')
                if hint:
                    try:
                        delay = max(0, float(hint))
                    except ValueError:
                        try:
                            delay = max(0, (parsedate_to_datetime(hint) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError):
                            pass
                    # Do not retry earlier than requested, or block a runner indefinitely.
                    if delay > 120:
                        raise
                response.close()
            sleep(delay)
