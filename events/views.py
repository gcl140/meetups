from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .calendarsync import (
    build_action_ics, build_call_ics, build_event_ics, describe_event_changes,
    send_event_updated_email, snapshot_event_fields,
)
from .forms import EventForm
from .models import ActionCompletion, CallRsvp, Event, EventAction, EventMembership, PlanningCall


@login_required
def dashboard(request):
    my_memberships = (
        EventMembership.objects.filter(user=request.user)
        .select_related('event')
        .order_by('event__start_datetime')
    )
    now = timezone.now()
    upcoming = [m for m in my_memberships if not m.event.is_past]
    past = [m for m in my_memberships if m.event.is_past]

    open_events = (
        Event.objects.filter(visibility=Event.VISIBILITY_OPEN, start_datetime__gte=now)
        .exclude(membership__user=request.user)
        .order_by('start_datetime')
    )

    return render(request, 'events/dashboard.html', {
        'upcoming_memberships': upcoming,
        'past_memberships': past,
        'open_events': open_events,
        'has_any_events': bool(my_memberships),
    })


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if event.visibility == Event.VISIBILITY_PRIVATE and not event.has_member(request.user) and not event.is_admin(request.user):
        messages.error(request, "You don't have access to that event.")
        return redirect('events:dashboard')

    membership = None
    if request.user.is_authenticated:
        membership = EventMembership.objects.filter(event=event, user=request.user).first()

    planning_calls = list(event.planning_calls.all())
    if planning_calls:
        attending_names = {}
        for rsvp in CallRsvp.objects.filter(call__event=event, will_attend=True).select_related('user'):
            attending_names.setdefault(rsvp.call_id, []).append(str(rsvp.user))

        my_rsvps = {}
        if request.user.is_authenticated:
            my_rsvps = {
                r.call_id: r.will_attend
                for r in CallRsvp.objects.filter(call__event=event, user=request.user)
            }

        for call in planning_calls:
            # None = hasn't responded yet, distinct from an explicit "not attending".
            call.my_will_attend = my_rsvps.get(call.id)
            call.attendee_names = attending_names.get(call.id, [])

    before_actions = list(event.actions.filter(action_type=EventAction.TYPE_BEFORE))
    after_actions = list(event.actions.filter(action_type=EventAction.TYPE_AFTER))
    all_actions = before_actions + after_actions
    if all_actions:
        completed_names = {}
        for completion in ActionCompletion.objects.filter(action__event=event).select_related('user'):
            completed_names.setdefault(completion.action_id, []).append(str(completion.user))

        my_completed_ids = set()
        if request.user.is_authenticated:
            my_completed_ids = set(
                ActionCompletion.objects.filter(action__event=event, user=request.user)
                .values_list('action_id', flat=True)
            )

        for action in all_actions:
            # Independent per attendee -- one member finishing a task
            # doesn't finish it for anyone else going to the event.
            action.my_is_completed = action.id in my_completed_ids
            action.completed_by_names = completed_names.get(action.id, [])

    return render(request, 'events/event_detail.html', {
        'event': event,
        'membership': membership,
        'is_admin': event.is_admin(request.user),
        'before_actions': before_actions,
        'after_actions': after_actions,
        'planning_calls': planning_calls,
    })


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.admin = request.user
            event.save()
            EventMembership.objects.create(
                event=event, user=request.user,
                rsvp_status=EventMembership.STATUS_GOING, responded_at=timezone.now(),
            )
            messages.success(request, f'"{event.title}" was created.')
            return redirect(event.get_absolute_url())
    else:
        form = EventForm()

    return render(request, 'events/event_form.html', {'form': form, 'is_new': True})


def _is_modal_request(request):
    return request.headers.get('X-Requested-With') == 'fetch'


@login_required
def event_edit(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not event.is_admin(request.user):
        if _is_modal_request(request):
            return JsonResponse({'detail': 'Only the event admin can edit this event.'}, status=403)
        messages.error(request, 'Only the event admin can edit this event.')
        return redirect(event.get_absolute_url())

    is_modal = _is_modal_request(request)

    if request.method == 'POST':
        before = snapshot_event_fields(event)
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            changes = describe_event_changes(before, event)
            if changes:
                send_event_updated_email(event, changes, changed_by=request.user)
                messages.success(request, f'Event updated. Notified attendees of {len(changes)} change(s).')
            else:
                messages.success(request, 'Event updated.')
            if is_modal:
                return JsonResponse({'success': True, 'redirect_url': event.get_absolute_url()})
            return redirect(event.get_absolute_url())
        elif is_modal:
            html = render_to_string(
                'events/_event_form_fields.html',
                {'form': form, 'event': event, 'is_new': False, 'is_modal': True},
                request=request,
            )
            return JsonResponse({'success': False, 'html': html})
    else:
        form = EventForm(instance=event)

    if is_modal:
        html = render_to_string(
            'events/_event_form_fields.html',
            {'form': form, 'event': event, 'is_new': False, 'is_modal': True},
            request=request,
        )
        return HttpResponse(html)

    return render(request, 'events/event_form.html', {'form': form, 'event': event, 'is_new': False})


@login_required
def event_delete(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not event.is_admin(request.user):
        messages.error(request, 'Only the event admin can delete this event.')
        return redirect(event.get_absolute_url())
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted.')
        return redirect('events:dashboard')
    return render(request, 'events/event_confirm_delete.html', {'event': event})


def export_event_ics(request, slug):
    event = get_object_or_404(Event, slug=slug)
    ics_bytes = build_event_ics(event)
    response = HttpResponse(ics_bytes, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}.ics"'
    return response


def export_action_ics(request, slug, action_id):
    action = get_object_or_404(EventAction, pk=action_id, event__slug=slug)
    ics_bytes = build_action_ics(action)
    response = HttpResponse(ics_bytes, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{action.event.slug}-action-{action.pk}.ics"'
    return response


def export_call_ics(request, slug, call_id):
    call = get_object_or_404(PlanningCall, pk=call_id, event__slug=slug)
    ics_bytes = build_call_ics(call)
    response = HttpResponse(ics_bytes, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{call.event.slug}-call-{call.pk}.ics"'
    return response
