from django.urls import path

from . import api

urlpatterns = [
    path('events/', api.EventListAPI.as_view(), name='api-event-list'),
    path('events/<slug:slug>/members/', api.EventMembersAPI.as_view(), name='api-event-members'),
    path('events/<slug:slug>/rsvp/', api.RsvpAPI.as_view(), name='api-event-rsvp'),
    path('events/<slug:slug>/join/', api.JoinOpenEventAPI.as_view(), name='api-event-join'),
    path('events/<slug:slug>/leave/', api.LeaveEventAPI.as_view(), name='api-event-leave'),
    path('events/<slug:slug>/invite/', api.InviteMemberAPI.as_view(), name='api-event-invite'),
    path(
        'events/<slug:slug>/members/<int:user_id>/remove/',
        api.RemoveMemberAPI.as_view(), name='api-event-remove-member',
    ),
    path('events/<slug:slug>/actions/', api.EventActionListCreateAPI.as_view(), name='api-event-actions'),
    path('actions/<int:pk>/', api.EventActionDeleteAPI.as_view(), name='api-action-delete'),
    path('events/<slug:slug>/photos/', api.EventPhotoListCreateAPI.as_view(), name='api-event-photos'),
    path('photos/<int:pk>/', api.EventPhotoDeleteAPI.as_view(), name='api-photo-delete'),
    path('events/<slug:slug>/calls/', api.PlanningCallListCreateAPI.as_view(), name='api-event-calls'),
    path('calls/<int:pk>/', api.PlanningCallDeleteAPI.as_view(), name='api-call-delete'),
    path('events/<slug:slug>/attendance/', api.AttendanceListAPI.as_view(), name='api-event-attendance'),
    path(
        'events/<slug:slug>/attendance/<int:user_id>/toggle/',
        api.AttendanceToggleAPI.as_view(), name='api-attendance-toggle',
    ),
]
