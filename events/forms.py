from django import forms

from .models import Event, EventAction, EventPhoto, PlanningCall
from .richtext import sanitize_rich_text

DATETIME_WIDGET = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'cover_image', 'title', 'description',
            'start_datetime', 'end_datetime',
            'location_name', 'location_address', 'latitude', 'longitude',
            'visibility', 'capacity',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': '!text-lg !font-medium', 'placeholder': 'Give it a name'}),
            'start_datetime': DATETIME_WIDGET,
            'end_datetime': DATETIME_WIDGET,
            # Rendered as a hidden field -- static/js/rich_text.js mounts a Quill
            # editor over it and keeps this in sync so it still POSTs normally.
            'description': forms.Textarea(attrs={'id': 'id_description', 'class': 'hidden'}),
            'location_name': forms.TextInput(attrs={'placeholder': 'e.g. Dartmouth College'}),
            'location_address': forms.TextInput(attrs={'placeholder': 'Street address (optional)'}),
            # Kept out of the visible layout (see event_form.html) -- filled in by the
            # "Use my location" button. Still real form fields so they validate/submit normally.
            'latitude': forms.HiddenInput(attrs={'id': 'id_latitude'}),
            'longitude': forms.HiddenInput(attrs={'id': 'id_longitude'}),
            'visibility': forms.RadioSelect(attrs={'class': 'peer sr-only'}),
            'capacity': forms.NumberInput(attrs={'placeholder': 'Unlimited', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('start_datetime', 'end_datetime'):
            value = self.initial.get(name) or getattr(self.instance, name, None)
            if value:
                self.initial[name] = value.strftime('%Y-%m-%dT%H:%M')

    def clean_description(self):
        return sanitize_rich_text(self.cleaned_data.get('description', ''))

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        # is_past (models.py) treats end_datetime as authoritative when set,
        # so an end before the start makes an event that hasn't happened
        # yet read as already over -- reject it here instead of downstream.
        if start and end and end < start:
            self.add_error('end_datetime', 'End time must be after the start time.')
        return cleaned_data


class EventActionForm(forms.ModelForm):
    class Meta:
        model = EventAction
        fields = ['title', 'description', 'action_type', 'deadline']
        widgets = {
            'deadline': DATETIME_WIDGET,
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class EventPhotoForm(forms.ModelForm):
    class Meta:
        model = EventPhoto
        fields = ['image', 'external_url', 'caption']


class PlanningCallForm(forms.ModelForm):
    class Meta:
        model = PlanningCall
        fields = ['title', 'description', 'scheduled_at', 'call_link']
        widgets = {
            'scheduled_at': DATETIME_WIDGET,
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class InviteForm(forms.Form):
    email = forms.EmailField()
