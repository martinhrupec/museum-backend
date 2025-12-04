from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .api_models import User

User = get_user_model()


class UserAPITestCase(TestCase):
    """Test suite for User API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        # Admin - ima is_staff=True i ROLE_ADMIN
        self.admin_user = User.objects.create_user(
            username='admin',
            password='adminpass123',
            email='admin@test.com',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=False,
            role=User.ROLE_ADMIN
        )
        
        # Guard - obični korisnik muzeja  
        self.guard_user = User.objects.create_user(
            username='guard',
            password='guardpass123',
            email='guard@test.com',
            first_name='Guard',
            last_name='User',
            role=User.ROLE_GUARD
        )
        
        # Drugi guard za testove
        self.other_guard = User.objects.create_user(
            username='other_guard',
            password='otherpass123',
            email='other@test.com',
            first_name='Other',
            last_name='Guard',
            role=User.ROLE_GUARD
        )

    # ===========================================
    # JWT Authentication Tests
    # ===========================================
    
    def test_jwt_login_success(self):
        """Test successful JWT login"""
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_jwt_login_invalid_credentials(self):
        """Test JWT login with invalid credentials"""
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_jwt_refresh_token(self):
        """Test JWT token refresh"""
        # Get tokens
        login_response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'adminpass123'
        })
        refresh_token = login_response.data['refresh']
        
        # Refresh token
        response = self.client.post('/api/token/refresh/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    # ===========================================
    # CRUD Operations Tests (6 default methods)
    # ===========================================
    
    def test_list_users_unauthorized(self):
        """Test GET /api/users/ without authentication"""
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_users_as_admin(self):
        """Test GET /api/users/ as admin"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # All 3 users
    
    def test_list_users_as_guard(self):
        """Test GET /api/users/ as guard (should see only themselves)"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only themselves
        self.assertEqual(response.data['results'][0]['username'], 'guard')
    
    def test_create_user_as_admin(self):
        """Test POST /api/users/ as admin (should succeed)"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/users/', {
            'username': 'newuser',
            'password': 'newpass123',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': User.ROLE_GUARD
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 4)
    
    def test_create_user_as_guard(self):
        """Test POST /api/users/ as guard (should fail)"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.post('/api/users/', {
            'username': 'newuser',
            'password': 'newpass123',
            'email': 'newuser@test.com',
            'role': User.ROLE_GUARD
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_user_as_admin(self):
        """Test GET /api/users/{id}/ as admin"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/users/{self.guard_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'guard')
    
    def test_retrieve_user_as_guard_own_profile(self):
        """Test GET /api/users/{id}/ as guard (own profile)"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get(f'/api/users/{self.guard_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_user_as_guard_other_profile(self):
        """Test GET /api/users/{id}/ as guard (other profile - should fail)"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get(f'/api/users/{self.admin_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_user_as_admin(self):
        """Test PUT /api/users/{id}/ as admin"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put(f'/api/users/{self.guard_user.id}/', {
            'username': 'guard',
            'email': 'updated@test.com',
            'first_name': 'Updated',
            'last_name': 'User',
            'role': User.ROLE_GUARD,
            'is_active': True
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.guard_user.refresh_from_db()
        self.assertEqual(self.guard_user.email, 'updated@test.com')
    
    def test_partial_update_user(self):
        """Test PATCH /api/users/{id}/ (partial update)"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(f'/api/users/{self.guard_user.id}/', {
            'first_name': 'PartiallyUpdated'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.guard_user.refresh_from_db()
        self.assertEqual(self.guard_user.first_name, 'PartiallyUpdated')
    
    def test_destroy_user_soft_delete(self):
        """Test DELETE /api/users/{id}/ (our custom soft delete)"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(f'/api/users/{self.guard_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check user is soft deleted
        self.guard_user.refresh_from_db()
        self.assertFalse(self.guard_user.is_active)
        self.assertEqual(response.data['message'], 'Korisnik je deaktiviran.')

    # ===========================================
    # Custom Action Tests
    # ===========================================
    
    def test_me_endpoint(self):
        """Test GET /api/users/me/"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'guard')
    
    def test_me_endpoint_unauthorized(self):
        """Test GET /api/users/me/ without authentication"""
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile_endpoint(self):
        """Test PUT /api/users/update_profile/"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.put('/api/users/update_profile/', {
            'first_name': 'UpdatedFirstName',
            'last_name': 'UpdatedLastName',
            'email': 'updatedemail@test.com'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.guard_user.refresh_from_db()
        self.assertEqual(self.guard_user.first_name, 'UpdatedFirstName')
    
    def test_update_profile_partial(self):
        """Test PATCH /api/users/update_profile/ (partial update)"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.patch('/api/users/update_profile/', {
            'email': 'newemail@test.com'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.guard_user.refresh_from_db()
        self.assertEqual(self.guard_user.email, 'newemail@test.com')
    
    def test_change_password_success(self):
        """Test POST /api/users/change_password/ with correct old password"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.post('/api/users/change_password/', {
            'old_password': 'guardpass123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password was changed
        self.guard_user.refresh_from_db()
        self.assertTrue(self.guard_user.check_password('newpassword123'))
    
    def test_change_password_wrong_old_password(self):
        """Test POST /api/users/change_password/ with wrong old password"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.post('/api/users/change_password/', {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)
    
    def test_change_password_mismatch(self):
        """Test POST /api/users/change_password/ with password mismatch"""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.post('/api/users/change_password/', {
            'old_password': 'guardpass123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'differentpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password_confirm', response.data)

    # ===========================================
    # Helper Methods Tests
    # ===========================================
    
    def test_queryset_filtering_admin_show_inactive(self):
        """Test get_queryset with ?show_inactive=true as admin"""
        # Deactivate a user
        self.other_guard.is_active = False
        self.other_guard.save()
        
        self.client.force_authenticate(user=self.admin_user)
        
        # Without show_inactive - should see only active users
        response = self.client.get('/api/users/')
        self.assertEqual(len(response.data['results']), 2)  # admin + guard
        
        # With show_inactive - should see all users
        response = self.client.get('/api/users/?show_inactive=true')
        self.assertEqual(len(response.data['results']), 3)  # All users
    
    def test_serializer_class_selection(self):
        """Test that proper serializer is selected based on user role"""
        # Admin should get UserAdminSerializer with extra fields
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/users/{self.guard_user.id}/')
        self.assertIn('is_staff', response.data)  # Admin serializer field
        
        # Guard should get UserDetailSerializer
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get(f'/api/users/{self.guard_user.id}/')
        self.assertNotIn('is_staff', response.data)  # Not in detail serializer
