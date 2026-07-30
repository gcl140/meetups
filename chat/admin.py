from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['event', 'sender', 'is_bot', 'created_at']
    list_filter = ['is_bot']
