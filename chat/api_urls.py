from django.urls import path

from . import api

urlpatterns = [
    path('events/<slug:slug>/chat/messages/', api.ChatMessageListAPI.as_view(), name='api-chat-messages'),
    path('events/<slug:slug>/chat/attachments/', api.ChatAttachmentUploadAPI.as_view(), name='api-chat-attachment'),
    path(
        'events/<slug:slug>/chat/messages/<int:message_id>/react/',
        api.MessageReactionToggleAPI.as_view(), name='api-chat-react',
    ),
]
