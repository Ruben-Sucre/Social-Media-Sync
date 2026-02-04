"""Utilities: human-like waits and retry decorator.

Provide `random_wait(min_seconds, max_seconds)` to simulate human delays
and a `retry` decorator implementing exponential backoff with jitter.
These helpers honor the `SKIP_WAITS` environment variable to bypass
sleeping during tests or CI when desired.
"""
from __future__ import annotations

import os
import random
import time
import functools
from typing import Callable, Any


def _skip_waits() -> bool:
    val = os.environ.get("SKIP_WAITS")
    if val is None:
        return False
    return val.lower() in ("1", "true", "yes")


def random_wait(min_seconds: float = 1.0, max_seconds: float = 6.0) -> None:
    """Sleep for a random duration between min_seconds and max_seconds.

    If `SKIP_WAITS` is set in the environment, this is a no-op.
    """
    if _skip_waits():
        return
    wait = random.uniform(float(min_seconds), float(max_seconds))
    time.sleep(wait)


def retry(
    retries: int = 3,
    base: float = 5.0,
    factor: float = 3.0,
    max_wait: float = 90.0,
    jitter: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to retry a function with exponential backoff and jitter.

    Example backoff sequence with base=5 and factor=3: 5, 15, 45, ...
    A small jitter (±10%) is applied when `jitter=True`.

    If `SKIP_WAITS` is set, sleeping between retries is skipped.
    """

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    last_exc = exc
                    if attempt >= retries:
                        break
                    wait = base * (factor ** (attempt - 1))
                    if wait > max_wait:
                        wait = max_wait
                    if jitter:
                        # apply small +/- 10% jitter
                        jitter_amount = wait * 0.1
                        wait = wait + random.uniform(-jitter_amount, jitter_amount)
                    if not _skip_waits():
                        time.sleep(max(0.0, wait))
            # Retries exhausted
            raise last_exc

        return _wrapper

    return _decorator
