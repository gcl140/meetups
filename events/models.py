import random
import string
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

SLUG_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits


def random_slug_suffix(length=6):
    return ''.join(random.choices(SLUG_SUFFIX_ALPHABET, k=length))


class Event(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_OPEN = 'open'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, 'Private (invite only)'),
        (VISIBILITY_OPEN, 'Open (anyone can join)'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='event_covers/', blank=True, null=True)

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='administered_events',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='EventMembership', related_name='events',
    )

    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    capacity = models.PositiveIntegerField(blank=True, null=True, help_text='Leave blank for unlimited.')

    location_name = models.CharField(max_length=200, blank=True)
    location_address = models.CharField(max_length=300, blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(blank=True, null=True)

    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_datetime']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            # Short and non-guessable rather than the full title: first
            # three words, then a random suffix so the URL doesn't just
            # leak the whole (possibly long) event name.
            base_slug = slugify(' '.join(self.title.split()[:3]))[:100] or 'event'
            slug = f'{base_slug}-{random_slug_suffix()}'
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{random_slug_suffix()}'
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('events:detail', args=[self.slug])

    @property
    def is_open(self):
        return self.visibility == self.VISIBILITY_OPEN

    @property
    def is_past(self):
        end = self.end_datetime or self.start_datetime
        return end < timezone.now()

    @property
    def going_count(self):
        return self.membership_set.filter(rsvp_status=EventMembership.STATUS_GOING).count()

    @property
    def is_full(self):
        return bool(self.capacity) and self.going_count >= self.capacity

    def has_member(self, user):
        if not user.is_authenticated:
            return False
        return self.membership_set.filter(user=user).exists()

    def is_admin(self, user):
        return user.is_authenticated and self.admin_id == user.id

    def google_maps_url(self):
        if self.latitude is not None and self.longitude is not None:
            query = f'{self.latitude},{self.longitude}'
        elif self.location_address:
            query = self.location_address
        elif self.location_name:
            query = self.location_name
        else:
            return ''
        from urllib.parse import quote_plus
        return f'https://www.google.com/maps/search/?api=1&query={quote_plus(query)}'


class EventMembership(models.Model):
    STATUS_INVITED = 'invited'
    STATUS_GOING = 'going'
    STATUS_MAYBE = 'maybe'
    STATUS_NOT_GOING = 'not_going'
    STATUS_CHOICES = [
        (STATUS_INVITED, 'Invited'),
        (STATUS_GOING, 'Going'),
        (STATUS_MAYBE, 'Maybe'),
        (STATUS_NOT_GOING, "Not going"),
    ]

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE,
        related_name='membership_set', related_query_name='membership',
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rsvp_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_INVITED)
    joined_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('event', 'user')
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user} @ {self.event} ({self.rsvp_status})'


class Invitation(models.Model):
    """Tracks an invite sent to an email address that may not have an
    account yet. Once that email signs up (or logs in), matching pending
    invitations are converted into EventMembership rows automatically."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'email')

    def __str__(self):
        return f'Invite for {self.email} to {self.event}'

    @classmethod
    def accept_all_for_email(cls, user):
        """Turn every pending invitation for user's email into a real
        membership. Returns the number of events joined."""
        pending = cls.objects.filter(email__iexact=user.email, accepted=False).select_related('event')
        count = 0
        for invite in pending:
            _, created = EventMembership.objects.get_or_create(
                event=invite.event, user=user,
                defaults={'rsvp_status': EventMembership.STATUS_INVITED},
            )
            invite.accepted = True
            invite.save(update_fields=['accepted'])
            if created:
                count += 1
        return count


class EventAction(models.Model):
    TYPE_BEFORE = 'before'
    TYPE_AFTER = 'after'
    TYPE_CHOICES = [
        (TYPE_BEFORE, 'Before the event'),
        (TYPE_AFTER, 'After the event'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='actions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    action_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_BEFORE)
    deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['deadline']

    def __str__(self):
        return f'{self.title} ({self.get_action_type_display()})'

    @property
    def is_past_due(self):
        return self.deadline < timezone.now()


class ActionCompletion(models.Model):
    """Per-attendee completion for a before/after-event task. Deliberately
    independent per person (like CallRsvp for planning calls) rather than a
    single shared flag -- one member finishing a task doesn't finish it for
    everyone else going to the event."""

    action = models.ForeignKey(EventAction, on_delete=models.CASCADE, related_name='completions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('action', 'user')

    def __str__(self):
        return f'{self.user} completed {self.action}'


class EventPhoto(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='photos')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='event_photos/', blank=True, null=True)
    external_url = models.URLField(blank=True, help_text='Link to a shared album, e.g. Google Photos.')
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.caption or f'Photo for {self.event}'


class PlanningCall(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='planning_calls')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    ends_at = models.DateTimeField(
        blank=True, null=True,
        help_text="When the call is expected to wrap up -- shown to attendees as the call's length.",
    )
    call_link = models.URLField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at']

    def __str__(self):
        return self.title

    @property
    def is_past_due(self):
        return (self.ends_at or self.scheduled_at) < timezone.now()

    @property
    def is_ongoing(self):
        if not self.ends_at:
            return False
        return self.scheduled_at <= timezone.now() <= self.ends_at

    @property
    def duration_minutes(self):
        if not self.ends_at:
            return None
        return int((self.ends_at - self.scheduled_at).total_seconds() // 60)


class CallRsvp(models.Model):
    """Lightweight per-user "will attend" flag for a planning call --
    deliberately not EventMembership.rsvp_status's going/maybe/not_going
    (a call is a single meeting, not the whole event), and not a shared
    completion flag either: whether a call happened isn't a thing one
    member should be able to toggle for everyone else."""

    call = models.ForeignKey(PlanningCall, on_delete=models.CASCADE, related_name='rsvps')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    will_attend = models.BooleanField(default=True)
    responded_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('call', 'user')

    def __str__(self):
        state = 'attending' if self.will_attend else 'not attending'
        return f'{self.user} @ {self.call} ({state})'


class Attendance(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendance_records')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    checked_in_at = models.DateTimeField(blank=True, null=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='+',
    )

    class Meta:
        unique_together = ('event', 'user')
        ordering = ['user__first_name', 'user__username']

    def __str__(self):
        state = 'checked in' if self.checked_in_at else 'not checked in'
        return f'{self.user} @ {self.event} ({state})'


class ReminderLog(models.Model):
    TYPE_EVENT_UPCOMING = 'event_upcoming'
    TYPE_ACTION_DEADLINE = 'action_deadline'
    TYPE_CALL_REMINDER = 'call_reminder'
    TYPE_CHOICES = [
        (TYPE_EVENT_UPCOMING, 'Event upcoming'),
        (TYPE_ACTION_DEADLINE, 'Action deadline'),
        (TYPE_CALL_REMINDER, 'Planning call reminder'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    event_action = models.ForeignKey(EventAction, on_delete=models.CASCADE, blank=True, null=True)
    planning_call = models.ForeignKey(PlanningCall, on_delete=models.CASCADE, blank=True, null=True)
    reminder_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    window_label = models.CharField(max_length=20, help_text='e.g. "7d", "1d", dedupes per reminder window.')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event', 'event_action', 'planning_call', 'reminder_type', 'window_label')
