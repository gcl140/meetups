"""Shared message serialization + realtime broadcast helpers used by both
the async Channels consumer and the plain (sync) DRF views, so an
HTTP-uploaded attachment or a reaction toggle shows up live for everyone
connected to the room without duplicating the payload shape in two places.
"""

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _attachment_ext(name):
    return name.rsplit('.', 1)[-1].lower() if '.' in name else ''


def serialize_reactions(message):
    """{emoji: {count, user_ids}} -- every client (REST or websocket)
    computes its own "did I react with this" by checking whether its own
    user id is in user_ids, so the same payload works for a personalized
    REST response and a broadcast identical to every socket in the room."""
    summary = {}
    for reaction in message.reactions.all():
        entry = summary.setdefault(reaction.emoji, {'count': 0, 'user_ids': []})
        entry['count'] += 1
        entry['user_ids'].append(reaction.user_id)
    return summary


def serialize_message(message):
    attachment_url = None
    is_image = False
    if message.attachment:
        attachment_url = message.attachment.url
        is_image = _attachment_ext(message.attachment_name or message.attachment.name) in IMAGE_EXTENSIONS

    return {
        'id': message.id,
        'sender': None if message.is_bot else (message.sender.display_name if message.sender else 'Deleted user'),
        'sender_id': None if message.is_bot else message.sender_id,
        'is_bot': message.is_bot,
        'content': message.content,
        'attachment_url': attachment_url,
        'attachment_name': message.attachment_name,
        'is_image': is_image,
        'created_at': message.created_at.isoformat(),
        'reactions': serialize_reactions(message),
    }


def broadcast_to_event(event_id, payload_type, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{event_id}', {'type': 'chat.message', 'message': {'type': payload_type, **payload}},
    )
