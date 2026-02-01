"""
Integration test demonstrating proper Guard creation.

Guards are created automatically via signal when User with role=ROLE_GUARD is created.
Admin should create User with role='guard', NOT create Guard directly.
"""
import pytest
from api.api_models import User, Guard


@pytest.mark.django_db
class TestProperGuardCreation:
    """Test proper way to create guards through User endpoint"""
    
    def test_admin_creates_guard_via_user_creation(self, authenticated_admin):
        """
        Admin creates User with role='guard' → Signal auto-creates Guard profile.
        
        Expected:
        - 201 Created
        - User created with role=ROLE_GUARD
        - Guard profile auto-created via signal
        """
        response = authenticated_admin.post(
            '/api/users/',
            {
                'username': 'newguard',
                'password': 'testpass123',
                'email': 'newguard@museum.com',
                'first_name': 'New',
                'last_name': 'Guard',
                'role': 'guard'
            },
            format='json'
        )
        
        assert response.status_code == 201
        assert response.data['username'] == 'newguard'
        assert response.data['role'] == 'guard'
        
        # Verify User created
        user = User.objects.get(username='newguard')
        assert user.role == User.ROLE_GUARD
        
        # Verify Guard profile auto-created via signal
        assert hasattr(user, 'guard')
        assert user.guard is not None
        assert isinstance(user.guard, Guard)
    
    def test_guard_cannot_create_other_guards(self, authenticated_guard):
        """
        Guard cannot create other User/Guard accounts.
        
        Expected:
        - 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/users/',
            {
                'username': 'anotherguard',
                'password': 'testpass123',
                'email': 'another@museum.com',
                'role': 'guard'
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_admin_cannot_create_guard_directly_via_guards_endpoint(self, authenticated_admin, guard_user):
        """
        Admin CANNOT create Guard directly through /api/guards/.
        This ensures Guards are always properly linked to Users.
        
        Expected:
        - 405 Method Not Allowed
        """
        response = authenticated_admin.post(
            '/api/guards/',
            {
                'user': guard_user.id,
                'priority_number': 1.5
            },
            format='json'
        )
        
        assert response.status_code == 405
