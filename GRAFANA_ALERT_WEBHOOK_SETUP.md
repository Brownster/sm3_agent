# Grafana Alert Webhook Setup Guide

This guide explains how to configure Grafana to send alert notifications to the AI investigation webhook.

## Overview

The Grafana AI Agent can automatically investigate alerts when they fire by:
1. Receiving alert webhooks from Grafana
2. Using AI to query Prometheus, Loki, and dashboards for context
3. Generating root cause hypotheses and recommended actions
4. Creating mock ServiceNow tickets (writes to `/tmp/servicenow_tickets/`)

## Prerequisites

- Grafana MCP Chat API running on port 8000
- Grafana instance with alerting configured
- LGTM stack (Loki, Grafana, Tempo, Mimir/Prometheus) running for data queries
- MCP server running on port 8888

## Alert Severity Filtering

The webhook only processes **major/critical** alerts:

| Severity  | Priority | Action | Processed? |
|-----------|----------|--------|------------|
| critical  | P1       | Page   | ✅ Yes     |
| high      | P2       | Ticket | ✅ Yes     |
| warning   | P3       | Ticket | ❌ No      |
| info      | P4       | Email  | ❌ No      |

## Configuring Grafana Alert Webhook

### 1. Create Contact Point

In Grafana UI:

1. Go to **Alerting → Contact points**
2. Click **+ Add contact point**
3. Configure:
   ```
   Name: grafana-ai-agent
   Integration: Webhook
   URL: http://localhost:8000/api/alerts/webhook
   HTTP Method: POST
   ```

### 2. Configure Alert Rule Labels

For alerts you want investigated, add these labels:

```yaml
labels:
  severity: critical  # or 'high' for P2
  service: your-service-name
  environment: production
```

### 3. Set Notification Policy

1. Go to **Alerting → Notification policies**
2. Create or edit a policy
3. Set **Contact point** to `grafana-ai-agent`
4. Add label matchers:
   ```
   severity = critical
   ```
   or
   ```
   severity = high
   ```

## Alert Payload Format

Grafana sends alerts in this format:

```json
{
  "receiver": "grafana-ai-agent",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighErrorRate",
        "severity": "critical",
        "service": "api-gateway",
        "environment": "production",
        "instance": "api-gw-01"
      },
      "annotations": {
        "summary": "API Gateway error rate above threshold",
        "description": "The API Gateway is experiencing an error rate of 15%...",
        "runbook_url": "https://wiki.example.com/runbooks/high-error-rate"
      },
      "startsAt": "2025-12-19T21:40:00Z",
      "values": {
        "B": 15.2,
        "C": 5.0
      }
    }
  ]
}
```

## AI Investigation Process

When an alert fires, the AI agent:

1. **Checks Recent Trends**: Queries Prometheus metrics for the last hour
2. **Gathers Context**: Checks related metrics (CPU, memory, network, error rates)
3. **Reviews Logs**: Queries Loki for error logs around the alert time
4. **Checks Dashboards**: Looks for relevant dashboards showing service health
5. **Correlates**: Checks if other instances/services are affected

The investigation prompt asks the AI to provide:

- **Root Cause Hypothesis**: What likely caused this alert?
- **Impact Assessment**: What's affected and how severe?
- **Recommended Actions**: 3-4 specific steps to resolve
- **Evidence**: Specific metrics, log entries, or dashboard data found

## ServiceNow Ticket Output

Mock tickets are written to `/tmp/servicenow_tickets/` with:

- **JSON format**: `INC<timestamp>.json` - structured data for API integration
- **Text format**: `INC<timestamp>.txt` - human-readable ticket

### Example Ticket

```
╔══════════════════════════════════════════════════════════════╗
║                    SERVICENOW TICKET (MOCK)                   ║
╚══════════════════════════════════════════════════════════════╝

Ticket Number:    INC20251219215152
Priority:         P1
State:            New
Created:          2025-12-19 21:51:52 UTC
Assignment Group: platform-ops
Category:         Infrastructure

─────────────────────────────────────────────────────────────────

SHORT DESCRIPTION:
[CRITICAL] HighErrorRate

─────────────────────────────────────────────────────────────────

DESCRIPTION:

=== ALERT DETAILS ===
Alert: HighErrorRate
Severity: CRITICAL
Summary: API Gateway error rate above threshold
Investigated: 2025-12-19 21:51:52 UTC
Confidence: 95%

=== ROOT CAUSE HYPOTHESIS ===
[AI-generated analysis of root cause]

=== IMPACT ASSESSMENT ===
[AI-generated impact assessment]

=== RECOMMENDED ACTIONS ===
  1. [Action 1]
  2. [Action 2]
  3. [Action 3]

=== SUPPORTING EVIDENCE ===
  - [Metric or log evidence]
  - [Dashboard reference]
```

