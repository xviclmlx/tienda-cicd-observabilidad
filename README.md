# Tienda · CI/CD con GitHub Actions → AWS EC2 + Playwright + OpenObserve

Proyecto Parcial 2 — Gestión del Proceso de Desarrollo.

| Pieza | Tecnología |
|---|---|
| Backend | FastAPI + SQLAlchemy + SQLite, JWT (login, CRUD usuarios/categorías/productos, pedidos GET/POST) |
| Frontend | HTML/JS servido con nginx (proxy `/api` → backend) |
| Contenedores | `backend` (python:3.12-**slim**) y `frontend` (nginx:**alpine**) |
| Pruebas | **pytest** (14 pruebas de endpoints) + **Playwright** (9 pruebas: API y UI de extremo a extremo) |
| CI/CD | GitHub Actions: pruebas → registro en OpenObserve → deploy por SSH/rsync a EC2 **solo si todo pasa** |
| Observabilidad | OpenTelemetry (OTLP) → OTel Collector → **OpenObserve** (logs, métricas, trazas, CPU/RAM/red/disco, temperatura) |

```
backend/            API + telemetry.py (OTel) + tests/ (pytest)
frontend/           public/ (index.html, app.js, styles.css) + nginx.conf
e2e/                Playwright (tests/api.spec.js, tests/ui.spec.js)
observability/      otel-collector.yaml, temp-agent.sh
scripts/o2-event.sh Envía eventos del pipeline a OpenObserve (HTTP/JSON)
.github/workflows/ci-cd.yml
docker-compose.yml
```

## 1. Correr en local

```bash
docker compose up -d --build                             # solo app (2 contenedores) en http://localhost
docker compose --profile observability up -d --build     # + OpenObserve en http://localhost:5080
```

Credenciales por defecto (cámbialas en `.env`):
- App: `admin@tienda.com` / `Admin123!`
- OpenObserve: `admin@tienda.com` / `Complexpass#123`
- Docs de la API: `http://localhost/api/docs`

Pruebas:
```bash
cd backend && pip install -r requirements-dev.txt && pytest -v
cd e2e && npm install && npx playwright install chromium && BASE_URL=http://localhost npx playwright test
```

## 2. Preparar la instancia EC2 (una sola vez)

1. Lanzar una instancia **Ubuntu 24.04**, t3.small o mayor (OpenObserve necesita ~1 GB RAM).
2. **Security Group** — reglas de entrada: `22` (SSH), `80` (app), `5080` (OpenObserve; necesario para que GitHub Actions envíe eventos y para ver la interfaz).
3. Conectarse por SSH e instalar Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 rsync
   sudo usermod -aG docker ubuntu && exit   # volver a entrar para aplicar el grupo
   mkdir -p ~/tienda
   ```
4. Crear `~/tienda/.env` copiando `.env.example` y cambiando contraseñas. `O2_AUTH` es `base64("O2_USER:O2_PASSWORD")`:
   ```bash
   echo -n 'admin@tienda.com:TuPassword' | base64
   ```
   (El `.env` no se sube ni se sobrescribe con el deploy.)

## 3. Secrets en GitHub (Settings → Secrets and variables → Actions)

| Secret | Valor |
|---|---|
| `EC2_HOST` | IP pública o DNS de la instancia |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contenido completo del `.pem` |
| `O2_URL` | `http://<IP_EC2>:5080` |
| `O2_USER` / `O2_PASSWORD` | Los mismos que en el `.env` del servidor |

Crear también el environment `production` (Settings → Environments) — el job de deploy lo usa.

## 4. Flujo del pipeline (`.github/workflows/ci-cd.yml`)

```
push a main
 ├─ backend-tests  (pytest)              ┐
 ├─ e2e-tests      (docker compose +     ├─ en paralelo
 │                  Playwright UI + API) ┘
 ├─ report-tests   (siempre) → OpenObserve stream `cicd_events`
 │     event_type=tests  status=success|failure  + commit, rama, actor, conteo de pruebas
 │     si falló → event_type=deploy_blocked
 └─ deploy         (needs ambos jobs de pruebas: si alguno falla, NO se ejecuta ni abre SSH)
       rsync del código → ssh `docker compose --profile observability up -d --build`
       → verifica /health → OpenObserve event_type=deploy
```

## 5. Observabilidad en OpenObserve

| Señal | Dónde verla | Stream |
|---|---|---|
| Eventos del pipeline (RF-03) | Logs | `cicd_events` |
| Logs estructurados de la API y excepciones (RF-04) | Logs | `default` (campos `endpoint`, `method`, `status_code`, `duration_ms`) |
| Trazas de peticiones + consultas SQL (RF-04) | Traces | `default` (spans `GET /api/...` → `SELECT /app/data/app.db`) |
| Métricas por endpoint (RF-04) | Metrics | `http_requests_total`, `http_errors_total`, `http_request_duration_ms` |
| CPU / RAM / red / disco de EC2 (RF-05) | Metrics | `system_cpu_utilization`, `system_memory_utilization`, `system_network_io`, `system_filesystem_utilization` |
| Temperatura (RF-05) | Logs | `host_temperature` |

> **Temperatura:** las instancias EC2 son máquinas virtuales y AWS no expone sensores térmicos al sistema invitado. El agente `temp-agent` revisa primero `/sys/class/thermal` y `/sys/class/hwmon` (valor real, `estimated: false`). Si no encuentra sensor, envía una **estimación** basada en la carga de CPU (35 °C en reposo + hasta 45 °C a carga completa) con `estimated: true` y `source: "estimated-from-cpu-load"`. Esto debe explicarse en el reporte como limitación de la plataforma: la gráfica muestra la tendencia, no una lectura física.

### Dashboard (RF-05 / RF-06 / criterio 3)

El dashboard **"Tienda · CI/CD y Observabilidad"** (15 paneles) se crea automáticamente; el script valida cada consulta antes de crearlo:

```bash
python observability/create_dashboard.py http://<IP_EC2>:5080 admin@tienda.com 'Complexpass#123'
```

Para crearlo a mano: Dashboards → New dashboard → Add panel → modo SQL:

| Panel | Tipo | SQL |
|---|---|---|
| Peticiones por endpoint | barras | `SELECT endpoint, SUM(value) AS total FROM "http_requests_total" GROUP BY endpoint` |
| Latencia promedio por endpoint (ms) | línea | `SELECT histogram(_timestamp) AS t, endpoint, AVG(value) AS ms FROM "http_request_duration_ms_sum" GROUP BY t, endpoint` |
| Errores HTTP por endpoint y código | tabla | `SELECT endpoint, status_code, SUM(value) AS errores FROM "http_errors_total" GROUP BY endpoint, status_code` |
| Peticiones con error (logs) | tabla | `SELECT _timestamp, method, endpoint, status_code, duration_ms FROM "default" WHERE status_code >= 400 ORDER BY _timestamp DESC` |
| CPU % | línea | `SELECT histogram(_timestamp) AS t, AVG(value)*100 AS cpu FROM "system_cpu_utilization" WHERE state != 'idle' GROUP BY t` |
| RAM % | línea | `SELECT histogram(_timestamp) AS t, AVG(value)*100 AS ram FROM "system_memory_utilization" WHERE state = 'used' GROUP BY t` |
| Ancho de banda (bytes) | área | `SELECT histogram(_timestamp) AS t, direction, MAX(value) - MIN(value) AS bytes FROM "system_network_io" GROUP BY t, direction` |
| Temperatura °C (estimada si no hay sensor) | línea | `SELECT histogram(_timestamp) AS t, AVG(temp_c) AS temp FROM "host_temperature" GROUP BY t` |
| Ejecuciones del pipeline | tabla | `SELECT _timestamp, event_type, status, branch, commit_short, actor, detail FROM "cicd_events" ORDER BY _timestamp DESC` |

> Si algún nombre de columna difiere (las etiquetas OTel se aplanan, p. ej. `state`, `direction`), ábrelo primero en *Metrics/Logs → stream* para ver los campos exactos.

### Alertas sugeridas (Alerts → Add alert, tipo programada, cada 1 min)

| Alerta | Stream | Condición |
|---|---|---|
| Pruebas fallidas / deploy bloqueado | `cicd_events` (logs) | `status = 'failure'` → count ≥ 1 |
| Tasa de errores 5xx | `default` (logs) | `status_code >= 500` → count ≥ 5 en 5 min |
| CPU alta | `system_cpu_utilization` | promedio de `value` (state ≠ idle) > 0.8 |
| RAM alta | `system_memory_utilization` | `state = 'used'` promedio > 0.85 |

Destino: Alerts → Destinations → webhook o correo.

## 6. Demostrar los criterios de aceptación

**Criterio 1 — commit con error intencional.** Por ejemplo, en `backend/app/routes.py`, en `create_order`, cambiar
`order.total = round(total, 2)` por `order.total = round(total * 2, 2)`. Hacer commit y push a `main`:
pytest y Playwright fallan → `report-tests` registra `tests/failure` y `deploy_blocked` en OpenObserve → el job **deploy aparece como *skipped*** (nunca abre SSH).

**Criterio 2 — commit válido.** Revertir el cambio y hacer push: todas las pruebas pasan → deploy actualiza los contenedores en EC2 → `cicd_events` muestra `deploy/success` con el commit.

**Criterio 3.** En el dashboard de OpenObserve se ven juntos: tabla de ejecuciones del pipeline, trazas (Traces) de las peticiones HTTP y gráficas de CPU, ancho de banda, temperatura y RAM.
