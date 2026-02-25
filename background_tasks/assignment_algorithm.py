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
from collections import defaultdict

logger = structlog.get_logger(__name__)


def positions_overlap(pos1, pos2):
    """
    Check if two positions overlap in time.
    
    Positions overlap if they are on the same day AND their time ranges intersect.
    Time ranges intersect if: start1 < end2 AND start2 < end1
    
    Args:
        pos1: Position instance
        pos2: Position instance
    
    Returns:
        bool: True if positions overlap
    """
    if pos1.date != pos2.date:
        return False
    
    return pos1.start_time < pos2.end_time and pos2.start_time < pos1.end_time


def build_overlap_groups(positions):
    """
    Group positions that overlap in time.
    
    Returns a dict mapping each position index to a set of overlapping position indices.
    Used to ensure a guard's row slots can only be assigned to non-overlapping positions.
    
    Args:
        positions: List of Position instances
    
    Returns:
        dict: {position_index: set of overlapping position indices}
    """
    n = len(positions)
    overlap_map = defaultdict(set)
    
    for i in range(n):
        for j in range(i + 1, n):
            if positions_overlap(positions[i], positions[j]):
                overlap_map[i].add(j)
                overlap_map[j].add(i)
    
    return overlap_map


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
    # Each slot of the guard can potentially work ANY valid position
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
                    # Guard cannot work this position (not in their work periods)
                    score_matrix[current_row, j] = -9999
                    continue
                
                # Calculate components
                # 1. Priority (min-max normalized → 0-1)
                
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


def filter_overlapping_assignments(assignments, positions):
    """
    Filter overlapping assignments per guard, keeping highest score.
    
    Returns:
        tuple: (valid_assignments, freed_position_indices)
        - valid_assignments: list of non-overlapping assignments
        - freed_position_indices: set of position indices that were filtered out
    """
    guard_assignments = defaultdict(list)
    for a in assignments:
        guard_assignments[a['guard'].id].append(a)
    
    valid_assignments = []
    freed_position_indices = set()
    
    for guard_id, assigns in guard_assignments.items():
        if len(assigns) == 1:
            valid_assignments.append(assigns[0])
            continue
        
        # Sort by score descending (highest first)
        assigns.sort(key=lambda x: x['score'], reverse=True)
        
        # Keep non-overlapping positions (greedy by score)
        kept = []
        for a in assigns:
            pos = a['position']
            overlap_found = False
            for kept_a in kept:
                kept_pos = kept_a['position']
                if positions_overlap(pos, kept_pos):
                    overlap_found = True
                    freed_position_indices.add(a['pos_idx'])
                    logger.debug(
                        f"Filtered overlap: {a['guard'].user.username} - "
                        f"{pos.exhibition.name} ({pos.date} {pos.start_time}) "
                        f"conflicts with {kept_pos.exhibition.name}"
                    )
                    break
            
            if not overlap_found:
                kept.append(a)
        
        valid_assignments.extend(kept)
    
    return valid_assignments, freed_position_indices


