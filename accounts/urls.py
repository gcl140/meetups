from django.urls import path

from . import google_oauth, views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.MeetupsLoginView.as_view(), name='login'),
    path('logout/', views.MeetupsLogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('users/<int:pk>/', views.user_profile, name='user-profile'),
    path('verify/<uidb64>/<token>/', views.verify_email, name='verify-email'),
    path('verify/resend/', views.resend_verification, name='resend-verification'),
    path('google/login/', google_oauth.google_login, name='google-login'),
    path('google/callback/', google_oauth.google_callback, name='google-callback'),
]
