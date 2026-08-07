from django.utils import timezone
from rest_framework import serializers

from .models import (
    Attendance, CallRsvp, Event, EventAction, EventMembership, EventPhoto, PlanningCall,
)


class MemberSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    avatar = serializers.SerializerMethodField()
    rsvp_status = serializers.CharField()
    is_admin = serializers.BooleanField()

    def get_avatar(self, obj):
        return obj.get('avatar')


class EventListSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='admin.__str__', read_only=True)
    going_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    cover_image = serializers.ImageField(read_only=True)
    url = serializers.SerializerMethodField()
    my_rsvp_status = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'cover_image', 'admin_name',
            'visibility', 'capacity', 'going_count', 'is_full',
            'location_name', 'start_datetime', 'end_datetime', 'url', 'my_rsvp_status',
        ]

    def get_url(self, obj):
        return obj.get_absolute_url()

    def get_my_rsvp_status(self, obj):
        user = self.context['request'].user
        if not user.is_authenticated:
            return None
        membership = obj.membership_set.filter(user=user).first()
        return membership.rsvp_status if membership else None


class EventActionSerializer(serializers.ModelSerializer):
    is_past_due = serializers.BooleanField(read_only=True)
    my_is_completed = serializers.SerializerMethodField()
    completed_by_names = serializers.SerializerMethodField()

    class Meta:
        model = EventAction
        fields = [
            'id', 'event', 'title', 'description', 'action_type', 'deadline', 'is_past_due',
            'my_is_completed', 'completed_by_names',
        ]
        read_only_fields = ['event']

    def get_my_is_completed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        return obj.completions.filter(user=request.user).exists()

    def get_completed_by_names(self, obj):
        # Shown regardless of the viewer's own completion -- "who's done
        # their part" is useful to everyone, not just people who've done theirs.
        return [str(c.user) for c in obj.completions.select_related('user').all()]


class EventPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.__str__', read_only=True)

    class Meta:
        model = EventPhoto
        fields = ['id', 'event', 'image', 'external_url', 'caption', 'uploaded_by_name', 'created_at']
        read_only_fields = ['event', 'uploaded_by_name']


class PlanningCallSerializer(serializers.ModelSerializer):
    is_past_due = serializers.BooleanField(read_only=True)
    is_ongoing = serializers.BooleanField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    my_will_attend = serializers.SerializerMethodField()
    attendees = serializers.SerializerMethodField()

    class Meta:
        model = PlanningCall
        fields = [
            'id', 'event', 'title', 'description', 'scheduled_at', 'ends_at', 'call_link',
            'is_past_due', 'is_ongoing', 'duration_minutes', 'my_will_attend', 'attendees',
        ]
        read_only_fields = ['event']

    def validate(self, attrs):
        # Only ever runs on create -- there's no call-edit endpoint, just
        # add/delete, so self.instance is always None here.
        scheduled_at = attrs.get('scheduled_at')
        ends_at = attrs.get('ends_at')
        if scheduled_at and scheduled_at < timezone.now():
            raise serializers.ValidationError({'scheduled_at': "Can't schedule a call in the past."})
        if ends_at and scheduled_at and ends_at <= scheduled_at:
            raise serializers.ValidationError({'ends_at': 'End time must be after the start time.'})
        return attrs

    def get_my_will_attend(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        rsvp = obj.rsvps.filter(user=request.user).first()
        return rsvp.will_attend if rsvp else None

    def get_attendees(self, obj):
        # Shown regardless of the viewer's own RSVP -- "who's coming" is
        # useful to everyone deciding whether to join, not just attendees.
        return [str(r.user) for r in obj.rsvps.filter(will_attend=True).select_related('user')]


class CallRsvpSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRsvp
        fields = ['id', 'call', 'user', 'will_attend', 'responded_at']
        read_only_fields = ['call', 'user', 'responded_at']


class AttendanceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.__str__', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'event', 'user', 'user_name', 'user_email', 'checked_in_at', 'checked_in_by']
        read_only_fields = ['event', 'user', 'checked_in_by']


class EventMembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.__str__', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = EventMembership
        fields = ['id', 'event', 'user', 'user_name', 'user_email', 'rsvp_status', 'joined_at', 'responded_at']
        read_only_fields = ['event', 'user', 'joined_at', 'responded_at']
