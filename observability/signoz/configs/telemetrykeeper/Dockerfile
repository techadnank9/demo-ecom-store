FROM clickhouse/clickhouse-keeper:25.12.5

COPY keeper.d/ /etc/clickhouse-keeper/

RUN cat > /entrypoint.sh <<'EOF'
#!/bin/bash
set -euo pipefail

REPLICA_INDEX=$(echo "${RENDER_SERVICE_NAME:-}" | grep -oE "[0-9]+$" || echo "0")
CONFIG_FILE="/etc/clickhouse-keeper/keeper-${REPLICA_INDEX}.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config $CONFIG_FILE not found, falling back to keeper-0.yaml"
  CONFIG_FILE="/etc/clickhouse-keeper/keeper-0.yaml"
fi

SELF_HOST="${RENDER_DISCOVERY_SERVICE%-discovery}"
if [ -n "${SELF_HOST}" ]; then
  sed -i "s/signoz-telemetrykeeper-clickhousekeeper-0/${SELF_HOST}/g" "$CONFIG_FILE"
  echo "Keeper internal host: ${SELF_HOST}"
fi

echo "Starting ClickHouse Keeper with config: $CONFIG_FILE"
exec /usr/bin/clickhouse-keeper --config-file="$CONFIG_FILE" "$@"
EOF

RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
