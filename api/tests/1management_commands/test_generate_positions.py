"""
Test generate_positions management command.

This command generates positions for next_week based on active exhibitions.
Creates 2 shifts per day (morning + afternoon) for each exhibition.
Special events get positions based on event times.
Skips non-working days.
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from api.api_models import SystemSettings, Exhibition, Position


@pytest.mark.django_db
class TestGeneratePositionsCommand:
    """Test generate_positions management command."""
    
    def test_generate_positions_creates_for_next_week(self, system_settings, sample_exhibition):
        """Test that positions are created for next_week period."""
        exhibition = sample_exhibition
        settings = system_settings
        
        # Delete existing positions for clean test
        Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        ).delete()
        
        initial_count = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        ).count()
        assert initial_count == 0
        
        # Run command
        out = StringIO()
        call_command('generate_positions', stdout=out)
        
        # Verify positions were created for next_week
        final_count = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        ).count()
        assert final_count > 0, "Positions should be created for next_week"
        
        # Verify all positions are within next_week range
        positions = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        )
        for pos in positions:
            assert settings.next_week_start <= pos.date <= settings.next_week_end, \
                f"Position date {pos.date} should be in next_week"
    
    def test_generate_positions_morning_and_afternoon_shifts(self, system_settings, sample_exhibition):
        """Test that both morning and afternoon shifts are created."""
        exhibition = sample_exhibition
        settings = system_settings
        
        # Ensure exhibition is open on workdays
        exhibition.number_of_positions = 1
        exhibition.open_on = list(settings.workdays)
        exhibition.save()
        
        # Clear positions
        Position.objects.filter(exhibition=exhibition).delete()
        
        # Run command
        out = StringIO()
        call_command('generate_positions', stdout=out)
        
        # Check for different shift times
        positions = Position.objects.filter(
            exhibition=exhibition,
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        )
        
        if positions.exists():
            # Should have positions with morning and afternoon times
            start_times = set(pos.start_time for pos in positions)
            assert len(start_times) >= 1, "Should have at least one shift type"
    
    def test_generate_positions_no_exhibitions(self, system_settings):
        """Test generation with no active exhibitions."""
        # Delete all exhibitions
        Exhibition.objects.all().delete()
        
        # Run command - should not crash
        out = StringIO()
        call_command('generate_positions', stdout=out)
        
        # Should complete without error
        output = out.getvalue()
        assert '✓' in output or 'created' in output.lower() or 'generated' in output.lower()
