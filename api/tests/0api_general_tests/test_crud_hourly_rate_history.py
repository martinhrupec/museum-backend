"""
Integration tests for HourlyRateHistory model functionality.

HourlyRateHistory does not have a CRUD API endpoint.
It is automatically managed through SystemSettings:
- Created automatically when SystemSettings.hourly_rate changes (via Django signal)
- Used to retrieve historical rates for accurate earnings calculations

Tests verify:
- Automatic creation of history entries when rate changes
- get_rate_for_date() returns correct historical rates
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from api.api_models import HourlyRateHistory, SystemSettings


@pytest.mark.django_db
class TestHourlyRateHistoryAutomation:
    """Test automatic HourlyRateHistory creation via SystemSettings changes"""
    
    def test_hourly_rate_history_created_when_rate_changes(self, admin_user):
        """
        When SystemSettings hourly_rate changes, HourlyRateHistory entry is auto-created.
        
        Expected: New HourlyRateHistory entry with new rate
        """
        # Get current settings
        settings = SystemSettings.get_active()
        old_rate = settings.hourly_rate
        new_rate = Decimal('18.50')
        
        # Change hourly rate
        settings.hourly_rate = new_rate
        settings.updated_by = admin_user
        settings.save()
        
        # Verify history entry was created
        latest_history = HourlyRateHistory.objects.order_by('-effective_from').first()
        assert latest_history is not None
        assert latest_history.hourly_rate == new_rate
        assert latest_history.changed_by == admin_user