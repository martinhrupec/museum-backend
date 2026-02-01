"""
Automated position assignment using Hungarian algorithm.

Assigns guards to positions based on:
- Priority number (60% weight)
- Exhibition preferences (20% weight)
- Day preferences (20% weight)

Uses scipy's linear_sum_assignment for optimal matching.
"""
import structlog
import numpy as np
from scipy.optimize import linear_sum_assignment
from decimal import Decimal

logger = structlog.get_logger(__name__)


def build_score_matrix(guards, positions, settings, availability_caps):
    """
    Build score matrix for Hungarian algorithm with guard duplication.
    
    Guards are duplicated in the matrix according to their availability.
    E.g., if Guard A has availability=2, they appear as 2 rows in the matrix.
    This allows Hungarian algorithm to assign multiple positions per guard.
    
    Matrix shape: (total_slots, n_positions) where total_slots = sum of all availabilities
    Each cell contains normalized score 0-1 for guard-position pair.
    Impossible pairs get -9999 (filtered in post-processing).
    
    Args:
        guards: List of Guard instances (with availability > 0)
        positions: List of Position instances for next_week
        settings: SystemSettings instance
        availability_caps: Dict {guard_id: capped_availability} or empty dict
    
    Returns:
        tuple: (score_matrix, row_to_guard_map, guard_work_periods_map, guard_positions_map)
        - score_matrix: numpy array (total_slots, n_positions)
        - row_to_guard_map: list mapping row index to Guard instance
        - guard_work_periods_map: dict {guard_id: [(day, shift), ...]}
        - guard_positions_map: dict {guard_id: [position_ids]}
    """
    from api.utils.preference_scoring import (
        calculate_exhibition_preference_score,
        calculate_day_preference_score
    )
    from api.utils.guard_periods import get_guard_work_periods, get_positions_for_guard
    
    n_positions = len(positions)
    
    # Calculate total slots (sum of all availabilities, respecting caps)
    total_slots = sum(
        availability_caps.get(g.id, g.availability) 
        for g in guards
    )
    
    logger.info(
        f"Building score matrix: {len(guards)} guards with {total_slots} total slots "
        f"x {n_positions} positions"
    )
    
    # Initialize matrix and row mapping
    score_matrix = np.zeros((total_slots, n_positions))
    row_to_guard_map = []  # Maps row index → Guard instance
    
    # Pre-calculate guard work periods and valid positions
    guard_work_periods_map = {}
    guard_positions_map = {}
    
    for guard in guards:
        work_periods = get_guard_work_periods(
            guard,
            settings.next_week_start,
            settings.next_week_end
        )
        guard_work_periods_map[guard.id] = work_periods
        
        valid_positions = get_positions_for_guard(positions, work_periods)
        guard_positions_map[guard.id] = [p.id for p in valid_positions]
        
        logger.debug(
            f"Guard {guard.user.username}: "
            f"{len(work_periods)} periods, {len(valid_positions)} valid positions"
        )
    
    # Min-max normalize priorities to 0-1 range
    priorities = [g.priority_number for g in guards]
    min_priority = min(priorities)
    max_priority = max(priorities)
    priority_range = max_priority - min_priority
    
    if priority_range == 0:
        # All guards have same priority - set all to 0.5
        logger.info("All guards have same priority - using 0.5 for all")
        priority_normalized = {g.id: 0.5 for g in guards}
    else:
        # Min-max normalization: (value - min) / (max - min)
        priority_normalized = {
            g.id: float((g.priority_number - min_priority) / priority_range)
            for g in guards
        }
    
    logger.info(
        f"Priority range: [{min_priority:.2f}, {max_priority:.2f}], "
        f"normalized to [0.0, 1.0]"
    )
    
    # Build matrix: duplicate each guard according to capped availability
    current_row = 0
    for guard in guards:
        guard_availability = availability_caps.get(guard.id, guard.availability)
        priority_norm = priority_normalized[guard.id]
        valid_position_ids = guard_positions_map[guard.id]
        
        # Create N rows for this guard (N = capped availability from caps dict)
        for slot in range(guard_availability):
            row_to_guard_map.append(guard)
            
            for j, position in enumerate(positions):
                if position.id not in valid_position_ids:
                    # Guard cannot work this position
                    score_matrix[current_row, j] = -9999
                    continue
                
                # Calculate components
                # 1. Priority (min-max normalized → 0-1)
                # Already normalized above
                
                # 2. Exhibition preference (0-2 → 0-1)
                exhibition_score = calculate_exhibition_preference_score(
                    guard,
                    position.exhibition,
                    settings.next_week_start
                )
                exhibition_norm = exhibition_score / 2.0
                
                # 3. Day preference (0-2 → 0-1)
                day_score = calculate_day_preference_score(
                    guard,
                    position.date.weekday(),
                    settings.next_week_start
                )
                day_norm = day_score / 2.0
                
                # Weighted sum: 60% priority, 20% exhibition, 20% day
                final_score = (
                    0.6 * priority_norm +
                    0.2 * exhibition_norm +
                    0.2 * day_norm
                )
                
                score_matrix[current_row, j] = final_score
            
            current_row += 1
    
    logger.info(f"Score matrix built: {total_slots} slots x {n_positions} positions")
    
    return score_matrix, row_to_guard_map, guard_work_periods_map, guard_positions_map


