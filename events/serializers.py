from rest_framework import serializers

from .models import (
    Attendance, Event, EventAction, EventMembership, EventPhoto, PlanningCall,
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

    class Meta:
        model = EventAction
        fields = ['id', 'event', 'title', 'description', 'action_type', 'deadline', 'is_past_due']
        read_only_fields = ['event']


class EventPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.__str__', read_only=True)

    class Meta:
        model = EventPhoto
        fields = ['id', 'event', 'image', 'external_url', 'caption', 'uploaded_by_name', 'created_at']
        read_only_fields = ['event', 'uploaded_by_name']


class PlanningCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanningCall
        fields = ['id', 'event', 'title', 'description', 'scheduled_at', 'call_link']
        read_only_fields = ['event']


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
