from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import bot
from .models import ChatMessage


def _serialize(message):
    return {
        'id': message.id,
        'sender': None if message.is_bot else (str(message.sender) if message.sender else 'Deleted user'),
        'is_bot': message.is_bot,
        'content': message.content,
        'created_at': message.created_at.isoformat(),
    }


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope['url_route']['kwargs']['slug']
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.event = await self.get_event()
        if self.event is None or not await self.can_access(self.event):
            await self.close()
            return

        self.group_name = f'chat_{self.event.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self.get_history()
        await self.send_json({'type': 'history', 'messages': history})

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = (content.get('message') or '').strip()
        if not text:
            return

        user_message = await self.save_message(self.user, text, is_bot=False)
        await self.broadcast(user_message)

        if text.startswith('/'):
            reply_text = await self.run_bot_command(text)
            bot_message = await self.save_message(None, reply_text, is_bot=True)
            await self.broadcast(bot_message)

    async def broadcast(self, message):
        await self.channel_layer.group_send(
            self.group_name, {'type': 'chat.message', 'message': {'type': 'message', **_serialize(message)}},
        )

    async def chat_message(self, event):
        await self.send_json(event['message'])

    @database_sync_to_async
    def get_event(self):
        from events.models import Event
        return Event.objects.filter(slug=self.slug).first()

    @database_sync_to_async
    def can_access(self, event):
        return event.is_admin(self.user) or event.has_member(self.user)

    @database_sync_to_async
    def save_message(self, user, content, is_bot):
        return ChatMessage.objects.create(event=self.event, sender=user, content=content, is_bot=is_bot)

    @database_sync_to_async
    def run_bot_command(self, text):
        return bot.handle_command(text, self.event)

    @database_sync_to_async
    def get_history(self):
        messages = ChatMessage.objects.filter(event=self.event).select_related('sender').order_by('-created_at')[:50]
        return [_serialize(m) for m in reversed(messages)]
