"""
Retry Utilities
===============

Utility functions for implementing retry logic with exponential backoff.
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import structlog

T = TypeVar("T")
logger = structlog.get_logger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    delay_seconds: int = 30,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T | Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each attempt
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T | Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            current_delay = delay_seconds

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay=current_delay,
                        error=str(e),
                    )

                    await asyncio.sleep(current_delay)
                    current_delay = int(current_delay * backoff_factor)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Unexpected retry logic error in {func.__name__}")

        return wrapper

    return decorator


async def retry_operation(
    operation: Callable[..., T | Awaitable[T]],
    operation_name: str,
    max_attempts: int = 3,
    delay_seconds: int = 30,
    *args: Any,
    **kwargs: Any,
) -> tuple[bool, T | None, str | None]:
    """Execute an operation with retry logic.

    Args:
        operation: Async function to execute
        operation_name: Name of the operation for logging
        max_attempts: Maximum number of retry attempts
        delay_seconds: Delay between retries
        *args: Positional arguments for operation
        **kwargs: Keyword arguments for operation

    Returns:
        Tuple of (success, result, error_message)
    """
    last_error: str | None = None

    for attempt in range(max_attempts):
        try:
            result = operation(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return True, result, None
        except Exception as e:
            last_error = str(e)

            if attempt == max_attempts - 1:
                logger.error(
                    f"{operation_name} failed after {max_attempts} attempts",
                    operation=operation_name,
                    attempts=max_attempts,
                    error=last_error,
                )
                return False, None, last_error

            logger.warning(
                f"{operation_name} failed, retrying",
                operation=operation_name,
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay=delay_seconds,
                error=last_error,
            )

            await asyncio.sleep(delay_seconds)

    return False, None, last_error or "Unknown error"
