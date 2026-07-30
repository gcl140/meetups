from django.conf import settings
from django.db import models

REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🙏']


class ChatMessage(models.Model):
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='+',
    )
    is_bot = models.BooleanField(default=False)
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to='chat_attachments/%Y/%m/', blank=True, null=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        who = 'bot' if self.is_bot else (self.sender or 'unknown')
        return f'{who}: {self.content[:40]}'


class MessageReaction(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f'{self.user} reacted {self.emoji} to message {self.message_id}'
