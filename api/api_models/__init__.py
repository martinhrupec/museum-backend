# Import all models so Django can discover them
from .user_type import User, Guard, ActiveUserManager, ActiveGuardManager
from .schedule import Exhibition, Position, PositionHistory
from .calculation import Point, GuardAvailablePositions
from .textual_model import AdminNotification, Report
from .system_settings import SystemSettings
from .preferences import GuardExhibitionPreference, GuardPositionPreference

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
    # Calculation models
    'Point',
    'GuardAvailablePositions',
    # Textual models
    'AdminNotification',
    'Report',
    # Settings
    'SystemSettings',
    # Preferences
    'GuardExhibitionPreference',
    'GuardPositionPreference',
]
