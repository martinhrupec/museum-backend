"""
Custom permissions for museum backend.
Clean, minimal permissions without redundancy.
"""
from rest_framework import permissions
from .api_models import User


class IsAdminRole(permissions.BasePermission):
    """
    Permission for ROLE_ADMIN users only.
    
    Double-checks both business role AND Django is_staff for extra safety,
    though save() method should ensure they're always in sync.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and 
            request.user.role == User.ROLE_ADMIN and
            request.user.is_staff  # Defensive check
        )


class IsAdminOrOwner(permissions.BasePermission):
    """
    Object-level permission:
    - Admins can access/modify ALL objects
    - Regular users can access/modify only THEIR OWN objects
    
    Use this for ViewSets where guards should see only their data.
    """
    def has_permission(self, request, view):
        # Everyone authenticated can try to access
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admins can access everything (double-check for safety)
        if (request.user.role == User.ROLE_ADMIN and request.user.is_staff):
            return True
        
        # Users can only access their own objects
        if hasattr(obj, 'user'):  # obj.user = owner
            return obj.user == request.user
        
        # If object IS a user, check if it's themselves
        if hasattr(obj, 'username'):  # It's a User object
            return obj == request.user
        
        return False