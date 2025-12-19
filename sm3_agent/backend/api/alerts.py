"""
API endpoints for handling Grafana alert webhooks.

Receives alerts from Grafana, investigates with AI, and creates ServiceNow tickets.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from backend.agents.agent_manager import AgentManager
from backend.app.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])

# Directory for mock ServiceNow tickets (local testing)
TICKETS_DIR = Path("/tmp/servicenow_tickets")
TICKETS_DIR.mkdir(exist_ok=True)


# Grafana Alert Webhook Models
class GrafanaAlertLabel(BaseModel):
    """Alert label from Grafana."""
    alertname: Optional[str] = None
    grafana_folder: Optional[str] = None
    severity: Optional[str] = None


class GrafanaAlertAnnotation(BaseModel):
    """Alert annotation from Grafana."""
    description: Optional[str] = None
    summary: Optional[str] = None
    runbook_url: Optional[str] = None


class GrafanaAlertValue(BaseModel):
    """Alert value/metric data."""
    instance: Optional[str] = None
    metric: Optional[str] = None
    value: Optional[float] = None


class GrafanaAlert(BaseModel):
    """Single alert from Grafana webhook."""
    status: str  # firing, resolved
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    startsAt: str
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: str
    values: Optional[Dict[str, float]] = None


class GrafanaWebhookPayload(BaseModel):
    """Grafana webhook payload structure."""
    receiver: str
    status: str  # firing, resolved
    alerts: List[GrafanaAlert]
    groupLabels: Dict[str, Any]
    commonLabels: Dict[str, Any]
    commonAnnotations: Dict[str, Any]
    externalURL: str
    version: str = "4"
    groupKey: str
    truncatedAlerts: int = 0


class AlertInvestigation(BaseModel):
    """AI-generated investigation result."""
    alert_name: str
    severity: str
    summary: str
    root_cause_hypothesis: str
    impact_assessment: str
    recommended_actions: List[str]
    related_evidence: List[str]
    confidence: float  # 0-1
    investigated_at: datetime


class ServiceNowTicket(BaseModel):
    """Mock ServiceNow ticket for local testing."""
    ticket_number: str
    priority: str  # P1, P2, P3
    short_description: str
    description: str
    assignment_group: str = "platform-ops"
    category: str = "Infrastructure"
    state: str = "New"
    created_at: datetime
    ai_generated: bool = True
    investigation_summary: str


# Severity mapping
SEVERITY_MAPPING = {
    "critical": {"priority": "P1", "snow_priority": "1", "action": "page"},
    "high": {"priority": "P2", "snow_priority": "2", "action": "ticket"},
    "warning": {"priority": "P3", "snow_priority": "3", "action": "ticket"},
    "info": {"priority": "P4", "snow_priority": "4", "action": "email_only"}
}


@router.post("/webhook")
async def grafana_webhook(
    payload: GrafanaWebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Receive alert webhook from Grafana.

    Grafana sends alerts here when they fire or resolve.
    For major/critical alerts, triggers AI investigation and creates ServiceNow ticket.
    """
    logger.info(f"Received Grafana webhook: {payload.status}, {len(payload.alerts)} alert(s)")

    # Only process firing alerts (ignore resolved for now)
    if payload.status != "firing":
        logger.info(f"Ignoring {payload.status} alert")
        return {"status": "ignored", "reason": f"Alert status is {payload.status}"}

    # Process each alert
    processed = []
    for alert in payload.alerts:
        # Extract severity
        severity = alert.labels.get("severity", "info").lower()

        # Only process major/critical alerts
        if severity not in ["critical", "high"]:
            logger.info(f"Skipping {severity} alert - only processing major/critical")
            continue

        # Process in background to not block webhook response
        background_tasks.add_task(
            process_alert,
            alert=alert,
            common_labels=payload.commonLabels,
            common_annotations=payload.commonAnnotations
        )

        processed.append({
            "fingerprint": alert.fingerprint,
            "severity": severity,
            "status": "queued_for_investigation"
        })

    return {
        "status": "received",
        "processed_count": len(processed),
        "alerts": processed
    }


async def process_alert(
    alert: GrafanaAlert,
    common_labels: Dict[str, Any],
    common_annotations: Dict[str, Any]
):
    """
    Process a single alert: investigate with AI and create ServiceNow ticket.

    Runs in background task.
    """
    try:
        logger.info(f"Processing alert: {alert.fingerprint}")

        # Extract alert details
        alert_name = alert.labels.get("alertname", "Unknown Alert")
        severity = alert.labels.get("severity", "unknown").lower()

        # Get alert description and summary
        description = alert.annotations.get("description", "No description")
        summary = alert.annotations.get("summary", alert_name)

        # Extract metric values
        metric_values = alert.values or {}

        # Run AI investigation
        investigation = await investigate_alert_with_ai(
            alert_name=alert_name,
            severity=severity,
            description=description,
            summary=summary,
            metric_values=metric_values,
            labels=alert.labels,
            annotations=alert.annotations
        )

        # Create ServiceNow ticket (mock for now)
        ticket = await create_servicenow_ticket(
            alert=alert,
            investigation=investigation,
            severity=severity
        )

        logger.info(f"Created ticket {ticket.ticket_number} for alert {alert_name}")

    except Exception as e:
        logger.error(f"Error processing alert {alert.fingerprint}: {e}", exc_info=True)


async def investigate_alert_with_ai(
    alert_name: str,
    severity: str,
    description: str,
    summary: str,
    metric_values: Dict[str, float],
    labels: Dict[str, Any],
    annotations: Dict[str, Any]
) -> AlertInvestigation:
    """
    Use AI agent to investigate the alert and gather context.
    """
    logger.info(f"Starting AI investigation for: {alert_name}")

    # Build investigation prompt
    metrics_str = "\n".join([f"  - {k}: {v}" for k, v in metric_values.items()])
    labels_str = "\n".join([f"  - {k}: {v}" for k, v in labels.items()])

    investigation_prompt = f"""
An alert has fired in production and requires investigation:

**Alert Details:**
- Name: {alert_name}
- Severity: {severity.upper()}
- Summary: {summary}
- Description: {description}

**Current Metric Values:**
{metrics_str or "  No metric values provided"}

**Labels:**
{labels_str}

**Your Task:**
Please investigate this alert by:

1. **Check Recent Trends**: Query relevant Prometheus metrics for the last hour to see if this is a spike or ongoing issue
2. **Gather Context**: Check related metrics (CPU, memory, network, error rates) for the affected service/instance
3. **Review Logs**: Query Loki for error logs around the alert time
4. **Check Dashboards**: Look for relevant dashboards that show the service health
5. **Correlate**: Are other instances/services affected?

**Provide in your response:**
- **Root Cause Hypothesis**: What likely caused this alert? (2-3 sentences)
- **Impact Assessment**: What's affected and how severe? (2-3 sentences)
- **Recommended Actions**: List 3-4 specific steps to resolve (bullet points)
- **Evidence**: Cite specific metrics, log entries, or dashboard data you found

Focus on actionable insights for the on-call engineer.
"""

    try:
        # Get agent manager
        settings = get_settings()
        agent_manager = AgentManager(settings)
        await agent_manager.initialize()

        # Run investigation
        session_id = f"alert-investigation-{datetime.utcnow().timestamp()}"
        result = await agent_manager.run_chat(
            message=investigation_prompt,
            session_id=session_id
        )

        # Parse the AI response
        ai_response = result.message

        # Log the full AI response for debugging
        logger.info(f"AI Investigation Response:\n{ai_response}\n{'='*80}")

        # Extract structured data from response
        # (In production, you'd use more sophisticated parsing or structured output)
        investigation = AlertInvestigation(
            alert_name=alert_name,
            severity=severity,
            summary=summary,
            root_cause_hypothesis=extract_section(ai_response, "Root Cause"),
            impact_assessment=extract_section(ai_response, "Impact"),
            recommended_actions=extract_actions(ai_response),
            related_evidence=extract_evidence(ai_response),
            confidence=calculate_confidence(result),
            investigated_at=datetime.utcnow()
        )

        logger.info(f"Investigation completed for {alert_name}")
        return investigation

    except Exception as e:
        logger.error(f"Error during AI investigation: {e}", exc_info=True)

        # Fallback investigation if AI fails
        return AlertInvestigation(
            alert_name=alert_name,
            severity=severity,
            summary=summary,
            root_cause_hypothesis="AI investigation failed - manual investigation required",
            impact_assessment=f"Alert triggered: {description}",
            recommended_actions=["Check Grafana dashboard", "Review recent deployments", "Check service logs"],
            related_evidence=["AI investigation unavailable"],
            confidence=0.0,
            investigated_at=datetime.utcnow()
        )


