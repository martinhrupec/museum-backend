"""
Test shift_weekly_periods management command.

This command shifts weekly periods in SystemSettings at start of each week:
- Old next_week becomes new this_week
- New next_week is calculated (+7 days from old next_week)
"""
import pytest
from io import StringIO
from django.core.management import call_command
from api.api_models import SystemSettings
from datetime import date, timedelta


@pytest.mark.django_db
class TestShiftWeeklyPeriodsCommand:
    """Test shift_weekly_periods management command."""
    
    def test_shift_weekly_periods_moves_next_to_this(self, system_settings):
        """Test that next_week becomes this_week after shift."""
        settings = system_settings
        
        # Store old values
        old_next_week_start = settings.next_week_start
        old_next_week_end = settings.next_week_end
        
        # Run command
        out = StringIO()
        call_command('shift_weekly_periods', stdout=out)
        
        # Refresh and verify shift happened
        settings.refresh_from_db()
        
        # Old next_week should now be this_week
        assert settings.this_week_start == old_next_week_start, \
            "next_week_start should become this_week_start"
        assert settings.this_week_end == old_next_week_end, \
            "next_week_end should become this_week_end"
        
        # New next_week should be 7 days after old next_week
        assert settings.next_week_start == old_next_week_start + timedelta(days=7), \
            "New next_week_start should be +7 days from old"
        assert settings.next_week_end == old_next_week_end + timedelta(days=7), \
            "New next_week_end should be +7 days from old"
    
    def test_shift_maintains_7_day_periods(self, system_settings):
        """Test that periods are always 7 days apart."""
        settings = system_settings
        
        # Run command
        out = StringIO()
        call_command('shift_weekly_periods', stdout=out)
        
        settings.refresh_from_db()
        
        # this_week should be 7 days
        this_week_duration = (settings.this_week_end - settings.this_week_start).days
        assert this_week_duration == 6, "this_week should span 6 days (Mon-Sun)"
        
        # next_week should start right after this_week
        assert settings.next_week_start == settings.this_week_start + timedelta(days=7), \
            "next_week should start 7 days after this_week"
    
    def test_shift_output_format(self, system_settings):
        """Test command output contains shift confirmation."""
        out = StringIO()
        call_command('shift_weekly_periods', stdout=out)
        
        output = out.getvalue()
        assert '✓' in output or 'shifted' in output.lower() or 'week' in output.lower()
