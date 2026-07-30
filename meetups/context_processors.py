from django.conf import settings


def site_settings(request):
    return {
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        'SITE_URL': settings.SITE_URL,
    }
