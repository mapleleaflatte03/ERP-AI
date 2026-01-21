"""
ERPX AI Accounting - OpenTelemetry Hooks (Skeleton)
===================================================
Distributed tracing skeleton for observability.
In production, configure with actual OTLP endpoint.
"""

import functools
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


# Mock tracer for when OpenTelemetry is not available
class MockSpan:
    """Mock span for development without OTLP"""

    def __init__(self, name: str, attributes: dict = None):
        self.name = name
        self.attributes = attributes or {}
        self.start_time = time.time()
        self.end_time = None
        self.status = "OK"
        self.events = []

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict = None):
        self.events.append({"name": name, "attributes": attributes or {}})

    def set_status(self, status: str, description: str = None):
        self.status = status

    def record_exception(self, exception: Exception):
        self.events.append(
            {"name": "exception", "attributes": {"type": type(exception).__name__, "message": str(exception)}}
        )

    def end(self):
        self.end_time = time.time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.record_exception(exc_val)
            self.set_status("ERROR", str(exc_val))
        self.end()
        return False


class MockTracer:
    """Mock tracer for development"""

    def __init__(self, name: str):
        self.name = name
        self._spans = []

    def start_span(self, name: str, attributes: dict = None) -> MockSpan:
        span = MockSpan(name, attributes)
        self._spans.append(span)
        return span

    @contextmanager
    def start_as_current_span(self, name: str, attributes: dict = None):
        span = self.start_span(name, attributes)
        try:
            yield span
        finally:
            span.end()


class TracingManager:
    """
    Manages OpenTelemetry tracing setup and access.
    Falls back to mock tracer if OpenTelemetry is not configured.
    """

    def __init__(self):
        self._tracer = None
        self._initialized = False
        self._use_mock = True

    def setup(self, service_name: str = "erpx-accounting", endpoint: str = None, sample_rate: float = 1.0):
        """
        Setup OpenTelemetry tracing.

        Args:
            service_name: Service name for traces
            endpoint: OTLP endpoint (e.g., http://localhost:4317)
            sample_rate: Sampling rate (0.0 to 1.0)
        """
        endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

        if not endpoint:
            print("OTEL endpoint not configured, using mock tracer")
            self._tracer = MockTracer(service_name)
            self._use_mock = True
            self._initialized = True
            return

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

            # Create resource
            resource = Resource(attributes={SERVICE_NAME: service_name})

            # Create sampler
            sampler = TraceIdRatioBased(sample_rate)

            # Create provider
            provider = TracerProvider(resource=resource, sampler=sampler)

            # Create exporter
            exporter = OTLPSpanExporter(endpoint=endpoint)

            # Add processor
            provider.add_span_processor(BatchSpanProcessor(exporter))

            # Set global provider
            trace.set_tracer_provider(provider)

            # Get tracer
            self._tracer = trace.get_tracer(service_name)
            self._use_mock = False
            self._initialized = True

            print(f"OpenTelemetry initialized: endpoint={endpoint}")

        except ImportError:
            print("OpenTelemetry not installed, using mock tracer")
            self._tracer = MockTracer(service_name)
            self._use_mock = True
            self._initialized = True
        except Exception as e:
            print(f"Failed to initialize OpenTelemetry: {e}, using mock tracer")
            self._tracer = MockTracer(service_name)
            self._use_mock = True
            self._initialized = True

    def get_tracer(self) -> Any:
        """Get the tracer instance"""
        if not self._initialized:
            self.setup()
        return self._tracer

    def is_mock(self) -> bool:
        """Check if using mock tracer"""
        return self._use_mock


# Global tracing manager
_tracing_manager = TracingManager()


def setup_tracing(service_name: str = "erpx-accounting", endpoint: str = None, sample_rate: float = 1.0):
    """Setup tracing globally"""
    _tracing_manager.setup(service_name, endpoint, sample_rate)


def get_tracer():
    """Get the global tracer"""
    return _tracing_manager.get_tracer()


def traced(name: str = None, attributes: dict = None):
    """
    Decorator to trace a function.

    Usage:
        @traced("process_document")
        def process_document(doc_id):
            ...
    """

    def decorator(func: Callable):
        span_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            # Build attributes
            span_attrs = attributes.copy() if attributes else {}
            span_attrs["function"] = func.__name__

            with tracer.start_as_current_span(span_name, attributes=span_attrs) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status("OK")
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status("ERROR", str(e))
                    raise

        return wrapper

    return decorator


@contextmanager
def trace_span(name: str, attributes: dict = None):
    """
    Context manager for manual span creation.

    Usage:
        with trace_span("process_invoice", {"doc_id": "123"}) as span:
            span.set_attribute("status", "processing")
            ...
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span


if __name__ == "__main__":
    # Test tracing
    setup_tracing()

    @traced("test_function", {"test_attr": "value"})
    def test_function(x: int) -> int:
        return x * 2

    result = test_function(5)
    print(f"Result: {result}")

    # Manual span
    with trace_span("manual_span", {"operation": "test"}) as span:
        span.set_attribute("custom_attr", "custom_value")
        span.add_event("event_happened", {"detail": "some detail"})

    print("Tracing test complete")
