"""Distributed tracing with OpenTelemetry."""

import time
from typing import Dict, Optional, Any, List
from contextlib import contextmanager
import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

from ..logger import get_logger

logger = get_logger(__name__)


class TracingManager:
    """Manages distributed tracing setup."""
    
    def __init__(self) -> None:
        self._initialized = False
        self._tracer = None
        self._meter = None
        
    async def initialize(
        self, 
        service_name: str = "async-scraper",
        environment: str = "development"
    ) -> None:
        """Initialize tracing."""
        if self._initialized:
            return
            
        try:
            # Set up tracer provider
            tracer_provider = TracerProvider(
                resource=self._create_resource(service_name, environment)
            )
            trace.set_tracer_provider(tracer_provider)
            
            # Create tracer
            self._tracer = trace.get_tracer(__name__)
            
            # Initialize instrumentations
            self._setup_instrumentations()
            
            self._initialized = True
            logger.info("Tracing initialized", service_name=service_name)
            
        except Exception as e:
            logger.error("Failed to initialize tracing", error=str(e))
            raise
            
    def _create_resource(self, service_name: str, environment: str):
        """Create OpenTelemetry resource."""
        from opentelemetry.sdk.resources import Resource
        
        return Resource.create({
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": environment,
        })
        
    def _setup_instrumentations(self) -> None:
        """Set up automatic instrumentation."""
        # FastAPI instrumentation will be set up by the API server
        # HTTP client instrumentation
        AioHttpClientInstrumentor().instrument()
        
    def get_tracer(self):
        """Get the tracer instance."""
        return self._tracer
        
    @contextmanager
    def trace_operation(
        self, 
        name: str, 
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Context manager for tracing operations."""
        if not self._tracer:
            yield
            return
            
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
                
    async def trace_async_operation(
        self,
        name: str,
        operation,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Trace an async operation."""
        if not self._tracer:
            return await operation
            
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            try:
                result = await operation
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
                
    def add_span_attributes(self, attributes: Dict[str, Any]) -> None:
        """Add attributes to current span."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            for key, value in attributes.items():
                current_span.set_attribute(key, value)
                
    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to current span."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(name, attributes or {})
            
    def set_span_status(self, status_code: trace.StatusCode, description: str = "") -> None:
        """Set status of current span."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_status(trace.Status(status_code, description))
            
    async def cleanup(self) -> None:
        """Cleanup tracing resources."""
        try:
            # Cleanup would go here
            self._initialized = False
            logger.info("Tracing cleaned up")
        except Exception as e:
            logger.error("Failed to cleanup tracing", error=str(e))


# Global tracer instance
tracer = TracingManager()