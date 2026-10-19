from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.webhook import (
    IncomingMessageWebhook,
    MessageStatusWebhook,
)
from app.db.models import (
    Message,
    MessageDirection,
    MessageEvent,
    Teacher,
)
from app.services.base import BaseService


class WebhookService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def process_incoming_message(
        self,
        data: IncomingMessageWebhook,
    ):
        result = await self.session.execute(
            select(Teacher).where(
                Teacher.phone == data.sender_phone
            )
        )

        teacher = result.scalar_one_or_none()

        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher with this phone number does not exist",
            )

        message = Message(
            provider=data.provider,
            provider_message_id=data.provider_message_id,
            content=data.content,
            direction=MessageDirection.INBOUND,
            teacher_id=teacher.id,
            campaign_id=None,
        )

        return await self._create(message)
    

    async def process_message_status(
        self,
        data: MessageStatusWebhook,
    ):
        result = await self.session.execute(
            select(Message).where(
                Message.provider == data.provider,
                Message.provider_message_id == data.provider_message_id,
            )
        )

        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message does not exist",
            )

        result = await self.session.execute(
            select(MessageEvent).where(
                MessageEvent.provider_event_id == data.provider_event_id
            )
        )

        existing_event = result.scalar_one_or_none()

        if existing_event:
            return existing_event

        event = MessageEvent(
            status=data.status,
            provider=data.provider,
            provider_event_id=data.provider_event_id,
            event_timestamp=data.event_timestamp,
            raw_payload=data.model_dump(mode="json"),
            message_id=message.id,
        )

        # The timestamp on a new message is its creation time, not a provider
        # status timestamp. The first event establishes the status clock.
        message.status_updated_at = (
            max(data.event_timestamp, message.status_updated_at)
            if message.timeline else data.event_timestamp
        )

        self.session.add(event)
        self.session.add(message)

        await self.session.commit()
        await self.session.refresh(event)

        return event
