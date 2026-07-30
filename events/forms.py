from django import forms

from .models import Event, EventAction, EventPhoto, PlanningCall

DATETIME_WIDGET = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'cover_image', 'visibility', 'capacity',
            'location_name', 'location_address', 'latitude', 'longitude',
            'start_datetime', 'end_datetime',
        ]
        widgets = {
            'start_datetime': DATETIME_WIDGET,
            'end_datetime': DATETIME_WIDGET,
            'description': forms.Textarea(attrs={'rows': 5}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'id': 'id_latitude'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'id': 'id_longitude'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('start_datetime', 'end_datetime'):
            value = self.initial.get(name) or getattr(self.instance, name, None)
            if value:
                self.initial[name] = value.strftime('%Y-%m-%dT%H:%M')


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