async def create_servicenow_ticket(
    alert: GrafanaAlert,
    investigation: AlertInvestigation,
    severity: str
) -> ServiceNowTicket:
    """
    Create ServiceNow ticket (mock version - writes to file).

    In production, this would call ServiceNow REST API.
    """
    # Get priority mapping
    severity_config = SEVERITY_MAPPING.get(severity, SEVERITY_MAPPING["info"])
    priority = severity_config["priority"]

    # Generate ticket number (mock)
    ticket_number = f"INC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Format description
    description = format_ticket_description(investigation)

    # Create ticket object
    ticket = ServiceNowTicket(
        ticket_number=ticket_number,
        priority=priority,
        short_description=f"[{severity.upper()}] {investigation.alert_name}",
        description=description,
        created_at=datetime.utcnow(),
        investigation_summary=investigation.root_cause_hypothesis
    )

    # Write to file (mock ServiceNow)
    ticket_file = TICKETS_DIR / f"{ticket_number}.json"
    ticket_file.write_text(
        json.dumps(ticket.dict(), indent=2, default=str),
        encoding="utf-8"
    )

    # Also write human-readable version
    ticket_txt = TICKETS_DIR / f"{ticket_number}.txt"
    ticket_txt.write_text(format_ticket_text(ticket), encoding="utf-8")

    logger.info(f"Mock ServiceNow ticket written to {ticket_file}")

    return ticket


def format_ticket_description(investigation: AlertInvestigation) -> str:
    """Format investigation into ServiceNow ticket description."""
    actions = "\n".join([f"  {i+1}. {action}" for i, action in enumerate(investigation.recommended_actions)])
    evidence = "\n".join([f"  - {item}" for item in investigation.related_evidence])

    return f"""
=== ALERT DETAILS ===
Alert: {investigation.alert_name}
Severity: {investigation.severity.upper()}
Summary: {investigation.summary}
Investigated: {investigation.investigated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
Confidence: {investigation.confidence:.0%}

=== ROOT CAUSE HYPOTHESIS ===
{investigation.root_cause_hypothesis}

=== IMPACT ASSESSMENT ===
{investigation.impact_assessment}

=== RECOMMENDED ACTIONS ===
{actions}

=== SUPPORTING EVIDENCE ===
{evidence}

---
This ticket was generated automatically by the Grafana AI Agent.
""".strip()


def format_ticket_text(ticket: ServiceNowTicket) -> str:
    """Format ticket as human-readable text file."""
    return f"""
╔══════════════════════════════════════════════════════════════╗
║                    SERVICENOW TICKET (MOCK)                   ║
╚══════════════════════════════════════════════════════════════╝

Ticket Number:    {ticket.ticket_number}
Priority:         {ticket.priority}
State:            {ticket.state}
Created:          {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
Assignment Group: {ticket.assignment_group}
Category:         {ticket.category}

─────────────────────────────────────────────────────────────────

SHORT DESCRIPTION:
{ticket.short_description}

─────────────────────────────────────────────────────────────────

DESCRIPTION:

{ticket.description}

─────────────────────────────────────────────────────────────────

** This is a MOCK ticket for local testing **
** In production, this would be created in ServiceNow via REST API **

""".strip()


