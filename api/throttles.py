"""
Custom throttle classes for specific actions.
"""

from rest_framework.throttling import UserRateThrottle


class AssignPositionThrottle(UserRateThrottle):
    """Throttle for position assignment - max 10 per minute"""
    scope = 'assign_position'


class CancelPositionThrottle(UserRateThrottle):
    """Throttle for position cancellation - max 10 per minute"""
    scope = 'cancel_position'


class SwapRequestThrottle(UserRateThrottle):
    """Throttle for swap requests - max 5 per 10 minutes"""
    scope = 'swap_request'


class AcceptSwapThrottle(UserRateThrottle):
    """Throttle for accepting swaps - max 10 per minute"""
    scope = 'accept_swap'


class BulkCancelThrottle(UserRateThrottle):
    """Throttle for bulk cancel - max 5 per hour"""
    scope = 'bulk_cancel'


class LoginThrottle(UserRateThrottle):
    """Throttle for login attempts - max 10 per 15 minutes"""
    scope = 'login'


class RegisterThrottle(UserRateThrottle):
    """Throttle for registration - max 3 per hour"""
    scope = 'register'
