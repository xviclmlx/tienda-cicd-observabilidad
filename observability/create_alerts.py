"""Crea las alertas operativas en OpenObserve (RF-06).

Uso:
    python observability/create_alerts.py http://<IP_EC2>:5080 admin@tienda.com 'Complexpass#123'

Crea:
  * Plantilla "tienda_alerta_json" (cuerpo JSON de la notificación).
  * Destino "tienda_registro_alertas": webhook HTTP hacia el propio OpenObserve,
    que guarda cada alerta disparada en el stream de logs "alertas_disparadas"
    (así se pueden ver en la interfaz y en el dashboard sin configurar SMTP/Slack).
  * 4 alertas programadas: pipeline fallido, errores HTTP, CPU alta y RAM alta.
Es idempotente: si algo ya existe, lo reemplaza.
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

URL, USER, PASSWORD = (sys.argv[1:4] + [None] * 3)[:3]
URL = (URL or "http://localhost:5080").rstrip("/")
USER = USER or "admin@tienda.com"
PASSWORD = PASSWORD or "Complexpass#123"
ORG = "default"
AUTH = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()

TEMPLATE = "tienda_alerta_json"
DESTINATION = "tienda_registro_alertas"


def call(method, path, body=None, ok404=False):
    req = urllib.request.Request(
        URL + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if ok404 and e.code == 404:
            return None
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:500]}")


# ---------- Plantilla ----------
template_body = json.dumps([{
    "alerta": "{alert_name}",
    "stream": "{stream_name}",
    "tipo": "{alert_type}",
    "condicion": "{alert_operator} {alert_threshold}",
    "periodo_min": "{alert_period}",
    "resultados": "{alert_count}",
    "inicio": "{alert_start_time}",
    "fin": "{alert_end_time}",
    "url": "{alert_url}",
}])
tpl = {"name": TEMPLATE, "title": "Alerta Tienda", "body": template_body, "type": "http"}
if call("GET", f"/api/{ORG}/alerts/templates/{TEMPLATE}", ok404=True):
    call("PUT", f"/api/{ORG}/alerts/templates/{TEMPLATE}", tpl)
else:
    call("POST", f"/api/{ORG}/alerts/templates", tpl)
print(f"Plantilla: {TEMPLATE}")

# ---------- Destino (webhook hacia el propio OpenObserve) ----------
dest = {
    "name": DESTINATION, "type": "http", "method": "post",
    # OpenObserve bloquea webhooks a IPs privadas (protección SSRF), así que se usa
    # la URL pública del propio servidor (la misma que se pasa al script)
    "url": f"{URL}/api/{ORG}/alertas_disparadas/_json",
    "headers": {"Authorization": AUTH, "Content-Type": "application/json"},
    "template": TEMPLATE, "skip_tls_verify": False,
}
if call("GET", f"/api/{ORG}/alerts/destinations/{DESTINATION}", ok404=True):
    call("PUT", f"/api/{ORG}/alerts/destinations/{DESTINATION}", dest)
else:
    call("POST", f"/api/{ORG}/alerts/destinations", dest)
print(f"Destino: {DESTINATION} -> stream alertas_disparadas")

# ---------- Alertas ----------
ALERTS = [
    {
        "name": "pipeline_cicd_fallido",
        "description": "Pruebas fallidas o despliegue a EC2 bloqueado/fallido",
        "stream_type": "logs", "stream_name": "cicd_events",
        "sql": "SELECT event_type, status, commit_short, branch, actor FROM \"cicd_events\" "
               "WHERE status = 'failure'",
        "period": 5, "frequency": 1,
    },
    {
        "name": "errores_http_altos",
        "description": "10 o más respuestas 4xx/5xx en 5 minutos",
        "stream_type": "logs", "stream_name": "default",
        "sql": "SELECT count(*) AS errores FROM \"default\" "
               "WHERE endpoint LIKE '/api%' AND status_code >= 400 HAVING count(*) >= 10",
        "period": 5, "frequency": 1,
    },
    {
        "name": "cpu_ec2_alta",
        "description": "Uso promedio de CPU mayor a 80% en 5 minutos",
        "stream_type": "metrics", "stream_name": "system_cpu_utilization",
        "sql": "SELECT 100 - AVG(value) * 100 AS cpu FROM \"system_cpu_utilization\" "
               "WHERE state = 'idle' HAVING 100 - AVG(value) * 100 > 80",
        "period": 5, "frequency": 1,
    },
    {
        "name": "ram_ec2_alta",
        "description": "Uso promedio de RAM mayor a 85% en 5 minutos",
        "stream_type": "metrics", "stream_name": "system_memory_utilization",
        "sql": "SELECT AVG(value) * 100 AS ram FROM \"system_memory_utilization\" "
               "WHERE state = 'used' HAVING AVG(value) * 100 > 85",
        "period": 5, "frequency": 1,
    },
]

existing = {a.get("name"): a for a in call("GET", f"/api/v2/{ORG}/alerts").get("list", [])}
for a in ALERTS:
    old = existing.get(a["name"])
    if old:
        aid = old.get("alert_id") or old.get("id")
        call("DELETE", f"/api/v2/{ORG}/alerts/{aid}")
    body = {
        "name": a["name"], "description": a["description"],
        "stream_type": a["stream_type"], "stream_name": a["stream_name"],
        "is_real_time": False,
        "query_condition": {"type": "sql", "sql": a["sql"]},
        "trigger_condition": {"period": a["period"], "operator": ">=", "threshold": 1,
                              "frequency": a["frequency"], "frequency_type": "minutes",
                              "silence": 10},
        "destinations": [DESTINATION], "enabled": True,
        "folder_id": "default",
    }
    res = call("POST", f"/api/v2/{ORG}/alerts?folder=default", body)
    print(f"Alerta creada: {a['name']}  ({res.get('id') or res.get('alert_id') or res})")

print("\nListo. Las alertas disparadas se guardan en Logs -> stream 'alertas_disparadas'.")
