"""Retry utilities for async functions."""

from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])


def async_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable[[F], F]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts.
        initial_wait: Initial wait time in seconds.
        max_wait: Maximum wait time in seconds.

    Returns:
        Decorated async function with retry logic.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_config = AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=initial_wait,
                    max=max_wait,
                ),
            )

            async for attempt in retry_config:
                with attempt:
                    return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator

