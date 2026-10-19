import asyncio
from datetime import datetime

from sqlalchemy import select

from app.config import webhook_settings
from app.db.models import Message, MessageEvent, MessageStatus


def payload(event_id="event_001", status="read", timestamp="2026-09-29T19:05:00"):
    return {
        "provider": "fake_provider",
        "provider_event_id": event_id,
        "provider_message_id": "test_message_001",
        "status": status,
        "event_timestamp": timestamp,
    }


def events_for(sessions, message_id):
    async def read():
        async with sessions() as session:
            return (await session.scalars(
                select(MessageEvent).where(MessageEvent.message_id == message_id)
            )).all()
    return asyncio.run(read())


def test_webhook_secret(outbound_message):
    client, sessions, message_id = outbound_message
    assert client.post("/webhook/status", json=payload()).status_code == 422
    assert client.post("/webhook/status", json=payload(), headers={
        "X-Webhook-Secret": "incorrect"
    }).status_code == 401
    assert client.post("/webhook/status", json=payload(), headers={
        "X-Webhook-Secret": webhook_settings.WEBHOOK_SECRET
    }).status_code == 200
    assert len(events_for(sessions, message_id)) == 1


def test_duplicate_status_event(outbound_message):
    client, sessions, message_id = outbound_message
    headers = {"X-Webhook-Secret": webhook_settings.WEBHOOK_SECRET}
    first = client.post("/webhook/status", json=payload(), headers=headers)
    second = client.post("/webhook/status", json=payload(), headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    events = events_for(sessions, message_id)
    assert len(events) == 1
    assert events[0].provider_event_id == "event_001"


def test_out_of_order_status_events(outbound_message):
    client, sessions, message_id = outbound_message
    headers = {"X-Webhook-Secret": webhook_settings.WEBHOOK_SECRET}
    read = client.post("/webhook/status", json=payload(), headers=headers)
    delivered = client.post("/webhook/status", json=payload(
        "event_002", "delivered", "2026-09-29T19:02:00"
    ), headers=headers)
    assert read.status_code == delivered.status_code == 200

    async def state():
        async with sessions() as session:
            return await session.get(Message, message_id)

    message = asyncio.run(state())
    assert [(e.status, e.event_timestamp) for e in message.timeline] == [
        (MessageStatus.DELIVERED, datetime(2026, 9, 29, 19, 2)),
        (MessageStatus.READ, datetime(2026, 9, 29, 19, 5)),
    ]
    assert message.current_status == MessageStatus.READ
    assert message.status_updated_at == datetime(2026, 9, 29, 19, 5)
