"""
saas/worker/callbacks.py
Webhook delivery for event notifications.
"""
import hashlib
import hmac
import json
import logging
import uuid

import requests

from saas.worker.celery_app import app

logger = logging.getLogger("saas.worker.callbacks")


@app.task(bind=True, name="saas.worker.callbacks.deliver_webhook", max_retries=3, default_retry_delay=30)
def deliver_webhook(self, tenant_id: str, event_type: str, payload: dict):
    """Deliver webhook to all registered endpoints for this tenant/event."""
    from saas.worker.tasks import _get_sync_session

    session = _get_sync_session()
    try:
        from saas.models.webhook_endpoint import WebhookEndpoint
        endpoints = (
            session.query(WebhookEndpoint)
            .filter(
                WebhookEndpoint.tenant_id == uuid.UUID(tenant_id),
                WebhookEndpoint.active.is_(True),
            )
            .all()
        )

        for endpoint in endpoints:
            events = endpoint.events if isinstance(endpoint.events, list) else []
            if event_type not in events and "*" not in events:
                continue

            body = json.dumps({
                "event": event_type,
                "data": payload,
                "tenant_id": tenant_id,
            })

            # HMAC-SHA256 signature
            signature = hmac.new(
                endpoint.secret.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            try:
                resp = requests.post(
                    endpoint.url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Signature-256": f"sha256={signature}",
                        "X-Event-Type": event_type,
                    },
                    timeout=10,
                )
                logger.info(
                    f"Webhook delivered to {endpoint.url[:50]} "
                    f"({event_type}) -> {resp.status_code}"
                )
            except Exception as e:
                logger.warning(f"Webhook delivery failed to {endpoint.url[:50]}: {e}")

    except Exception as exc:
        logger.error(f"Webhook delivery error: {exc}")
        raise self.retry(exc=exc)
    finally:
        session.close()
