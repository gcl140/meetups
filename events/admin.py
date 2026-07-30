from django.contrib import admin

from .models import (
    Attendance, Event, EventAction, EventMembership, EventPhoto, Invitation,
    PlanningCall, ReminderLog,
)


class EventMembershipInline(admin.TabularInline):
    model = EventMembership
    extra = 0


class EventActionInline(admin.TabularInline):
    model = EventAction
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'admin', 'visibility', 'start_datetime', 'going_count', 'capacity']
    list_filter = ['visibility']
    search_fields = ['title', 'description', 'location_name']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [EventMembershipInline, EventActionInline]


@admin.register(EventMembership)
class EventMembershipAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'rsvp_status', 'joined_at']
    list_filter = ['rsvp_status']


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ['event', 'email', 'invited_by', 'accepted', 'created_at']
    list_filter = ['accepted']


@admin.register(EventAction)
class EventActionAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'action_type', 'deadline']
    list_filter = ['action_type']


@admin.register(EventPhoto)
class EventPhotoAdmin(admin.ModelAdmin):
    list_display = ['event', 'uploaded_by', 'caption', 'created_at']


@admin.register(PlanningCall)
class PlanningCallAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'scheduled_at', 'created_by']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'checked_in_at', 'checked_in_by']
    list_filter = ['event']


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'reminder_type', 'window_label', 'sent_at']
    list_filter = ['reminder_type']
