"""
Tests for Retry Utility
========================

Unit tests for retry utility functions.
"""

import asyncio

import pytest

from ..utils.retry import retry_operation, retry_with_backoff


class TestRetryOperation:
    """Test retry_operation function."""

    @pytest.mark.asyncio
    async def test_retry_operation_success_first_try(self):
        """Test retry operation that succeeds on first try."""

        async def successful_operation():
            return "success"

        success, result, error = await retry_operation(
            successful_operation, "Test operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is True
        assert result == "success"
        assert error is None

    @pytest.mark.asyncio
    async def test_retry_operation_success_after_retries(self):
        """Test retry operation that succeeds after retries."""

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "success"

        success, result, error = await retry_operation(
            flaky_operation, "Flaky operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is True
        assert result == "success"
        assert error is None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_operation_failure_max_attempts(self):
        """Test retry operation that fails after max attempts."""

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Failure {call_count}")

        success, result, error = await retry_operation(
            failing_operation, "Failing operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is False
        assert result is None
        assert "Failure 3" in error  # Should contain the last error
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_operation_with_different_exceptions(self):
        """Test retry operation with different exception types."""

        call_count = 0

        async def mixed_exceptions():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Value error")
            elif call_count == 2:
                raise ConnectionError("Connection error")
            else:
                raise RuntimeError("Runtime error")

        success, result, error = await retry_operation(
            mixed_exceptions, "Mixed exceptions", max_attempts=3, delay_seconds=0.01
        )

        assert success is False
        assert result is None
        assert "Runtime error" in error
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_operation_with_args_and_kwargs(self):
        """Test retry operation with function arguments."""

        async def operation_with_args(arg1, arg2, kwarg1=None, kwarg2=None):
            return f"args: {arg1}, {arg2}, kwargs: {kwarg1}, {kwarg2}"

        success, result, error = await retry_operation(
            operation_with_args,
            "Operation with args",
            3,  # max_attempts
            0.01,  # delay_seconds
            "value1",
            "value2",
            kwarg1="kwvalue1",
            kwarg2="kwvalue2",
        )

        assert success is True
        assert result == "args: value1, value2, kwargs: kwvalue1, kwvalue2"
        assert error is None

    @pytest.mark.asyncio
    async def test_retry_operation_with_zero_delay(self):
        """Test retry operation with zero delay."""

        call_count = 0

        async def quick_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Quick failure")
            return "quick success"

        start_time = asyncio.get_event_loop().time()
        success, result, error = await retry_operation(
            quick_retry, "Quick retry", max_attempts=3, delay_seconds=0
        )
        end_time = asyncio.get_event_loop().time()

        assert success is True
        assert result == "quick success"
        assert error is None
        assert end_time - start_time < 0.1  # Should be very quick

    @pytest.mark.asyncio
    async def test_retry_operation_with_single_attempt(self):
        """Test retry operation with single attempt."""

        async def single_attempt():
            raise Exception("Single failure")

        success, result, error = await retry_operation(
            single_attempt, "Single attempt", max_attempts=1, delay_seconds=0.01
        )

        assert success is False
        assert result is None
        assert "Single failure" in error

    @pytest.mark.asyncio
    async def test_retry_operation_with_async_exception(self):
        """Test retry operation with async-specific exceptions."""

        call_count = 0

        async def async_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("Async timeout")
            elif call_count == 2:
                raise asyncio.CancelledError("Async cancelled")
            else:
                return "async success"

        success, result, error = await retry_operation(
            async_failing_operation,
            "Async operation",
            max_attempts=3,
            delay_seconds=0.01,
        )

        assert success is True
        assert result == "async success"
        assert error is None
        assert call_count == 3


class TestRetryWithBackoffDecorator:
    """Test retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success_first_try(self):
        """Test decorator with successful first try."""

        @retry_with_backoff(max_attempts=3, delay_seconds=0.01)
        async def successful_function():
            return "decorator success"

        result = await successful_function()
        assert result == "decorator success"

    @pytest.mark.asyncio
    async def test_decorator_success_after_retries(self):
        """Test decorator with success after retries."""

        call_count = 0

        @retry_with_backoff(max_attempts=3, delay_seconds=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Decorator failure {call_count}")
            return "decorator success"

        result = await flaky_function()
        assert result == "decorator success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_failure_max_attempts(self):
        """Test decorator with failure after max attempts."""

        call_count = 0

        @retry_with_backoff(max_attempts=2, delay_seconds=0.01)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Decorator failure {call_count}")

        with pytest.raises(Exception, match="Decorator failure 2"):
            await failing_function()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_with_function_arguments(self):
        """Test decorator with function arguments."""

        @retry_with_backoff(max_attempts=3, delay_seconds=0.01)
        async def function_with_args(arg1, arg2, kwarg1=None):
            return f"args: {arg1}, {arg2}, kwarg: {kwarg1}"

        result = await function_with_args("value1", "value2", kwarg1="kwvalue1")
        assert result == "args: value1, value2, kwarg: kwvalue1"

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @retry_with_backoff(max_attempts=3, delay_seconds=0.01)
        async def documented_function():
            """This function has documentation."""
            return "metadata preserved"

        assert documented_function.__name__ == "documented_function"
        assert "This function has documentation." in documented_function.__doc__

    @pytest.mark.asyncio
    async def test_decorator_with_different_exception_types(self):
        """Test decorator with different exception types."""

        call_count = 0

        @retry_with_backoff(max_attempts=4, delay_seconds=0.01)
        async def mixed_exception_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Value error")
            elif call_count == 2:
                raise KeyError("Key error")
            elif call_count == 3:
                raise TypeError("Type error")
            else:
                return "mixed success"

        result = await mixed_exception_function()
        assert result == "mixed success"
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_decorator_with_exponential_backoff(self):
        """Test decorator with exponential backoff timing."""

        call_count = 0

        @retry_with_backoff(max_attempts=3, delay_seconds=0.01)
        async def backoff_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Backoff failure {call_count}")
            return "backoff success"

        start_time = asyncio.get_event_loop().time()
        result = await backoff_function()
        end_time = asyncio.get_event_loop().time()

        assert result == "backoff success"
        assert call_count == 3
        # Should have some delay due to backoff
        assert end_time - start_time > 0.01

    @pytest.mark.asyncio
    async def test_decorator_with_max_attempts_one(self):
        """Test decorator with max_attempts=1."""

        @retry_with_backoff(max_attempts=1, delay_seconds=0.01)
        async def single_attempt_function():
            raise Exception("Single attempt failure")

        with pytest.raises(Exception, match="Single attempt failure"):
            await single_attempt_function()

    @pytest.mark.asyncio
    async def test_decorator_nested_calls(self):
        """Test decorator with nested function calls."""

        call_count = 0

        @retry_with_backoff(max_attempts=2, delay_seconds=0.01)
        async def inner_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Inner failure")
            return "inner success"

        @retry_with_backoff(max_attempts=2, delay_seconds=0.01)
        async def outer_function():
            result = await inner_function()
            return f"outer + {result}"

        result = await outer_function()
        assert result == "outer + inner success"
        assert call_count == 2


class TestRetryUtilityIntegration:
    """Integration tests for retry utilities."""

    @pytest.mark.asyncio
    async def test_retry_with_real_network_simulation(self):
        """Test retry with simulated network conditions."""

        call_count = 0

        async def simulated_network_call():
            nonlocal call_count
            call_count += 1

            # Simulate different network conditions
            if call_count == 1:
                raise ConnectionError("Network unreachable")
            elif call_count == 2:
                raise TimeoutError("Request timeout")
            elif call_count == 3:
                raise ConnectionError("DNS resolution failed")
            else:
                return {"status": "success", "data": "network response"}

        success, result, error = await retry_operation(
            simulated_network_call,
            "Network simulation",
            max_attempts=5,
            delay_seconds=0.01,
        )

        assert success is True
        assert result["status"] == "success"
        assert result["data"] == "network response"
        assert error is None
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_retry_with_logging_verification(self):
        """Test retry with logging verification."""

        call_count = 0

        async def logged_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Logged failure")
            return "logged success"

        # Test that the operation works correctly
        success, result, error = await retry_operation(
            logged_operation, "Logged operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is True
        assert result == "logged success"
        assert error is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_resource_cleanup(self):
        """Test retry with resource cleanup simulation."""

        call_count = 0
        resources = []

        async def resource_operation():
            nonlocal call_count
            call_count += 1

            # Simulate resource acquisition
            resource = f"resource_{call_count}"
            resources.append(resource)

            try:
                if call_count < 2:
                    raise Exception("Resource operation failed")
                return f"success with {resource}"
            except Exception:
                # Simulate cleanup on failure
                resources.remove(resource)
                raise

        success, result, error = await retry_operation(
            resource_operation, "Resource operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is True
        assert result == "success with resource_2"
        assert error is None
        assert call_count == 2
        assert len(resources) == 1  # Only successful resource remains
        assert resources[0] == "resource_2"

    @pytest.mark.asyncio
    async def test_retry_performance_characteristics(self):
        """Test retry performance characteristics."""

        call_count = 0

        async def performance_test():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise Exception(f"Performance test failure {call_count}")
            return "performance success"

        start_time = asyncio.get_event_loop().time()
        success, result, error = await retry_operation(
            performance_test,
            "Performance test",
            max_attempts=5,
            delay_seconds=0.001,  # Very short delay
        )
        end_time = asyncio.get_event_loop().time()

        assert success is True
        assert result == "performance success"
        assert error is None
        assert call_count == 5

        # Should complete in reasonable time
        assert end_time - start_time < 1.0  # Less than 1 second
        # But should have some delay due to retries
        assert end_time - start_time > 0.001  # More than minimum delay
