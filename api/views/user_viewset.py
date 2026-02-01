from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from ..api_models import User
from ..serializers import (
    UserBasicSerializer, UserDetailSerializer, UserAdminSerializer,
    ChangePasswordSerializer
)
from ..permissions import IsAdminRole, IsAdminOrOwner
from ..mixins import AuditLogMixin


class UserViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing users with role-based access control.
    
    - Admins can manage all users
    - Regular users can only view/update their own profile
    - Custom endpoint for password changes

    

    ModelViewSet is automatically mapping:
    
    list(self, request)      -> GET /users/
    create(self, request)    -> POST /users/
    retrieve(self, request, pk=None)  -> GET /users/{id}/
    update(self, request, pk=None)    -> PUT /users/{id}/ -> changes whole object
    partial_update(self, request, pk=None) -> PATCH /users/{id}/ -> changes part of the object
    destroy(self, request, pk=None)   -> DELETE /users/{id}/
    
    Helper methods:
    get_object(self)         -> retrieves the User instance based on pk
    get_queryset(self)       -> returns the queryset of User objects
    get_serializer_class(self) -> returns the serializer class to be used
    get_permissions(self)    -> returns the list of permission classes to be used
    get_serializer(self, *args, **kwargs) -> returns the serializer instance
    perform_create(self, serializer) -> saves a new User instance
    perform_update(self, serializer) -> saves updates to an existing User instance
    perform_destroy(self, instance) -> deletes a User instance
    filter_queryset(self, queryset) -> filters the queryset based on request parameters
    paginate_queryset(self, queryset) -> paginates the queryset if pagination is enabled
    
    """
    
    queryset = User.objects.all()
    # permission_classes se postavlja u get_permissions() metodi
    
    def get_serializer_class(self):
        """Return appropriate serializer based on user role and action"""
        if self.action == 'change_password':
            return ChangePasswordSerializer
        elif self.request.user.role == User.ROLE_ADMIN:
            return UserAdminSerializer
        elif self.action in ['list', 'retrieve']:
            return UserDetailSerializer
        else:
            return UserDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role and show only active users"""
        if self.request.user.role == User.ROLE_ADMIN:
            # Admin can see all users (including inactive ones with ?show_inactive=true)
            if self.request.query_params.get('show_inactive') == 'true':
                return User.objects.all()
            return User.objects.filter(is_active=True)
        else:
            return User.objects.filter(is_active=True)

    def get_permissions(self):
        """Set permissions based on action using custom role-based permissions"""
        if self.action in ['create', 'destroy']:
            # Only ROLE_ADMIN can create/delete users
            return [IsAdminRole()]
        elif self.action in ['retrieve', 'update', 'partial_update']:
            # Admin can access all, users can access only their own
            return [IsAdminOrOwner()]
        elif self.action in ['list', 'me', 'update_profile', 'change_password']:
            # All authenticated users, but queryset filtering handles access
            return [permissions.IsAuthenticated()]
        else:
            # Default: require authentication
            return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        """Soft delete - set is_active to False instead of actual deletion"""
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'message': 'Korisnik je deaktiviran.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update current user's profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change current user's password"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Lozinka je uspješno promijenjena.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
