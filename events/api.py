from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import permissions as perms
from .calendarsync import (
    send_call_rsvp_notification, send_invite_email, send_new_action_email, send_new_call_email,
    send_removed_email,
)
from .models import (
    ActionCompletion, Attendance, CallRsvp, Event, EventAction, EventMembership, EventPhoto,
    Invitation, PlanningCall,
)
from .serializers import (
    AttendanceSerializer, CallRsvpSerializer, EventActionSerializer, EventListSerializer,
    EventMembershipSerializer, EventPhotoSerializer, PlanningCallSerializer,
)


def _member_payload(event):
    memberships = (
        EventMembership.objects.filter(event=event).select_related('user').order_by('joined_at')
    )
    return [
        {
            'id': m.user.id,
            'name': str(m.user),
            'email': m.user.email,
            'rsvp_status': m.rsvp_status,
            'is_admin': event.is_admin(m.user),
        }
        for m in memberships
    ]


class EventListAPI(generics.ListAPIView):
    serializer_class = EventListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        scope = self.request.query_params.get('scope', 'mine')
        qs = Event.objects.select_related('admin')
        if scope == 'open':
            return qs.filter(visibility=Event.VISIBILITY_OPEN).exclude(
                membership__user=self.request.user,
            ).order_by('start_datetime')
        return qs.filter(membership__user=self.request.user).order_by('start_datetime')


class EventMembersAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        perms.require_member_or_open(event, request.user)
        return Response(_member_payload(event))


