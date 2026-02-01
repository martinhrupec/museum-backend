# Import all models so Django can discover them
from .user_type import User, Guard, ActiveUserManager, ActiveGuardManager
from .schedule import Exhibition, Position, PositionHistory, NonWorkingDay
from .calculation import Point, GuardAvailablePositions, GuardWorkPeriod
from .textual_model import AdminNotification, Report, PositionSwapRequest
from .system_settings import SystemSettings, HourlyRateHistory
from .preferences import GuardExhibitionPreference, GuardDayPreference
from .audit_log import AuditLog

__all__ = [
    # User models
    'User',
    'Guard',
    'ActiveUserManager',
    'ActiveGuardManager',
    # Schedule models
    'Exhibition',
    'Position',
    'PositionHistory',
    'NonWorkingDay',
    # Calculation models
    'Point',
    'GuardAvailablePositions',
    'GuardWorkPeriod',
    # Textual models
    'AdminNotification',
    'Report',
    'PositionSwapRequest',
    # Settings
    'SystemSettings',
    'HourlyRateHistory',
    # Preferences
    'GuardExhibitionPreference',
    'GuardDayPreference',
    # Audit
    'AuditLog',
]

# Ensure signals are registered by importing modules
# (Signals are registered when @receiver decorator is executed at module load)
from . import user_type  # noqa: F401
from . import schedule  # noqa: F401
from . import textual_model  # noqa: F401
from . import system_settings  # noqa: F401
