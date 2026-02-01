"""Simple test to check fixture isolation."""
import pytest
from api.api_models import User, Guard


@pytest.mark.django_db
def test_simple_guard_creation(create_guard_with_user):
    """Test that we can create a guard without conflicts."""
    guard = create_guard_with_user('simple_guard', 'simple@test.com', availability=1)
    
    assert guard is not None
    assert guard.user.username == 'simple_guard'
    assert User.objects.count() == 1
    assert Guard.objects.count() == 1
