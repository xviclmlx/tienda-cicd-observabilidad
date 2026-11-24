#!/bin/sh
# Agente de temperatura -> OpenObserve (stream "host_temperature").
# 1) Intenta leer un sensor real: /sys/class/thermal/thermal_zone*/temp o
#    /sys/class/hwmon/hwmon*/temp*_input  -> estimated=false
# 2) Las instancias EC2 virtualizadas normalmente NO exponen sensores térmicos.
#    En ese caso se envía una ESTIMACIÓN a partir de la carga de CPU
#    (35 °C en reposo + hasta 45 °C a carga completa) con estimated=true y
#    source="estimated-from-cpu-load", para poder graficar la tendencia.
apk add --no-cache curl >/dev/null 2>&1

SYS=/host/sys/class
NCPU=$(nproc 2>/dev/null || echo 1)
while true; do
  TEMP=""
  SRC=""
  for f in $SYS/thermal/thermal_zone*/temp $SYS/hwmon/hwmon*/temp*_input; do
    [ -r "$f" ] || continue
    v=$(cat "$f" 2>/dev/null) || continue
    [ -n "$v" ] || continue
    TEMP=$(awk "BEGIN { printf \"%.1f\", $v / 1000 }")
    SRC="$f"
    break
  done

  LOAD=$(cut -d' ' -f1 /proc/loadavg)
  if [ -n "$TEMP" ]; then
    EST=false
  else
    EST=true
    SRC="estimated-from-cpu-load"
    TEMP=$(awk "BEGIN { r = $LOAD / $NCPU; if (r > 1) r = 1; printf \"%.1f\", 35 + r * 45 }")
  fi

  BODY="[{\"host\":\"$HOST_NAME\",\"temp_c\":$TEMP,\"estimated\":$EST,\"source\":\"$SRC\",\"load1\":$LOAD,\"cpus\":$NCPU}]"
  curl -s -o /dev/null -w "temp-agent: %{http_code} $BODY\n" \
    -H "Authorization: Basic $O2_AUTH" -H "Content-Type: application/json" \
    -d "$BODY" "$O2_URL/api/default/host_temperature/_json"
  sleep "${INTERVAL:-30}"
done
