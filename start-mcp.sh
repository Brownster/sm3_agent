#!/bin/bash
cd /home/marc/Documents/github/grafana-web-agent
export GRAFANA_URL=http://localhost:3000
export GRAFANA_SERVICE_ACCOUNT_TOKEN=${GRAFANA_SERVICE_ACCOUNT_TOKEN:-your-grafana-service-account-token}
./mcp-grafana/mcp-grafana -t streamable-http -address localhost:8888
