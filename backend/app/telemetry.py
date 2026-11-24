"""Instrumentación OpenTelemetry (OTLP) -> OTel Collector -> OpenObserve.

Emite las tres señales que pide RF-04:
  * Trazas: cada petición HTTP (FastAPI) + cada consulta SQL (SQLAlchemy).
  * Métricas: latencia, volumen y errores por endpoint (http_requests_total,
    http_request_duration_ms) con atributos endpoint/method/status_code.
  * Logs: registro estructurado de cada petición y de las excepciones.

Se desactiva con OTEL_ENABLED=false (por ejemplo en las pruebas unitarias).
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request

log = logging.getLogger("app")

ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"

_req_counter = None
_req_duration = None
_err_counter = None


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in ("endpoint", "method", "status_code", "duration_ms", "client_ip",
                  "otelTraceID", "otelSpanID"):
            if hasattr(record, k):
                data[k] = getattr(record, k)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_telemetry(app: FastAPI, engine) -> None:
    global _req_counter, _req_duration, _err_counter

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    if not ENABLED:
        log.info("OpenTelemetry desactivado (OTEL_ENABLED=false)")
        return

    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # El endpoint se toma de OTEL_EXPORTER_OTLP_ENDPOINT (p. ej. http://otel-collector:4318)
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "tienda-backend"),
        "deployment.environment": os.getenv("APP_ENV", "production"),
        "service.version": os.getenv("APP_VERSION", "dev"),
    })

    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tp)

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=15000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(lp)
    root.addHandler(LoggingHandler(level=logging.INFO, logger_provider=lp))
    LoggingInstrumentor().instrument(set_logging_format=False)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    SQLAlchemyInstrumentor().instrument(engine=engine)

    meter = metrics.get_meter("tienda-backend")
    _req_counter = meter.create_counter(
        "http_requests_total", unit="1", description="Peticiones HTTP por endpoint")
    _err_counter = meter.create_counter(
        "http_errors_total", unit="1", description="Respuestas HTTP 4xx/5xx por endpoint")
    _req_duration = meter.create_histogram(
        "http_request_duration_ms", unit="ms", description="Latencia por endpoint")
    log.info("OpenTelemetry activado")


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            log.exception("Excepción no controlada", extra={
                "endpoint": request.url.path, "method": request.method, "status_code": 500})
            raise
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            route = request.scope.get("route")
            endpoint = getattr(route, "path", request.url.path)
            if endpoint != "/health":
                attrs = {"endpoint": endpoint, "method": request.method,
                         "status_code": status_code}
                if _req_counter is not None:
                    _req_counter.add(1, attrs)
                    _req_duration.record(elapsed, attrs)
                    if status_code >= 400:
                        _err_counter.add(1, attrs)
                level = logging.ERROR if status_code >= 500 else (
                    logging.WARNING if status_code >= 400 else logging.INFO)
                log.log(level, f"{request.method} {endpoint} -> {status_code}", extra={
                    **attrs, "duration_ms": round(elapsed, 2),
                    "client_ip": request.client.host if request.client else None})
