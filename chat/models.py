from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='+',
    )
    is_bot = models.BooleanField(default=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        who = 'bot' if self.is_bot else (self.sender or 'unknown')
        return f'{who}: {self.content[:40]}'