class RsvpAPI(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        status_value = request.data.get('rsvp_status')
        valid = dict(EventMembership.STATUS_CHOICES)
        if status_value not in valid:
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = EventMembership.objects.filter(event=event, user=request.user).first()
        if membership is None:
            if not event.is_open:
                return Response({'detail': 'You are not invited to this event.'}, status=status.HTTP_403_FORBIDDEN)
            if status_value == EventMembership.STATUS_GOING and event.is_full:
                return Response({'detail': 'This event is full.'}, status=status.HTTP_409_CONFLICT)
            membership = EventMembership(event=event, user=request.user)

        if (
            status_value == EventMembership.STATUS_GOING
            and membership.rsvp_status != EventMembership.STATUS_GOING
            and event.is_full
        ):
            return Response({'detail': 'This event is full.'}, status=status.HTTP_409_CONFLICT)

        membership.rsvp_status = status_value
        membership.responded_at = timezone.now()
        membership.save()
        return Response(EventMembershipSerializer(membership).data)


class LeaveEventAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        if event.is_admin(request.user):
            return Response(
                {'detail': 'The admin cannot leave their own event. Delete the event instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        EventMembership.objects.filter(event=event, user=request.user).delete()
        Attendance.objects.filter(event=event, user=request.user).delete()
        return Response({'detail': 'You left the event.'})


class RemoveMemberAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, user_id):
        event = get_object_or_404(Event, slug=slug)
        perms.require_admin(event, request.user)
        membership = get_object_or_404(EventMembership, event=event, user_id=user_id)
        user = membership.user
        membership.delete()
        Attendance.objects.filter(event=event, user=user).delete()
        send_removed_email(event, user)
        return Response({'detail': 'Member removed.'})


class InviteMemberAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        perms.require_admin(event, request.user)
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            if event.is_admin(existing_user):
                return Response({'detail': 'That user is already the admin.'}, status=status.HTTP_400_BAD_REQUEST)
            membership, created = EventMembership.objects.get_or_create(
                event=event, user=existing_user,
                defaults={'rsvp_status': EventMembership.STATUS_INVITED},
            )
            if not created:
                return Response({'detail': 'That person is already part of this event.'}, status=status.HTTP_400_BAD_REQUEST)
            send_invite_email(membership, is_new_account=False)
        else:
            invitation, created = Invitation.objects.get_or_create(
                event=event, email=email, defaults={'invited_by': request.user},
            )
            if not created and invitation.accepted:
                return Response({'detail': 'That invitation was already accepted.'}, status=status.HTTP_400_BAD_REQUEST)
            send_invite_email(invitation, is_new_account=True, token=invitation.token)

        return Response({'detail': f'Invitation sent to {email}.'})


class JoinOpenEventAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        if not event.is_open:
            return Response({'detail': 'This event is invite-only.'}, status=status.HTTP_403_FORBIDDEN)
        if event.has_member(request.user):
            return Response({'detail': 'You are already part of this event.'}, status=status.HTTP_400_BAD_REQUEST)
        if event.is_full:
            return Response({'detail': 'This event is full.'}, status=status.HTTP_409_CONFLICT)
        membership = EventMembership.objects.create(
            event=event, user=request.user, rsvp_status=EventMembership.STATUS_GOING,
            responded_at=timezone.now(),
        )
        return Response(EventMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class EventActionListCreateAPI(generics.ListCreateAPIView):
    serializer_class = EventActionSerializer
    permission_classes = [IsAuthenticated]

    def get_event(self):
        return get_object_or_404(Event, slug=self.kwargs['slug'])

    def get_queryset(self):
        event = self.get_event()
        perms.require_member_or_open(event, self.request.user)
        return EventAction.objects.filter(event=event)

    def perform_create(self, serializer):
        event = self.get_event()
        perms.require_admin(event, self.request.user)
        serializer.save(event=event)
        send_new_action_email(serializer.instance)


class EventActionDeleteAPI(generics.DestroyAPIView):
    serializer_class = EventActionSerializer
    permission_classes = [IsAuthenticated]
    queryset = EventAction.objects.all()

    def perform_destroy(self, instance):
        perms.require_admin(instance.event, self.request.user)
        instance.delete()


class EventActionCompleteAPI(APIView):
    """Toggle *your own* completion of a task. Any event member -- not just
    the admin -- can check it off, since these are shared before/after-event
    tasks rather than something only the organizer is responsible for. But
    completion itself is tracked per person: checking it off marks it done
    for you, not for every other attendee."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        action = get_object_or_404(EventAction, pk=pk)
        perms.require_member(action.event, request.user)

        completion = ActionCompletion.objects.filter(action=action, user=request.user).first()
        if completion:
            completion.delete()
        else:
            ActionCompletion.objects.create(action=action, user=request.user)

        return Response(EventActionSerializer(action, context={'request': request}).data)


class PlanningCallRsvpAPI(APIView):
    """Per-user "will you be on this call" flag. Separate from the main
    event RSVP -- someone going to the event overall may still skip a
    planning call, or vice versa before they've decided about the event."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        call = get_object_or_404(PlanningCall, pk=pk)
        perms.require_member(call.event, request.user)

        will_attend = bool(request.data.get('will_attend', True))
        previous = CallRsvp.objects.filter(call=call, user=request.user).first()
        was_attending = previous.will_attend if previous else None

        rsvp, _ = CallRsvp.objects.update_or_create(
            call=call, user=request.user, defaults={'will_attend': will_attend},
        )

        # Only ping the admin on a fresh "yes" -- not on "can't make it",
        # not on re-clicking "yes" when they were already marked attending,
        # and not when the admin is RSVPing to their own call.
        if will_attend and was_attending is not True and request.user.id != call.event.admin_id:
            send_call_rsvp_notification(call, request.user)

        return Response(
            PlanningCallSerializer(call, context={'request': request}).data,
        )


class EventPhotoListCreateAPI(generics.ListCreateAPIView):
    serializer_class = EventPhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_event(self):
        return get_object_or_404(Event, slug=self.kwargs['slug'])

    def get_queryset(self):
        event = self.get_event()
        perms.require_member_or_open(event, self.request.user)
        return EventPhoto.objects.filter(event=event)

    def perform_create(self, serializer):
        event = self.get_event()
        perms.require_member(event, self.request.user)
        serializer.save(event=event, uploaded_by=self.request.user)


class EventPhotoDeleteAPI(generics.DestroyAPIView):
    serializer_class = EventPhotoSerializer
    permission_classes = [IsAuthenticated]
    queryset = EventPhoto.objects.all()

    def perform_destroy(self, instance):
        if instance.uploaded_by_id != self.request.user.id and not instance.event.is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own photos.")
        instance.delete()


class PlanningCallListCreateAPI(generics.ListCreateAPIView):
    serializer_class = PlanningCallSerializer
    permission_classes = [IsAuthenticated]

    def get_event(self):
        return get_object_or_404(Event, slug=self.kwargs['slug'])

    def get_queryset(self):
        event = self.get_event()
        perms.require_member_or_open(event, self.request.user)
        return PlanningCall.objects.filter(event=event)

    def perform_create(self, serializer):
        event = self.get_event()
        perms.require_admin(event, self.request.user)
        serializer.save(event=event, created_by=self.request.user)
        send_new_call_email(serializer.instance)


class PlanningCallDeleteAPI(generics.DestroyAPIView):
    serializer_class = PlanningCallSerializer
    permission_classes = [IsAuthenticated]
    queryset = PlanningCall.objects.all()

    def perform_destroy(self, instance):
        perms.require_admin(instance.event, self.request.user)
        instance.delete()


class AttendanceListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        perms.require_member(event, request.user)
        going = EventMembership.objects.filter(event=event, rsvp_status=EventMembership.STATUS_GOING)
        for m in going:
            Attendance.objects.get_or_create(event=event, user=m.user)
        records = Attendance.objects.filter(event=event).select_related('user')
        return Response(AttendanceSerializer(records, many=True).data)


class AttendanceToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, user_id):
        event = get_object_or_404(Event, slug=slug)
        perms.require_member(event, request.user)
        if str(request.user.id) != str(user_id) and not event.is_admin(request.user):
            return Response(
                {'detail': 'Only the admin can check in other members.'}, status=status.HTTP_403_FORBIDDEN,
            )
        record, _ = Attendance.objects.get_or_create(event=event, user_id=user_id)
        if record.checked_in_at:
            record.checked_in_at = None
            record.checked_in_by = None
        else:
            record.checked_in_at = timezone.now()
            record.checked_in_by = request.user
        record.save()
        return Response(AttendanceSerializer(record).data)