def assign_positions_automatically(settings, availability_caps=None):
    """
    Main automated assignment function using Hungarian algorithm.
    
    Steps:
    1. Get guards with availability > 0
    2. Apply availability caps if provided (demand > supply)
    3. Get all positions for next_week
    4. Build score matrix
    5. Run Hungarian algorithm (maximize)
    6. Post-process: remove impossible assignments (-9999) and respect caps
    7. Create PositionHistory records (ASSIGNED action)
    
    Args:
        settings: SystemSettings instance
        availability_caps: dict {guard_id: capped_availability} or None
    
    Returns:
        dict: Assignment results summary
    """
    from background_tasks.tasks import get_guards_with_availability_updated
    from api.api_models.schedule import Position, PositionHistory
    
    if availability_caps is None:
        availability_caps = {}
    
    logger.info("=" * 60)
    logger.info("Starting automated position assignment")
    logger.info("=" * 60)
    
    # Get guards with availability
    guards = list(get_guards_with_availability_updated())
    
    if not guards:
        logger.warning("No guards with availability set - skipping assignment")
        return {'status': 'skipped', 'reason': 'no_guards'}
    
    # Get positions for next_week (exclude special events - they are manually assigned)
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end,
        exhibition__is_special_event=False  # Exclude special events from automated assignment
    ).select_related('exhibition').order_by('date', 'start_time'))
    
    if not positions:
        logger.warning("No positions for next_week - skipping assignment")
        return {'status': 'skipped', 'reason': 'no_positions'}
    
    logger.info(f"Assignment pool: {len(guards)} guards, {len(positions)} positions")
    
    # Build score matrix (with guard duplication by availability)
    score_matrix, row_to_guard_map, guard_work_periods_map, guard_positions_map = build_score_matrix(
        guards,
        positions,
        settings,
        availability_caps
    )
    
    # Run Hungarian algorithm (maximize=True)
    row_indices, position_indices = linear_sum_assignment(score_matrix, maximize=True)
    
    logger.info(f"Hungarian algorithm completed: {len(row_indices)} assignments proposed")
    
    # Post-process: filter out impossible assignments
    valid_assignments = []
    filtered_count = 0
    
    for row_idx, position_idx in zip(row_indices, position_indices):
        score = score_matrix[row_idx, position_idx]
        
        if score == -9999:
            # Impossible assignment - skip
            filtered_count += 1
            guard = row_to_guard_map[row_idx]
            logger.debug(
                f"Filtered impossible assignment: "
                f"{guard.user.username} → Position #{positions[position_idx].id}"
            )
            continue
        
        guard = row_to_guard_map[row_idx]
        valid_assignments.append({
            'guard': guard,
            'position': positions[position_idx],
            'score': score
        })
    
    logger.info(
        f"After filtering: {len(valid_assignments)} valid assignments "
        f"({filtered_count} impossible filtered)"
    )
    
    # Check for underutilization warning
    total_slots = len(row_to_guard_map)
    if filtered_count > 0:
        utilization_rate = (len(valid_assignments) / total_slots) * 100
        logger.warning(
            f"Slot underutilization detected: {len(valid_assignments)}/{total_slots} slots used "
            f"({utilization_rate:.1f}%). This may indicate guards' work_periods are too restrictive "
            f"or don't match available positions."
        )
    
    # Create PositionHistory records directly (no need for cap enforcement - already in matrix)
    created_count = 0
    guard_assignment_counts = {}  # Track how many positions each guard got
    
    for assignment in valid_assignments:
        guard = assignment['guard']
        position = assignment['position']
        score = assignment['score']
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Track assignments per guard
        guard_assignment_counts[guard.id] = guard_assignment_counts.get(guard.id, 0) + 1
        
        created_count += 1
        logger.debug(
            f"Assigned {guard.user.username} → "
            f"{position.exhibition.name} ({position.date}, {position.start_time}) "
            f"[score: {score:.3f}]"
        )
    
    # Check if any guard was capped
    capping_occurred = bool(availability_caps) and any(
        availability_caps.get(g.id, g.availability) < g.availability
        for g in guards
    )
    
    logger.info("=" * 60)
    logger.info(f"Assignment complete: {created_count} positions assigned")
    logger.info("=" * 60)
    
    return {
        'status': 'success',
        'total_guards': len(guards),
        'total_positions': len(positions),
        'total_slots': len(row_to_guard_map),
        'assignments_proposed': len(row_indices),
        'assignments_filtered': filtered_count,
        'assignments_created': created_count,
        'positions_remaining': len(positions) - created_count,
        'capping_occurred': capping_occurred,
        'guard_assignments': guard_assignment_counts  # {guard_id: assigned_count}
    }
