from rest_framework.permissions import BasePermission


class IsOrganiser(BasePermission):
    """Only organisers can create and manage events."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'organiser'
        )


class IsOrganiserOrReadOnly(BasePermission):
    """Organisers can edit. Everyone else can only read."""

    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return (
            request.user.is_authenticated and
            request.user.role == 'organiser'
        )

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return obj.organiser == request.user