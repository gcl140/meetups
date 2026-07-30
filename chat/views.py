from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from events.models import Event


@login_required
def room(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not (event.is_admin(request.user) or event.has_member(request.user)):
        messages.error(request, "You don't have access to that event's chat.")
        return redirect('events:dashboard')
    return render(request, 'chat/room.html', {'event': event})
