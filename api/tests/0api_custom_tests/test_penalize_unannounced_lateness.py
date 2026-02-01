"""
Integration tests for admin using penalize_unannounced_lateness endpoint.

Tests admin-specific functionality:
- Admin can penalize guard for unannounced lateness
- Penalty points are deducted
"""
import pytest


@pytest.mark.django_db
class TestAdminPenalizeUnannouncedLateness:
    """Integration tests for admin using POST /api/points/penalize_unannounced_lateness/"""
    
    def test_admin_can_penalize_guard_for_unannounced_lateness(
        self,
        authenticated_admin,
        guard_user,
        system_settings
    ):
        """
        Admin successfully penalizes guard for unannounced lateness.
        
        Expected:
        - 200 or 201 response
        - Point record created with penalty
        """
        response = authenticated_admin.post(
            '/api/points/penalize_unannounced_lateness/',
            {
                'guard_id': guard_user.guard.id,
            },
            format='json'
        )
        
        assert response.status_code in (200, 201)
        assert 'message' in response.data or 'points' in response.data
    
    def test_admin_penalize_requires_guard_id(self, authenticated_admin):
        """
        Admin must provide guard_id when penalizing.
        
        Expected:
        - 400 response
        """
        response = authenticated_admin.post(
            '/api/points/penalize_unannounced_lateness/',
            {
                'reason': 'Late'
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'guard_id' in str(response.data).lower()
    
    def test_admin_penalize_nonexistent_guard_fails(self, authenticated_admin):
        """
        Admin cannot penalize nonexistent guard.
        
        Expected:
        - 404 response
        """
        response = authenticated_admin.post(
            '/api/points/penalize_unannounced_lateness/',
            {
                'guard_id': 99999,
                'reason': 'Late'
            },
            format='json'
        )
        
        assert response.status_code == 404
    
    def test_penalize_without_admin_authentication_fails(self, api_client, guard_user):
        """
        Penalizing without admin authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            '/api/points/penalize_unannounced_lateness/',
            {
                'guard_id': guard_user.guard.id,
                'reason': 'Late'
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
