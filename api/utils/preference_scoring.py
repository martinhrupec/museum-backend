"""
Preference scoring utilities for assignment algorithm.

Calculates exhibition and day preference scores (0-2 range, sum = n).
"""
from decimal import Decimal


def calculate_exhibition_preference_score(guard, exhibition, next_week_start):
    """
    Calculate exhibition preference score for guard-exhibition pair.
    
    Logic:
    - If no preference set: return 1.0 (neutral)
    - If preference set: linear mapping rank 1→2.0, rank n→0.0
    - Formula: 2.0 * (n - rank) / (n - 1)
    
    Args:
        guard: Guard instance
        exhibition: Exhibition instance
        next_week_start: Date of next week start (for filtering preferences)
    
    Returns:
        float: Score in range 0-2 (1.0 = neutral)
    """
    from api.api_models.preferences import GuardExhibitionPreference
    
    # Get preference for this guard and next_week
    preference = GuardExhibitionPreference.objects.filter(
        guard=guard,
        next_week_start=next_week_start
    ).first()
    
    if not preference:
        # Check for template
        preference = GuardExhibitionPreference.objects.filter(
            guard=guard,
            is_template=True
        ).first()
    
    if not preference or not preference.exhibition_order:
        # No preference set - neutral score
        return 1.0
    
    # Find exhibition rank in preference order
    try:
        rank = preference.exhibition_order.index(exhibition.id) + 1  # 1-indexed
    except ValueError:
        # Exhibition not in preference list (shouldn't happen after validation)
        return 1.0
    
    n = len(preference.exhibition_order)
    
    if n == 1:
        return 1.0  # Special case: only one exhibition
    
    # Linear mapping: rank 1 → 2.0, rank n → 0.0
    score = 2.0 * (n - rank) / (n - 1)
    
    return score


def calculate_day_preference_score(guard, day_of_week, next_week_start):
    """
    Calculate day preference score for guard-day pair.
    
    Logic:
    - If no preference set: return 1.0 (neutral)
    - If preference set: linear mapping rank 1→2.0, rank n→0.0
    - Formula: 2.0 * (n - rank) / (n - 1)
    
    Args:
        guard: Guard instance
        day_of_week: Integer 0-6 (0=Monday, 6=Sunday)
        next_week_start: Date of next week start (for filtering preferences)
    
    Returns:
        float: Score in range 0-2 (1.0 = neutral)
    """
    from api.api_models.preferences import GuardDayPreference
    
    # Get preference for this guard and next_week
    preference = GuardDayPreference.objects.filter(
        guard=guard,
        next_week_start=next_week_start
    ).first()
    
    if not preference:
        # Check for template
        preference = GuardDayPreference.objects.filter(
            guard=guard,
            is_template=True
        ).first()
    
    if not preference or not preference.day_order:
        # No preference set - neutral score
        return 1.0
    
    # Find day rank in preference order
    try:
        rank = preference.day_order.index(day_of_week) + 1  # 1-indexed
    except ValueError:
        # Day not in preference list (shouldn't happen after validation)
        return 1.0
    
    n = len(preference.day_order)
    
    if n == 1:
        return 1.0  # Special case: only one day
    
    # Linear mapping: rank 1 → 2.0, rank n → 0.0
    score = 2.0 * (n - rank) / (n - 1)
    
    return score
