from rest_framework.exceptions import PermissionDenied


def require_admin(event, user):
    if not event.is_admin(user):
        raise PermissionDenied('Only the event admin can do that.')


def require_member_or_open(event, user):
    if event.is_admin(user) or event.has_member(user):
        return
    if event.is_open:
        return
    raise PermissionDenied('You are not part of this event.')


def require_member(event, user):
    if event.is_admin(user) or event.has_member(user):
        return
    raise PermissionDenied('You are not part of this event.')
