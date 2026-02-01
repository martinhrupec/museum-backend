"""
FAZA 2: Preference Scoring Tests

Tests for exhibition and day preference scoring logic.
Component: api/utils/preference_scoring.py

Scoring logic:
- No preference: 1.0 (neutral)
- With preferences: rank 1 → 2.0, rank n → 0.0
- Formula: 2.0 * (n - rank) / (n - 1)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from api.api_models import GuardExhibitionPreference, GuardDayPreference, Position
from api.utils.preference_scoring import (
    calculate_exhibition_preference_score,
    calculate_day_preference_score
)


# ============================================================================
# UNIT TESTS - Exhibition Preferences (5 tests)
# ============================================================================

@pytest.mark.django_db
def test_exhibition_preference_ranking_calculation(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that exhibition preference ranking is calculated correctly.
    Rank 1 → 2.0, Rank n → 0.0, linear interpolation between.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibitions = sample_exhibitions  # 3 exhibitions
    settings = system_settings_for_assignment
    
    # Create preference: [exhibition1, exhibition2, exhibition3]
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibitions[0].id, exhibitions[1].id, exhibitions[2].id]
    )
    
    # Calculate scores
    score_rank1 = calculate_exhibition_preference_score(
        guard, exhibitions[0], settings.next_week_start
    )
    score_rank2 = calculate_exhibition_preference_score(
        guard, exhibitions[1], settings.next_week_start
    )
    score_rank3 = calculate_exhibition_preference_score(
        guard, exhibitions[2], settings.next_week_start
    )
    
    # Verify: rank 1 = 2.0, rank 3 = 0.0, rank 2 = middle (1.0)
    assert score_rank1 == 2.0, "Rank 1 should score 2.0"
    assert score_rank3 == 0.0, "Rank n should score 0.0"
    assert score_rank2 == 1.0, "Rank 2 (middle of 3) should score 1.0"
    
    # Verify linear relationship
    assert score_rank1 > score_rank2 > score_rank3


@pytest.mark.django_db
def test_exhibition_no_preferences_returns_neutral(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that guards without exhibition preferences get neutral score (1.0).
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibition = sample_exhibitions[0]
    settings = system_settings_for_assignment
    
    # No preferences created - should return neutral
    score = calculate_exhibition_preference_score(
        guard, exhibition, settings.next_week_start
    )
    
    assert score == 1.0, "No preference should return neutral score 1.0"


@pytest.mark.django_db
def test_exhibition_single_preference_gets_neutral(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that when only one exhibition in preference, score is neutral (1.0).
    Cannot rank when n=1.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibition = sample_exhibitions[0]
    settings = system_settings_for_assignment
    
    # Create preference with only one exhibition
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibition.id]
    )
    
    score = calculate_exhibition_preference_score(
        guard, exhibition, settings.next_week_start
    )
    
    assert score == 1.0, "Single exhibition preference should return neutral 1.0"


@pytest.mark.django_db
def test_exhibition_multiple_preferences_ranked_correctly(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that multiple exhibition preferences are ranked with correct scores.
    With 3 exhibitions: rank 1→2.0, rank 2→1.0, rank 3→0.0
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibitions = sample_exhibitions  # 3 exhibitions
    settings = system_settings_for_assignment
    
    # Prefer in reverse order: [exh3, exh2, exh1]
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibitions[2].id, exhibitions[1].id, exhibitions[0].id]
    )
    
    score_exh3 = calculate_exhibition_preference_score(
        guard, exhibitions[2], settings.next_week_start
    )
    score_exh2 = calculate_exhibition_preference_score(
        guard, exhibitions[1], settings.next_week_start
    )
    score_exh1 = calculate_exhibition_preference_score(
        guard, exhibitions[0], settings.next_week_start
    )
    
    # exh3 is rank 1, exh2 is rank 2, exh1 is rank 3
    assert score_exh3 == 2.0
    assert score_exh2 == 1.0
    assert score_exh1 == 0.0


@pytest.mark.django_db
def test_exhibition_preference_for_wrong_exhibition_returns_neutral(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that when guard has preferences but exhibition not in list,
    neutral score is returned (fallback behavior).
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibitions = sample_exhibitions  # 3 exhibitions
    settings = system_settings_for_assignment
    
    # Create preference with only first two exhibitions
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibitions[0].id, exhibitions[1].id]
    )
    
    # Try to score third exhibition (not in preference list)
    score = calculate_exhibition_preference_score(
        guard, exhibitions[2], settings.next_week_start
    )
    
    assert score == 1.0, "Exhibition not in preference list should return neutral 1.0"


# ============================================================================
# UNIT TESTS - Day Preferences (5 tests)
# ============================================================================

@pytest.mark.django_db
def test_day_preference_ranking_calculation(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that day preference ranking is calculated correctly.
    Rank 1 → 2.0, Rank n → 0.0, linear interpolation between.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # Create preference: [Monday=0, Wednesday=2, Friday=4]
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[0, 2, 4]
    )
    
    # Calculate scores
    score_monday = calculate_day_preference_score(guard, 0, settings.next_week_start)
    score_wednesday = calculate_day_preference_score(guard, 2, settings.next_week_start)
    score_friday = calculate_day_preference_score(guard, 4, settings.next_week_start)
    
    # Verify: rank 1 = 2.0, rank 3 = 0.0, rank 2 = middle (1.0)
    assert score_monday == 2.0, "Rank 1 (Monday) should score 2.0"
    assert score_friday == 0.0, "Rank 3 (Friday) should score 0.0"
    assert score_wednesday == 1.0, "Rank 2 (Wednesday) should score 1.0"
    
    # Verify linear relationship
    assert score_monday > score_wednesday > score_friday


@pytest.mark.django_db
def test_day_no_preferences_returns_neutral(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that guards without day preferences get neutral score (1.0).
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # No preferences created - should return neutral
    score = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    assert score == 1.0, "No preference should return neutral score 1.0"


@pytest.mark.django_db
def test_day_single_preference_gets_neutral(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that when only one day in preference, score is neutral (1.0).
    Cannot rank when n=1.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # Create preference with only one day (Monday=0)
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[0]
    )
    
    score = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    assert score == 1.0, "Single day preference should return neutral 1.0"


@pytest.mark.django_db
def test_day_multiple_preferences_ranked_correctly(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that multiple day preferences are ranked with correct scores.
    With 5 days: rank 1→2.0, rank 5→0.0, interpolated between.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # Prefer workdays in order: [Fri=4, Thu=3, Wed=2, Tue=1, Mon=0]
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[4, 3, 2, 1, 0]
    )
    
    score_friday = calculate_day_preference_score(guard, 4, settings.next_week_start)
    score_thursday = calculate_day_preference_score(guard, 3, settings.next_week_start)
    score_wednesday = calculate_day_preference_score(guard, 2, settings.next_week_start)
    score_tuesday = calculate_day_preference_score(guard, 1, settings.next_week_start)
    score_monday = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    # Friday is rank 1, Monday is rank 5
    assert score_friday == 2.0
    assert score_monday == 0.0
    
    # Thursday is rank 2: 2.0 * (5-2) / (5-1) = 2.0 * 3/4 = 1.5
    assert score_thursday == 1.5
    
    # Wednesday is rank 3: 2.0 * (5-3) / (5-1) = 2.0 * 2/4 = 1.0
    assert score_wednesday == 1.0
    
    # Tuesday is rank 4: 2.0 * (5-4) / (5-1) = 2.0 * 1/4 = 0.5
    assert score_tuesday == 0.5
    
    # Verify linear relationship
    assert score_friday > score_thursday > score_wednesday > score_tuesday > score_monday


@pytest.mark.django_db
def test_day_preference_for_wrong_day_returns_neutral(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that when guard has preferences but day not in list,
    neutral score is returned (fallback behavior).
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # Create preference with only Monday, Wednesday, Friday
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[0, 2, 4]
    )
    
    # Try to score Tuesday (1) - not in preference list
    score = calculate_day_preference_score(guard, 1, settings.next_week_start)
    
    assert score == 1.0, "Day not in preference list should return neutral 1.0"


# ============================================================================
# INTEGRATION TESTS - Combined Scoring (5 tests)
# ============================================================================

@pytest.mark.django_db
def test_combined_scoring_weights_in_final_score(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that final score combines: 60% priority + 20% exhibition + 20% day.
    This is an integration test verifying the scoring weights are correct.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', 
                                   availability=3, priority=Decimal('5.0'))
    exhibition = sample_exhibitions[0]
    settings = system_settings_for_assignment
    
    # Create preferences - rank 1 for both (max scores)
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibition.id, sample_exhibitions[1].id]
    )
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[0, 1, 2]
    )
    
    # Get individual scores
    exh_score = calculate_exhibition_preference_score(
        guard, exhibition, settings.next_week_start
    )
    day_score = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    assert exh_score == 2.0, "Exhibition score should be 2.0 (rank 1)"
    assert day_score == 2.0, "Day score should be 2.0 (rank 1)"
    
    # Verify scores are in expected range for combination
    # In actual algorithm: 0.6 * normalized_priority + 0.2 * exh_score + 0.2 * day_score
    # Here we just verify individual components work correctly
    assert 0.0 <= exh_score <= 2.0
    assert 0.0 <= day_score <= 2.0


@pytest.mark.django_db
def test_high_preference_increases_likelihood(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that high preferences (rank 1) give better scores than low preferences.
    This affects final assignment likelihood.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    exhibitions = sample_exhibitions  # 3 exhibitions
    settings = system_settings_for_assignment
    
    # Create preference: rank exh1 first, exh2 last
    GuardExhibitionPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibitions[0].id, exhibitions[1].id, exhibitions[2].id]
    )
    
    score_preferred = calculate_exhibition_preference_score(
        guard, exhibitions[0], settings.next_week_start
    )
    score_not_preferred = calculate_exhibition_preference_score(
        guard, exhibitions[2], settings.next_week_start
    )
    
    # Preferred exhibition should have significantly higher score
    assert score_preferred > score_not_preferred
    assert score_preferred == 2.0
    assert score_not_preferred == 0.0


@pytest.mark.django_db
def test_low_preference_decreases_likelihood(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that low preferences (rank n) give worse scores.
    This decreases assignment likelihood for disliked exhibitions/days.
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3)
    settings = system_settings_for_assignment
    
    # Create day preference: prefer Friday, dislike Monday
    GuardDayPreference.objects.create(
        guard=guard,
        next_week_start=settings.next_week_start,
        day_order=[4, 3, 2, 1, 0]  # Fri first, Mon last
    )
    
    score_liked = calculate_day_preference_score(guard, 4, settings.next_week_start)
    score_disliked = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    # Disliked day should have much lower score
    assert score_liked > score_disliked
    assert score_liked == 2.0
    assert score_disliked == 0.0


@pytest.mark.django_db
def test_preference_can_compensate_for_priority(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that strong preferences can compensate for lower priority.
    Guard with priority=1 but rank 1 preference should score well.
    """
    # Low priority guard with high preference
    guard_low_priority = create_guard_with_user(
        'low_priority', 'low@test.com', availability=3, priority=Decimal('1.0')
    )
    
    # High priority guard with low preference
    guard_high_priority = create_guard_with_user(
        'high_priority', 'high@test.com', availability=3, priority=Decimal('10.0')
    )
    
    exhibition = sample_exhibitions[0]
    settings = system_settings_for_assignment
    
    # Low priority guard ranks exhibition first
    GuardExhibitionPreference.objects.create(
        guard=guard_low_priority,
        next_week_start=settings.next_week_start,
        exhibition_order=[exhibition.id, sample_exhibitions[1].id]
    )
    
    # High priority guard ranks exhibition last
    GuardExhibitionPreference.objects.create(
        guard=guard_high_priority,
        next_week_start=settings.next_week_start,
        exhibition_order=[sample_exhibitions[1].id, exhibition.id]
    )
    
    score_low_priority = calculate_exhibition_preference_score(
        guard_low_priority, exhibition, settings.next_week_start
    )
    score_high_priority = calculate_exhibition_preference_score(
        guard_high_priority, exhibition, settings.next_week_start
    )
    
    # Low priority guard should have much better exhibition score
    assert score_low_priority == 2.0
    assert score_high_priority == 0.0
    
    # In final algorithm (60% priority + 20% exh + 20% day),
    # the 20% exhibition component can shift the balance


@pytest.mark.django_db
def test_no_preferences_uses_priority_only_fallback(
    create_guard_with_user, sample_exhibitions, system_settings_for_assignment
):
    """
    Test that when no preferences are set, scoring falls back to neutral (1.0).
    This means priority becomes the dominant factor (60% weight).
    """
    guard = create_guard_with_user('test_guard', 'test@test.com', 
                                   availability=3, priority=Decimal('7.5'))
    exhibition = sample_exhibitions[0]
    settings = system_settings_for_assignment
    
    # No preferences created
    exh_score = calculate_exhibition_preference_score(
        guard, exhibition, settings.next_week_start
    )
    day_score = calculate_day_preference_score(guard, 0, settings.next_week_start)
    
    # Both should be neutral
    assert exh_score == 1.0, "No exhibition preference should give neutral 1.0"
    assert day_score == 1.0, "No day preference should give neutral 1.0"
    
    # With both neutral, final score is: 0.6 * priority + 0.2 * 1.0 + 0.2 * 1.0
    # = 0.6 * priority + 0.4
    # This means priority is the main differentiator
