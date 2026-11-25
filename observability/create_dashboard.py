"""Crea (o recrea) el dashboard "Tienda · CI/CD y Observabilidad" en OpenObserve.

Uso:
    python observability/create_dashboard.py http://<IP_EC2>:5080 admin@tienda.com 'Complexpass#123'

Primero ejecuta cada consulta contra OpenObserve para validar que funcione y
después crea el dashboard (RF-05 / RF-06 / criterio 3).
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request

URL, USER, PASSWORD = (sys.argv[1:4] + [None] * 3)[:3]
URL = (URL or "http://localhost:5080").rstrip("/")
USER = USER or "admin@tienda.com"
PASSWORD = PASSWORD or "Complexpass#123"
ORG = "default"
TITLE = "Tienda · CI/CD y Observabilidad"
AUTH = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()


def call(method, path, body=None):
    req = urllib.request.Request(
        URL + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:400]}")


def field(alias, label, is_time=False):
    return {"label": label, "alias": alias, "column": alias, "color": None,
            "treatAsNonTimestamp": not is_time, "showFieldAsJson": False}


PANEL_CONFIG = {
    "show_legends": True, "legends_position": None, "decimals": 2,
    "line_thickness": 1.5, "step_value": "0", "top_results_others": False,
    "axis_border_show": False, "label_option": {"rotate": 0}, "show_symbol": False,
    "line_interpolation": "smooth", "legend_width": {"unit": "px"},
    "legend_height": {"unit": "px"}, "base_map": {"type": "osm"},
    "map_type": {"type": "world"}, "map_view": {"zoom": 1, "lat": 0, "lng": 0},
    "map_symbol_style": {"size": "by Value", "size_by_value": {"min": 1, "max": 100},
                         "size_fixed": 2},
    "drilldown": [], "mark_line": [], "override_config": [], "connect_nulls": True,
    "no_value_replacement": "", "wrap_table_cells": False, "table_transpose": False,
    "table_dynamic_columns": False, "mappings": [],
    "color": {"mode": "palette-classic-by-series", "fixedColor": ["#53ca53"],
              "seriesBy": "last", "colorBySeries": []},
    "trellis": {"layout": None, "num_of_columns": 1, "group_by_y_axis": False},
    "show_gridlines": True,
}

panels = []


def panel(ptype, title, desc, stream, stream_type, sql, x, y, breakdown=(),
          layout=(0, 0, 96, 14), unit=None, decimals=2):
    cfg = json.loads(json.dumps(PANEL_CONFIG))
    cfg["decimals"] = decimals
    if unit:
        cfg["unit"] = unit
    if ptype == "metric":
        cfg["show_legends"] = False
    n = len(panels) + 1
    panels.append({
        "id": f"p{n}", "type": ptype, "title": title, "description": desc,
        "config": cfg, "queryType": "sql",
        "queries": [{
            "query": sql, "vrlFunctionQuery": "", "customQuery": True,
            "fields": {"stream": stream, "stream_type": stream_type,
                       "x": list(x), "y": list(y), "z": [], "breakdown": list(breakdown),
                       "filter": {"filterType": "group", "logicalOperator": "AND",
                                  "conditions": []}},
            "config": {"promql_legend": "", "layer_type": "scatter", "weight_fixed": 1,
                       "limit": 0, "min": 0, "max": 100, "time_shift": [],
                       "query_label": ""},
            "joins": [],
        }],
        "layout": {"x": layout[0], "y": layout[1], "w": layout[2], "h": layout[3], "i": n},
        "htmlContent": "", "markdownContent": "", "customChartContent": "",
    })


T = field("x_axis_1", "Tiempo", is_time=True)
Y = lambda label: field("y_axis_1", label)  # noqa: E731

# ---------- Fila 1: indicadores ----------
panel("metric", "Despliegues exitosos", "Eventos deploy/success enviados por GitHub Actions",
      "cicd_events", "logs",
      "SELECT count(*) AS y_axis_1 FROM \"cicd_events\" WHERE event_type = 'deploy' AND status = 'success'",
      [], [Y("Deploys")], layout=(0, 0, 48, 8), decimals=0)
panel("metric", "Despliegues bloqueados", "Commits cuyas pruebas fallaron (no se abrió SSH a EC2)",
      "cicd_events", "logs",
      "SELECT count(*) AS y_axis_1 FROM \"cicd_events\" WHERE event_type = 'deploy_blocked'",
      [], [Y("Bloqueados")], layout=(48, 0, 48, 8), decimals=0)
panel("metric", "Peticiones HTTP", "Total de peticiones a la API (logs OTel)",
      "default", "logs",
      "SELECT count(*) AS y_axis_1 FROM \"default\" WHERE endpoint LIKE '/api%'",
      [], [Y("Peticiones")], layout=(96, 0, 48, 8), decimals=0)
panel("metric", "Errores HTTP (4xx/5xx)", "Respuestas con statusCode >= 400",
      "default", "logs",
      "SELECT count(*) AS y_axis_1 FROM \"default\" WHERE endpoint LIKE '/api%' AND status_code >= 400",
      [], [Y("Errores")], layout=(144, 0, 48, 8), decimals=0)

# ---------- Fila 2: pipeline ----------
panel("table", "Ejecuciones del pipeline CI/CD (RF-03)",
      "Resultado de pruebas y despliegues: commit, rama y usuario ejecutor",
      "cicd_events", "logs",
      "SELECT _timestamp AS x_axis_1, event_type AS x_axis_2, status AS x_axis_3, "
      "commit_short AS x_axis_4, branch AS x_axis_5, actor AS x_axis_6, detail AS x_axis_7, "
      "count(*) AS y_axis_1 FROM \"cicd_events\" "
      "GROUP BY x_axis_1, x_axis_2, x_axis_3, x_axis_4, x_axis_5, x_axis_6, x_axis_7 "
      "ORDER BY x_axis_1 DESC",
      [T, field("x_axis_2", "Evento"), field("x_axis_3", "Estado"), field("x_axis_4", "Commit"),
       field("x_axis_5", "Rama"), field("x_axis_6", "Usuario"), field("x_axis_7", "Detalle")],
      [Y("Eventos")], layout=(0, 8, 192, 13), decimals=0)

# ---------- Fila 3-4: infraestructura EC2 (RF-05) ----------
panel("line", "CPU de la EC2 (%)", "100 - % idle promedio de todos los núcleos (hostmetrics)",
      "system_cpu_utilization", "metrics",
      "SELECT histogram(_timestamp) AS x_axis_1, 100 - AVG(value) * 100 AS y_axis_1 "
      "FROM \"system_cpu_utilization\" WHERE state = 'idle' GROUP BY x_axis_1 ORDER BY x_axis_1",
      [T], [Y("CPU %")], layout=(0, 21, 96, 14), unit="percent")
panel("line", "Memoria RAM usada (%)", "system.memory.utilization (state = used)",
      "system_memory_utilization", "metrics",
      "SELECT histogram(_timestamp) AS x_axis_1, AVG(value) * 100 AS y_axis_1 "
      "FROM \"system_memory_utilization\" WHERE state = 'used' GROUP BY x_axis_1 ORDER BY x_axis_1",
      [T], [Y("RAM %")], layout=(96, 21, 96, 14), unit="percent")
panel("area", "Ancho de banda de la EC2 (KB/s, interfaz ens5)",
      "Bytes recibidos/transmitidos por minuto en la interfaz de red de la instancia",
      "system_network_io", "metrics",
      "SELECT histogram(_timestamp, '1 minute') AS x_axis_1, direction AS x_axis_2, "
      "(MAX(value) - MIN(value)) / 60 / 1024 AS y_axis_1 FROM \"system_network_io\" "
      "WHERE device = 'ens5' GROUP BY x_axis_1, x_axis_2 ORDER BY x_axis_1",
      [T], [Y("KB/s")], breakdown=[field("x_axis_2", "Dirección")], layout=(0, 35, 96, 14))
panel("line", "Temperatura (°C)",
      "Sensor real si existe; en EC2 (virtualizada) es una estimación por carga de CPU (estimated=true)",
      "host_temperature", "logs",
      "SELECT histogram(_timestamp) AS x_axis_1, AVG(temp_c) AS y_axis_1 "
      "FROM \"host_temperature\" GROUP BY x_axis_1 ORDER BY x_axis_1",
      [T], [Y("°C")], layout=(96, 35, 96, 14), decimals=1)

# ---------- Fila 5-6: endpoints (RF-04) ----------
panel("bar", "Peticiones por endpoint", "Volumen de peticiones por endpoint expuesto",
      "default", "logs",
      "SELECT endpoint AS x_axis_1, count(*) AS y_axis_1 FROM \"default\" "
      "WHERE endpoint LIKE '/api%' GROUP BY x_axis_1 ORDER BY y_axis_1 DESC",
      [field("x_axis_1", "Endpoint")], [Y("Peticiones")], layout=(0, 49, 96, 14), decimals=0)
panel("line", "Latencia promedio por endpoint (ms)", "duration_ms promedio por endpoint",
      "default", "logs",
      "SELECT histogram(_timestamp) AS x_axis_1, endpoint AS x_axis_2, AVG(duration_ms) AS y_axis_1 "
      "FROM \"default\" WHERE endpoint LIKE '/api%' GROUP BY x_axis_1, x_axis_2 ORDER BY x_axis_1",
      [T], [Y("ms")], breakdown=[field("x_axis_2", "Endpoint")], layout=(96, 49, 96, 14))
panel("line", "Peticiones por segundo", "Throughput de la API (promedio por minuto)",
      "default", "logs",
      "SELECT histogram(_timestamp, '1 minute') AS x_axis_1, count(*) / 60.0 AS y_axis_1 "
      "FROM \"default\" WHERE endpoint LIKE '/api%' GROUP BY x_axis_1 ORDER BY x_axis_1",
      [T], [Y("req/s")], layout=(0, 63, 96, 14), decimals=3)
panel("table", "Errores HTTP por endpoint y statusCode", "Tasa de errores por endpoint",
      "default", "logs",
      "SELECT endpoint AS x_axis_1, method AS x_axis_2, status_code AS x_axis_3, count(*) AS y_axis_1 "
      "FROM \"default\" WHERE endpoint LIKE '/api%' AND status_code >= 400 "
      "GROUP BY x_axis_1, x_axis_2, x_axis_3 ORDER BY y_axis_1 DESC",
      [field("x_axis_1", "Endpoint"), field("x_axis_2", "Método"), field("x_axis_3", "statusCode")],
      [Y("Errores")], layout=(96, 63, 96, 14), decimals=0)

# ---------- Fila 7: métricas OTel y trazas ----------
panel("bar", "Métrica OTel http_requests_total por endpoint y statusCode",
      "Contador OpenTelemetry (acumulado desde el último arranque del backend)",
      "http_requests_total", "metrics",
      "SELECT endpoint AS x_axis_1, status_code AS x_axis_2, MAX(value) AS y_axis_1 "
      "FROM \"http_requests_total\" GROUP BY x_axis_1, x_axis_2 ORDER BY y_axis_1 DESC",
      [field("x_axis_1", "Endpoint")], [Y("Peticiones")],
      breakdown=[field("x_axis_2", "statusCode")], layout=(0, 77, 96, 14), decimals=0)
panel("table", "Trazas recientes de peticiones HTTP",
      "Spans raíz de FastAPI; abrir el trace_id en Trazas para ver las consultas SQL",
      "default", "traces",
      "SELECT _timestamp AS x_axis_1, operation_name AS x_axis_2, trace_id AS x_axis_3, "
      "AVG(duration) / 1000.0 AS y_axis_1 FROM \"default\" "
      "WHERE operation_name NOT LIKE '%http send%' AND operation_name NOT LIKE '%http receive%' "
      "AND (operation_name LIKE 'GET %' OR operation_name LIKE 'POST %' OR operation_name LIKE 'PUT %' "
      "OR operation_name LIKE 'DELETE %') "
      "GROUP BY x_axis_1, x_axis_2, x_axis_3 ORDER BY x_axis_1 DESC LIMIT 100",
      [T, field("x_axis_2", "Operación"), field("x_axis_3", "trace_id")], [Y("Duración (ms)")],
      layout=(96, 77, 96, 14))


# ---------- Fila 8: alertas (RF-06) ----------
panel("table", "Alertas disparadas (RF-06)",
      "Notificaciones enviadas por las alertas de OpenObserve (create_alerts.py)",
      "alertas_disparadas", "logs",
      "SELECT _timestamp AS x_axis_1, alerta AS x_axis_2, stream AS x_axis_3, "
      "condicion AS x_axis_4, count(*) AS y_axis_1 FROM \"alertas_disparadas\" "
      "GROUP BY x_axis_1, x_axis_2, x_axis_3, x_axis_4 ORDER BY x_axis_1 DESC",
      [T, field("x_axis_2", "Alerta"), field("x_axis_3", "Stream"), field("x_axis_4", "Condición")],
      [Y("Veces")], layout=(0, 91, 192, 12), decimals=0)


def validate():
    end = int(time.time() * 1_000_000)
    start = end - 24 * 3600 * 1_000_000
    ok = True
    for p in panels:
        q = p["queries"][0]
        stype = q["fields"]["stream_type"]
        try:
            res = call("POST", f"/api/{ORG}/_search?type={stype}",
                       {"query": {"sql": q["query"], "start_time": start, "end_time": end,
                                  "size": 5}})
            print(f"  OK  {len(res.get('hits', [])):>3} filas  {p['title']}")
        except RuntimeError as e:
            ok = False
            print(f"  ERR {p['title']}: {e}")
    return ok


def main():
    print("Validando consultas…")
    if not validate():
        sys.exit("Hay consultas con error; no se creó el dashboard.")

    existing = call("GET", f"/api/{ORG}/dashboards").get("dashboards", [])
    for d in existing:
        if d.get("title") == TITLE or d.get("v8", {}).get("title") == TITLE:
            did = d.get("dashboard_id") or d.get("v8", {}).get("dashboardId")
            folder = d.get("folder_id", "default")
            call("DELETE", f"/api/{ORG}/dashboards/{did}?folder={folder}")
            print(f"Dashboard anterior eliminado ({did})")

    dashboard = {
        "version": 8, "title": TITLE,
        "description": "Pipeline CI/CD, endpoints de la API (logs, métricas, trazas) e infraestructura EC2",
        "role": "", "owner": "",
        "variables": {"list": [], "showDynamicFilters": False},
        "defaultDatetimeDuration": {"type": "relative", "relativeTimePeriod": "12h",
                                    "startTime": 0, "endTime": 0},
        "tabs": [{"tabId": "default", "name": "Resumen", "panels": panels}],
    }
    res = call("POST", f"/api/{ORG}/dashboards", dashboard)
    did = res.get("dashboardId") or res.get("v8", {}).get("dashboardId") or res.get("dashboard_id")
    print(f"Dashboard creado: {did}")
    print(f"{URL}/web/dashboards/view?org_identifier={ORG}&dashboard={did}&folder=default")


if __name__ == "__main__":
    main()
