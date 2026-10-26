from functools import wraps

from django.core.exceptions import PermissionDenied

FACULTY_ROLES = ("Faculty")


def is_faculty(user):
    """True for logged-in users whose role is Faculty or Admin."""
    role = getattr(user, "role", None)
    return user.is_authenticated and role is not None and role.role_name in FACULTY_ROLES


def faculty_required(view):
    """Show the 403 page to anyone who isn't Faculty or Admin."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_faculty(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper