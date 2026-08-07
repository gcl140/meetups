from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('events/new/', views.event_create, name='create'),
    path('events/<slug:slug>/', views.event_detail, name='detail'),
    path('events/<slug:slug>/edit/', views.event_edit, name='edit'),
    path('events/<slug:slug>/delete/', views.event_delete, name='delete'),
    path('events/<slug:slug>/export.ics', views.export_event_ics, name='export-ics'),
    path('events/<slug:slug>/actions/<int:action_id>/export.ics', views.export_action_ics, name='export-action-ics'),
    path('events/<slug:slug>/calls/<int:call_id>/export.ics', views.export_call_ics, name='export-call-ics'),
]
