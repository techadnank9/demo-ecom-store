FROM signoz/signoz-otel-collector:v0.144.8

USER root

COPY ingester.yaml /etc/otel/config.yaml
COPY opamp.yaml /etc/otel/manager-config.yaml

RUN cat > /foundry-entrypoint.sh <<'EOF'
#!/bin/sh
set -eu

CLICKHOUSE_INTERNAL_HOST="${CLICKHOUSE_HOST:-${DEPENDENCY_LINK_0:-signoz-telemetrystore-clickhouse-0-0}}"
sed -i "s/signoz-telemetrystore-clickhouse-0-0/${CLICKHOUSE_INTERNAL_HOST}/g" /etc/otel/config.yaml

if [ -n "${SIGNOZ_OPAMP_ENDPOINT:-}" ]; then
  OPAMP_ENDPOINT="${SIGNOZ_OPAMP_ENDPOINT}"
elif [ -n "${SIGNOZ_HOST:-}" ]; then
  OPAMP_ENDPOINT="ws://${SIGNOZ_HOST}:4320/v1/opamp"
else
  OPAMP_ENDPOINT="ws://signoz-signoz-0:4320/v1/opamp"
fi
sed -i "s|^server_endpoint:.*|server_endpoint: ${OPAMP_ENDPOINT}|" /etc/otel/manager-config.yaml

SELF_HOST="${RENDER_DISCOVERY_SERVICE%-discovery}"
echo "SigNoz ingester internal host: ${SELF_HOST}"
exec /signoz-otel-collector "$@"
EOF

RUN chmod +x /foundry-entrypoint.sh
ENTRYPOINT ["/foundry-entrypoint.sh"]
