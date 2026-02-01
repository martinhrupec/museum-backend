# Tests for utility functions and model methods

This directory contains tests for helper functions.

## Refactored functions:

### ✅ Helper functions in Models (api_models/)

- Position.get_assigned_guard() - Get currently assigned guard for a position
- Position.get_start_datetime() - Get timezone-aware datetime when position starts
- Poisition.clean()
- Position.is_special_event()
- Position.get_duration_hours()
- Position.get_period()
- AuditLog.log_create()
- AuditLog.log_update()
- AuditLog.log_delete()
- AuditLog.get_client_ip()
- default_open_days()
- Exhibition.is_active()
- Exhibition.is_upcoming()
- Exhibition.is_finished()
- Exhibition.clean()
- NonWorkingDay.delete_affected_positions()
- generate_special_event_positions
- _generate_positions_for_exhibition
- custom funkcije u system_settings...
...
- User.save()


### ✅ Helper functions in Utils (api/utils/)

- guard_matches_multicast() - utils/notification_matching.py - Check if guard matches multicast notification criteria
- calculate_max_availability_for_week() - utils/position_calculation.py - Calculate max availability based on workdays and holidays

### ✅ Helper functions in Viewsets (view-specific logic, api/views/)

- \_ensure_configuration_window_open (GuardViewSet) - Returns Response objects
- \_ensure_manual_window_open (PositionHistoryViewSet) - Returns Response objects
- \_check_grace_period_restrictions (PositionHistoryViewSet) - Returns Response objects
- \_resolve_guard_from_request (PositionHistoryViewSet) - Parses request.data/user
- \_invalidate_schedule_cache (PositionHistoryViewSet) - Cache invalidation
- \_build_assigned_schedule (PositionHistoryViewSet) - Schedule building logic
- \_build_week_response (PositionHistoryViewSet) - Response wrapper

## Tests to implement:

### Position model methods