## Testing the Webhook

### Test with curl

```bash
curl -X POST http://localhost:8000/api/alerts/webhook \
  -H "Content-Type: application/json" \
  -d @test_alert.json
```

### Test Alert JSON

Create `test_alert.json`:

```json
{
  "receiver": "grafana-ai-agent",
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "TestAlert",
      "severity": "critical",
      "service": "test-service"
    },
    "annotations": {
      "summary": "Test alert for webhook",
      "description": "This is a test alert"
    },
    "startsAt": "2025-12-19T21:40:00Z",
    "fingerprint": "test123"
  }],
  "groupLabels": {"alertname": "TestAlert"},
  "commonLabels": {"alertname": "TestAlert", "severity": "critical"},
  "commonAnnotations": {"summary": "Test alert for webhook"},
  "externalURL": "http://localhost:3000",
  "version": "4",
  "groupKey": "{}:{alertname=\"TestAlert\"}",
  "truncatedAlerts": 0
}
```

### Expected Response

```json
{
  "status": "received",
  "processed_count": 1,
  "alerts": [{
    "fingerprint": "test123",
    "severity": "critical",
    "status": "queued_for_investigation"
  }]
}
```

## Viewing Investigation Results

### List all tickets
```bash
curl http://localhost:8000/api/alerts/tickets
```

### Get specific ticket
```bash
curl http://localhost:8000/api/alerts/tickets/INC20251219215152
```

### View ticket file
```bash
cat /tmp/servicenow_tickets/INC20251219215152.txt
```

### Clear test tickets
```bash
curl -X DELETE http://localhost:8000/api/alerts/tickets
```

## Production ServiceNow Integration

To integrate with real ServiceNow:

1. **Update `backend/api/alerts.py`** in `create_servicenow_ticket()`:
   ```python
   # Replace file writing with ServiceNow REST API call
   response = requests.post(
       f"{SNOW_URL}/api/now/table/incident",
       auth=(SNOW_USER, SNOW_PASSWORD),
       headers={"Content-Type": "application/json"},
       json={
           "short_description": ticket.short_description,
           "description": ticket.description,
           "priority": severity_config["snow_priority"],
           "assignment_group": ticket.assignment_group,
           "category": ticket.category
       }
   )
   ```

2. **Add ServiceNow credentials** to `.env`:
   ```
   SERVICENOW_URL=https://your-instance.service-now.com
   SERVICENOW_USER=api_user
   SERVICENOW_PASSWORD=api_password
   ```

3. **Test in staging** before enabling in production

## Troubleshooting

### Webhook not receiving alerts

1. Check Grafana contact point configuration
2. Verify backend is running: `curl http://localhost:8000/health`
3. Check Grafana notification history for errors

### AI investigation fails

1. Ensure LGTM stack is running:
   ```bash
   curl http://localhost:9090  # Prometheus
   curl http://localhost:3100  # Loki
   ```

2. Check MCP server is running:
   ```bash
   curl http://localhost:8888/health
   ```

3. Verify datasource UIDs in Grafana match `prometheus` and `loki`

### Investigation produces generic results

- The AI needs real metrics and logs to generate specific recommendations
- Ensure the service/instance labels in the alert match Prometheus labels
- Check that Loki has logs for the affected service

### Tickets not being created

1. Check write permissions: `ls -la /tmp/servicenow_tickets/`
2. View backend logs: `tail -f /tmp/backend-alerts.log`
3. Look for investigation errors in logs

## Configuration Options

Edit `backend/api/alerts.py` to customize:

- **Severity mapping** (line 104): Change P1/P2/P3 assignments
- **Investigation prompt** (line 228): Modify what the AI investigates
- **Ticket format** (line 357): Customize ticket description layout
- **Assignment group** (line 95): Change default assignment group
- **Ticket directory** (line 24): Change where mock tickets are written

## Monitoring

The webhook provides these metrics at `/metrics`:

- `alert_webhooks_total`: Count of alerts received
- `alert_investigations_total`: Count of investigations completed
- `alert_investigation_duration_seconds`: Time to investigate
- `tickets_created_total`: Count of tickets created

## Next Steps

1. ✅ Configure Grafana contact point
2. ✅ Add severity labels to alert rules
3. ✅ Test with sample alert
4. ✅ Verify ticket creation
5. ✅ Review AI investigation quality
6. ⬜ Start LGTM stack for full testing
7. ⬜ Integrate with production ServiceNow API
