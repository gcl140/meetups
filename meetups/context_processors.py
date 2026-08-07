from django.conf import settings


def site_settings(request):
    return {
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        'SITE_URL': settings.SITE_URL,
        'GOOGLE_OAUTH_ENABLED': bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET),
    }
