from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event
from events.permissions import require_member

from .models import ChatMessage, MessageReaction
from .utils import broadcast_to_event, serialize_message

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_ATTACHMENT_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'pdf', 'doc', 'docx', 'txt', 'csv', 'xlsx', 'pptx',
}


class ChatPagination(PageNumberPagination):
    page_size = 25


class ChatMessageListAPI(APIView):
    """Newest-first, paginated. Page 1 = latest messages; higher page
    numbers = older history. Used for both the initial room load and
    "load older messages", so nothing ever needs a big websocket dump."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        require_member(event, request.user)

        queryset = ChatMessage.objects.filter(event=event).select_related('sender').prefetch_related('reactions').order_by('-created_at')
        paginator = ChatPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response([serialize_message(m) for m in page])


class ChatAttachmentUploadAPI(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        require_member(event, request.user)

        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'No file provided.'}, status=400)
        if file.size > MAX_ATTACHMENT_SIZE:
            return Response({'detail': 'File is too large (10MB max).'}, status=400)
        ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            return Response({'detail': f'Unsupported file type: .{ext}'}, status=400)

        message = ChatMessage.objects.create(
            event=event, sender=request.user, is_bot=False,
            content=(request.data.get('caption') or '').strip(),
            attachment=file, attachment_name=file.name,
        )
        payload = serialize_message(message)
        broadcast_to_event(event.id, 'message', payload)
        return Response(payload, status=201)


class MessageReactionToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, message_id):
        event = get_object_or_404(Event, slug=slug)
        require_member(event, request.user)
        message = get_object_or_404(ChatMessage, pk=message_id, event=event)

        emoji = (request.data.get('emoji') or '').strip()
        if not emoji:
            return Response({'detail': 'emoji is required.'}, status=400)

        existing = MessageReaction.objects.filter(message=message, user=request.user, emoji=emoji).first()
        if existing:
            existing.delete()
        else:
            MessageReaction.objects.create(message=message, user=request.user, emoji=emoji)

        message.refresh_from_db()
        reactions = serialize_message(message)['reactions']
        broadcast_to_event(event.id, 'reaction_update', {'id': message.id, 'reactions': reactions})
        return Response({'id': message.id, 'reactions': reactions})