def assign_positions_automatically(settings, availability_caps=None):
    """
    Main automated assignment function using Hungarian algorithm.
    
    Uses iterative approach to handle overlapping positions:
    1. Get guards with availability > 0
    2. Apply availability caps if provided (demand > supply)
    3. Get all positions for next_week
    4. Build score matrix
    5. Run Hungarian algorithm (maximize)
    6. Post-process: remove impossible assignments (-9999)
    7. Filter overlapping assignments per guard (keep highest scores)
    8. For freed positions, re-run with remaining guard slots
    9. Repeat until no more improvements
    10. Create PositionHistory records (ASSIGNED action)
    
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
    
    # Track final assignments and slot usage per guard
    final_assignments = []
    assigned_position_indices = set()  # Positions already assigned
    guard_slots_used = defaultdict(int)  # {guard_id: slots_used}
    
    # Track assigned positions per guard to check overlaps
    guard_assigned_positions = defaultdict(list)  # {guard_id: [position objects]}
    
    iteration = 0
    max_iterations = 10  # Safety limit
    initial_total_slots = sum(
        availability_caps.get(g.id, g.availability) 
        for g in guards
    )
    
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"--- Iteration {iteration} ---")
        
        # Calculate remaining availability for each guard
        remaining_caps = {}
        available_guards = []
        for g in guards:
            cap = availability_caps.get(g.id, g.availability)
            remaining = cap - guard_slots_used[g.id]
            if remaining > 0:
                remaining_caps[g.id] = remaining
                available_guards.append(g)
        
        if not available_guards:
            logger.info("No guards with remaining availability - stopping")
            break
        
        # Build score matrix with remaining guards and positions
        # Mask already-assigned positions
        score_matrix, row_to_guard_map, _, _ = build_score_matrix(
            available_guards,
            positions,
            settings,
            remaining_caps
        )
        
        # Mask already-assigned positions
        for pos_idx in assigned_position_indices:
            score_matrix[:, pos_idx] = -9999
        
        # Additionally, mask positions that would overlap with already-assigned positions
        # for each guard
        for row_idx, guard in enumerate(row_to_guard_map):
            for pos_idx, position in enumerate(positions):
                if score_matrix[row_idx, pos_idx] == -9999:
                    continue  # Already masked
                
                # Check if this position overlaps with any already-assigned position
                # for this guard
                for assigned_pos in guard_assigned_positions[guard.id]:
                    if positions_overlap(position, assigned_pos):
                        score_matrix[row_idx, pos_idx] = -9999
                        break
        
        # Check if any valid scores remain
        valid_count = np.sum(score_matrix != -9999)
        if valid_count == 0:
            logger.info("No valid assignments remaining - stopping")
            break
        
        # Run Hungarian algorithm
        row_indices, position_indices = linear_sum_assignment(score_matrix, maximize=True)
        
        # Collect valid assignments from this iteration
        iteration_assignments = []
        
        for row_idx, position_idx in zip(row_indices, position_indices):
            score = score_matrix[row_idx, position_idx]
            
            if score == -9999:
                continue
            
            guard = row_to_guard_map[row_idx]
            iteration_assignments.append({
                'guard': guard,
                'position': positions[position_idx],
                'pos_idx': position_idx,
                'score': score
            })
        
        if not iteration_assignments:
            logger.info("No valid assignments in this iteration - stopping")
            break
        
        # Filter overlapping assignments (within this iteration's assignments)
        valid_iter_assignments, freed = filter_overlapping_assignments(
            iteration_assignments, 
            positions
        )
        
        if freed:
            logger.info(f"Filtered {len(freed)} overlapping positions in iteration {iteration}")
        
        # Add to final assignments
        new_assignments_count = 0
        for a in valid_iter_assignments:
            guard = a['guard']
            position = a['position']
            pos_idx = a['pos_idx']
            
            # Final check: ensure this doesn't overlap with guard's existing assignments
            has_overlap = False
            for existing_pos in guard_assigned_positions[guard.id]:
                if positions_overlap(position, existing_pos):
                    has_overlap = True
                    logger.debug(
                        f"Final overlap check: {guard.user.username} cannot take "
                        f"{position.exhibition.name} - conflicts with {existing_pos.exhibition.name}"
                    )
                    break
            
            if has_overlap:
                continue
            
            final_assignments.append(a)
            assigned_position_indices.add(pos_idx)
            guard_slots_used[guard.id] += 1
            guard_assigned_positions[guard.id].append(position)
            new_assignments_count += 1
        
        logger.info(f"Iteration {iteration}: {new_assignments_count} new assignments")
        
        if new_assignments_count == 0:
            logger.info("No new assignments made - stopping")
            break
    
    logger.info(f"Completed after {iteration} iterations")
    logger.info(
        f"After filtering: {len(final_assignments)} valid assignments"
    )
    
    # Check for underutilization warning
    if len(final_assignments) < initial_total_slots:
        utilization_rate = (len(final_assignments) / initial_total_slots) * 100
        logger.info(
            f"Slot utilization: {len(final_assignments)}/{initial_total_slots} slots used "
            f"({utilization_rate:.1f}%)."
        )
    
    # Create PositionHistory records
    created_count = 0
    guard_assignment_counts = {}  # Track how many positions each guard got
    
    for assignment in final_assignments:
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
        'total_slots': initial_total_slots,
        'iterations': iteration,
        'assignments_created': created_count,
        'positions_remaining': len(positions) - created_count,
        'capping_occurred': capping_occurred,
        'guard_assignments': guard_assignment_counts  # {guard_id: assigned_count}
    }
