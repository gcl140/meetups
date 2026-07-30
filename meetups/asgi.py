"""
ASGI config for meetups project.

Routes plain HTTP to Django as usual, and WebSocket connections to the
Channels routing defined in chat.routing, wrapped in session/auth
middleware so consumers can see request.user.
"""

import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meetups.settings')
django.setup()

django_asgi_app = get_asgi_application()

import chat.routing  # noqa: E402  (must import after django.setup())

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})
