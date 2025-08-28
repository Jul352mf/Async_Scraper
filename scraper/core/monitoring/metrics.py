"""Prometheus metrics collection and management."""

import time
from typing import Dict, Optional, Any, List
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager
import asyncio

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_client.metrics import MetricWrapperBase

from ..logger import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Supported metric types."""
    
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"


@dataclass
class MetricConfig:
    """Configuration for a metric."""
    
    name: str
    help: str
    labels: Optional[List[str]] = None
    buckets: Optional[List[float]] = None  # For histograms


class MetricsManager:
    """Manages Prometheus metrics collection."""
    
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self._metrics: Dict[str, MetricWrapperBase] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize metrics collection."""
        if self._initialized:
            return
            
        try:
            # Core application metrics
            await self._register_core_metrics()
            
            # API metrics
            await self._register_api_metrics()
            
            # Job processing metrics
            await self._register_job_metrics()
            
            # Database metrics
            await self._register_database_metrics()
            
            # Queue metrics
            await self._register_queue_metrics()
            
            # Browser metrics
            await self._register_browser_metrics()
            
            # Proxy metrics
            await self._register_proxy_metrics()
            
            self._initialized = True
            logger.info("Metrics manager initialized")
            
        except Exception as e:
            logger.error("Failed to initialize metrics", error=str(e))
            raise
            
    async def _register_core_metrics(self) -> None:
        """Register core application metrics."""
        metrics = [
            MetricConfig(
                "app_start_time",
                "Application start time in Unix timestamp",
            ),
            MetricConfig(
                "app_info",
                "Application information",
                labels=["version", "environment"]
            ),
        ]
        
        for config in metrics:
            self._create_metric(MetricType.GAUGE, config)
            
        # Set application start time
        self.get_gauge("app_start_time").set(time.time())
        
    async def _register_api_metrics(self) -> None:
        """Register API-related metrics."""
        metrics = [
            MetricConfig(
                "http_requests_total",
                "Total HTTP requests",
                labels=["method", "endpoint", "status_code", "tenant_id"]
            ),
            MetricConfig(
                "http_request_duration_seconds",
                "HTTP request duration in seconds",
                labels=["method", "endpoint", "tenant_id"],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            ),
            MetricConfig(
                "websocket_connections_total",
                "Total WebSocket connections",
                labels=["tenant_id"]
            ),
            MetricConfig(
                "websocket_messages_total",
                "Total WebSocket messages",
                labels=["type", "tenant_id"]
            ),
            MetricConfig(
                "api_key_requests_total",
                "Total requests per API key",
                labels=["api_key_id", "tenant_id"]
            ),
            MetricConfig(
                "rate_limit_exceeded_total",
                "Total rate limit exceeded events",
                labels=["api_key_id", "tenant_id"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            if "connections_total" in config.name:
                metric_type = MetricType.GAUGE
            self._create_metric(metric_type, config)
            
    async def _register_job_metrics(self) -> None:
        """Register job processing metrics."""
        metrics = [
            MetricConfig(
                "jobs_created_total",
                "Total jobs created",
                labels=["job_type", "tenant_id"]
            ),
            MetricConfig(
                "jobs_completed_total",
                "Total jobs completed",
                labels=["job_type", "status", "tenant_id"]
            ),
            MetricConfig(
                "job_duration_seconds",
                "Job processing duration in seconds",
                labels=["job_type", "tenant_id"],
                buckets=[1, 5, 10, 30, 60, 300, 600, 1800]
            ),
            MetricConfig(
                "job_queue_size",
                "Current job queue size",
                labels=["queue_name", "tenant_id"]
            ),
            MetricConfig(
                "job_retry_attempts_total",
                "Total job retry attempts",
                labels=["job_type", "tenant_id"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            if "queue_size" in config.name:
                metric_type = MetricType.GAUGE
            self._create_metric(metric_type, config)
            
    async def _register_database_metrics(self) -> None:
        """Register database-related metrics."""
        metrics = [
            MetricConfig(
                "db_connections_active",
                "Active database connections",
                labels=["database_name"]
            ),
            MetricConfig(
                "db_query_duration_seconds",
                "Database query duration in seconds",
                labels=["operation", "table"],
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
            ),
            MetricConfig(
                "db_queries_total",
                "Total database queries",
                labels=["operation", "table", "status"]
            ),
            MetricConfig(
                "db_connection_errors_total",
                "Total database connection errors",
                labels=["database_name", "error_type"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            if "connections_active" in config.name:
                metric_type = MetricType.GAUGE
            self._create_metric(metric_type, config)
            
    async def _register_queue_metrics(self) -> None:
        """Register queue-related metrics."""
        metrics = [
            MetricConfig(
                "queue_messages_total",
                "Total queue messages",
                labels=["operation", "queue_name", "status"]
            ),
            MetricConfig(
                "queue_processing_duration_seconds",
                "Queue message processing duration",
                labels=["queue_name"],
                buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
            ),
            MetricConfig(
                "queue_size_current",
                "Current queue size",
                labels=["queue_name"]
            ),
            MetricConfig(
                "queue_workers_active",
                "Active queue workers",
                labels=["queue_name"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            if any(x in config.name for x in ["size_current", "workers_active"]):
                metric_type = MetricType.GAUGE
            self._create_metric(metric_type, config)
            
    async def _register_browser_metrics(self) -> None:
        """Register browser automation metrics."""
        metrics = [
            MetricConfig(
                "browser_sessions_total",
                "Total browser sessions",
                labels=["browser_type", "status"]
            ),
            MetricConfig(
                "browser_page_load_duration_seconds",
                "Browser page load duration",
                labels=["browser_type"],
                buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 60.0]
            ),
            MetricConfig(
                "browser_contexts_active",
                "Active browser contexts",
                labels=["browser_type"]
            ),
            MetricConfig(
                "browser_screenshots_total",
                "Total screenshots taken",
                labels=["browser_type", "format"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            if "contexts_active" in config.name:
                metric_type = MetricType.GAUGE
            self._create_metric(metric_type, config)
            
    async def _register_proxy_metrics(self) -> None:
        """Register proxy-related metrics."""
        metrics = [
            MetricConfig(
                "proxy_requests_total",
                "Total proxy requests",
                labels=["proxy_id", "status"]
            ),
            MetricConfig(
                "proxy_response_time_seconds",
                "Proxy response time in seconds",
                labels=["proxy_id"],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
            ),
            MetricConfig(
                "proxy_health_checks_total",
                "Total proxy health checks",
                labels=["proxy_id", "result"]
            ),
            MetricConfig(
                "proxy_rotation_total",
                "Total proxy rotations",
                labels=["strategy"]
            ),
        ]
        
        for config in metrics:
            metric_type = MetricType.HISTOGRAM if config.buckets else MetricType.COUNTER
            self._create_metric(metric_type, config)
            
    def _create_metric(self, metric_type: MetricType, config: MetricConfig) -> None:
        """Create a metric and register it."""
        try:
            if metric_type == MetricType.COUNTER:
                metric = Counter(
                    config.name,
                    config.help,
                    labelnames=config.labels or [],
                    registry=self.registry
                )
            elif metric_type == MetricType.HISTOGRAM:
                metric = Histogram(
                    config.name,
                    config.help,
                    labelnames=config.labels or [],
                    buckets=config.buckets or [],
                    registry=self.registry
                )
            elif metric_type == MetricType.GAUGE:
                metric = Gauge(
                    config.name,
                    config.help,
                    labelnames=config.labels or [],
                    registry=self.registry
                )
            else:  # SUMMARY
                metric = Summary(
                    config.name,
                    config.help,
                    labelnames=config.labels or [],
                    registry=self.registry
                )
                
            self._metrics[config.name] = metric
            
        except Exception as e:
            logger.error(f"Failed to create metric {config.name}", error=str(e))
            
    def get_counter(self, name: str) -> Counter:
        """Get a counter metric."""
        return self._metrics[name]
        
    def get_histogram(self, name: str) -> Histogram:
        """Get a histogram metric."""
        return self._metrics[name]
        
    def get_gauge(self, name: str) -> Gauge:
        """Get a gauge metric."""
        return self._metrics[name]
        
    def get_summary(self, name: str) -> Summary:
        """Get a summary metric."""
        return self._metrics[name]
        
    @contextmanager
    def time_operation(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """Time an operation with a histogram metric."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            metric = self.get_histogram(metric_name)
            if labels:
                metric.labels(**labels).observe(duration)
            else:
                metric.observe(duration)
                
    def increment_counter(
        self, 
        name: str, 
        labels: Optional[Dict[str, str]] = None,
        amount: float = 1.0
    ) -> None:
        """Increment a counter metric."""
        try:
            metric = self.get_counter(name)
            if labels:
                metric.labels(**labels).inc(amount)
            else:
                metric.inc(amount)
        except KeyError:
            logger.warning(f"Counter metric {name} not found")
        except Exception as e:
            logger.error(f"Failed to increment counter {name}", error=str(e))
            
    def set_gauge(
        self, 
        name: str, 
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value."""
        try:
            metric = self.get_gauge(name)
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)
        except KeyError:
            logger.warning(f"Gauge metric {name} not found")
        except Exception as e:
            logger.error(f"Failed to set gauge {name}", error=str(e))
            
    def observe_histogram(
        self, 
        name: str, 
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value in a histogram metric."""
        try:
            metric = self.get_histogram(name)
            if labels:
                metric.labels(**labels).observe(value)
            else:
                metric.observe(value)
        except KeyError:
            logger.warning(f"Histogram metric {name} not found")
        except Exception as e:
            logger.error(f"Failed to observe histogram {name}", error=str(e))
            
    def get_metrics_data(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode('utf-8')
        
    def get_content_type(self) -> str:
        """Get the content type for Prometheus metrics."""
        return CONTENT_TYPE_LATEST
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Clear metrics
            self._metrics.clear()
            self._initialized = False
            logger.info("Metrics manager cleaned up")
        except Exception as e:
            logger.error("Failed to cleanup metrics manager", error=str(e))


# Global metrics manager instance
metrics_manager = MetricsManager()