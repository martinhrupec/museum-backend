"""
Test run_automated_assignment management command.
"""
import pytest
from io import StringIO
from django.core.management import call_command
from api.api_models import Position, Guard
from unittest.mock import patch


@pytest.mark.django_db
class TestRunAutomatedAssignmentCommand:
    """Test run_automated_assignment management command."""
    
    def test_assignment_with_force_flag(self, system_settings, guard_user, sample_exhibition):
        """Test assignment with --force flag (skip confirmation)."""
        # Setup
        exhibition = sample_exhibition
        guard = Guard.objects.get(user=guard_user)
        guard.availability = 5
        guard.save()
        
        # Generate positions
        call_command('generate_positions', stdout=StringIO())
        
        # Check that positions exist and are unassigned
        unassigned_count = Position.objects.filter(position_histories__isnull=True).count()
        assert unassigned_count > 0
        
        # Run command with --force
        out = StringIO()
        call_command('run_automated_assignment', '--force', stdout=out)
        
        # Verify output
        output = out.getvalue()
        assert '✓' in output or 'completed' in output.lower()
    
    @patch('builtins.input', return_value='yes')
    def test_assignment_with_confirmation(self, mock_input, system_settings, guard_user, sample_exhibition):
        """Test assignment with user confirmation."""
        # Setup
        exhibition = sample_exhibition
        guard = Guard.objects.get(user=guard_user)
        guard.availability = 3
        guard.save()
        
        # Generate positions
        call_command('generate_positions', stdout=StringIO())
        
        # Run command with confirmation
        out = StringIO()
        call_command('run_automated_assignment', stdout=out)
        
        # Verify warning was shown
        output = out.getvalue()
        assert '⚠️' in output or 'WARNING' in output
        assert mock_input.called
    
    @patch('builtins.input', return_value='no')
    def test_assignment_abort(self, mock_input, system_settings):
        """Test aborting assignment on 'no' confirmation."""
        out = StringIO()
        call_command('run_automated_assignment', stdout=out)
        
        output = out.getvalue()
        assert 'Aborted' in output or 'abort' in output.lower()