# Helper functions for parsing AI response
def extract_section(text: str, section_name: str) -> str:
    """Extract a section from AI response."""
    # Simple extraction - in production use more robust parsing
    lines = text.split('\n')
    in_section = False
    section_lines = []

    for line in lines:
        if section_name.lower() in line.lower() and (':**' in line or '###' in line or '**' in line):
            in_section = True
            continue
        elif in_section and (line.startswith('**') or line.startswith('###') or not line.strip()):
            if section_lines:  # We've collected some lines
                break
        elif in_section:
            section_lines.append(line.strip())

    return ' '.join(section_lines) if section_lines else f"See full investigation for {section_name}"


def extract_actions(text: str) -> List[str]:
    """Extract recommended actions from AI response."""
    lines = text.split('\n')
    actions = []
    in_actions = False

    for line in lines:
        if 'recommended' in line.lower() and 'action' in line.lower():
            in_actions = True
            continue
        elif in_actions:
            # Look for bullet points or numbered lists
            stripped = line.strip()
            if stripped and (stripped.startswith('-') or stripped.startswith('*') or stripped[0].isdigit()):
                # Remove bullet/number
                action = stripped.lstrip('-*0123456789. ')
                if action:
                    actions.append(action)
            elif stripped and not stripped.startswith('**'):
                # Plain text action
                actions.append(stripped)
            elif stripped.startswith('**') or stripped.startswith('###'):
                # New section started
                break

    return actions[:5] if actions else ["Review alert in Grafana", "Check service logs", "Escalate if needed"]


def extract_evidence(text: str) -> List[str]:
    """Extract evidence from AI response."""
    # Look for metric values, log entries, dashboard references
    evidence = []
    lines = text.split('\n')

    for line in lines:
        if any(keyword in line.lower() for keyword in ['metric', 'log', 'dashboard', 'query', 'value', 'error']):
            if ':' in line and not line.startswith('#'):
                evidence.append(line.strip())

    return evidence[:10] if evidence else ["See investigation details above"]


def calculate_confidence(result) -> float:
    """Calculate confidence score based on investigation quality."""
    # Simple heuristic - in production, use more sophisticated scoring
    tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
    message_length = len(result.message) if hasattr(result, 'message') else 0

    # More tool calls and longer analysis = higher confidence
    confidence = min(1.0, (tool_calls * 0.15) + min(0.4, message_length / 2000))
    return round(confidence, 2)


# Management endpoints
@router.get("/tickets")
async def list_tickets(limit: int = 50):
    """
    List mock ServiceNow tickets created locally.

    Useful for reviewing what would have been sent to ServiceNow.
    """
    tickets = []

    for ticket_file in sorted(TICKETS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            ticket_data = json.loads(ticket_file.read_text())
            tickets.append(ticket_data)
        except Exception as e:
            logger.error(f"Error reading ticket {ticket_file}: {e}")

    return {
        "count": len(tickets),
        "tickets": tickets
    }


@router.get("/tickets/{ticket_number}")
async def get_ticket(ticket_number: str):
    """Get a specific mock ServiceNow ticket."""
    ticket_file = TICKETS_DIR / f"{ticket_number}.json"

    if not ticket_file.exists():
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found")

    ticket_data = json.loads(ticket_file.read_text())
    return ticket_data


@router.delete("/tickets")
async def clear_tickets():
    """Clear all mock ServiceNow tickets (for testing)."""
    count = 0
    for ticket_file in TICKETS_DIR.glob("*"):
        ticket_file.unlink()
        count += 1

    return {"status": "cleared", "deleted": count}
