# 🎯 Assignment Algorithm Tests - Master Plan

**Comprehensive testing suite for automated position assignment - the heart of the project.**

## 📋 Testing Strategy

Assignment algoritam se sastoji od **5 glavnih komponenti** koje testiramo odvojeno i integrisano:

### Core Components

1. **Preference Scoring** - Calculates preference-based scores for assignments
2. **Guard Work Periods** - Position filtering based on guard availability
3. **Score Matrix Builder** - Constructs cost matrix for Hungarian algorithm
4. **Hungarian Algorithm Integration** (`scipy.optimize.linear_sum_assignment`) - Optimal matching
5. **Minimum Calculator** (`background_tasks/minimum_calculator.py`) - Dynamic minimum calculation

### Realistic Test Data

Tests use realistic museum data to match production:

- **Guards**: 10-50 (average ~30)
- **Exhibitions**: 2-7 (average ~3)
- **Positions per shift**: 1-4 (average ~1.5)
- **Workdays**: Tuesday-Sunday (6 days = 12 shifts/week)
- **Total weekly positions**: ~18-36 typically

---

## 🗂️ TEST STRUCTURE - 9 Faza

### ✅ FAZA 1: Basic Assignment Tests

**File**: `test_basic_assignment.py`  
**Status**: ✅ 5/5 testova passing

1. `test_simple_assignment_with_sufficient_guards` - More guards than positions
2. `test_assignment_with_exact_match` - Guards availability matches positions
3. `test_assignment_respects_guard_availability` - Guards not over-assigned
4. `test_no_guards_available_returns_empty_result` - No guards handling
5. `test_guards_without_availability_set_are_skipped` - None availability skipped

---

### ✅ FAZA 2: Preference Scoring Tests

**File**: `test_preference_scoring.py`  
**Status**: ✅ 15/15 testova passing

**Exhibition Preferences (5 testova):**

1. `test_exhibition_preference_ranking_calculation` - Rank scoring
2. `test_exhibition_no_preferences_returns_neutral` - No preferences → neutral
3. `test_exhibition_single_preference_gets_neutral` - Single preference handling
4. `test_exhibition_multiple_preferences_ranked_correctly` - Multiple ranked preferences
5. `test_exhibition_preference_for_wrong_exhibition_returns_neutral` - Wrong exhibition → neutral

**Day Preferences (5 testova):** 6. `test_day_preference_ranking_calculation` - Day rank scoring 7. `test_day_no_preferences_returns_neutral` - No day preferences 8. `test_day_single_preference_gets_neutral` - Single day preference 9. `test_day_multiple_preferences_ranked_correctly` - Multiple days ranked 10. `test_day_preference_for_wrong_day_returns_neutral` - Wrong day → neutral

**Integration (5 testova):** 11. `test_combined_scoring_weights_in_final_score` - 60/20/20 weights 12. `test_high_preference_increases_likelihood` - High preference impact 13. `test_low_preference_decreases_likelihood` - Low preference impact 14. `test_preference_can_compensate_for_priority` - Preferences vs priority 15. `test_no_preferences_uses_priority_only_fallback` - Priority-only fallback

---

### ✅ FAZA 3: Guard Work Periods Tests

**File**: `test_guard_work_periods.py`  
**Status**: ✅ 12/12 testova passing

**Period Retrieval (4 testa):**

1. `test_get_template_work_periods` - Template periods retrieved
2. `test_get_specific_week_work_periods` - Specific week overrides template
3. `test_no_work_periods_returns_empty_list` - No periods → empty list
4. `test_work_period_date_matching` - Periods match dates correctly

**Position Filtering (4 testa):** 5. `test_positions_filtered_by_work_periods` - Only matching positions returned 6. `test_no_work_periods_returns_no_positions` - No periods → no positions 7. `test_partial_day_coverage` - Morning only → morning positions 8. `test_shift_time_matching` - Weekend vs weekday shifts

**Integration (4 testa):** 9. `test_guard_only_assigned_to_work_period_positions` - End-to-end check 10. `test_multiple_guards_different_periods` - Multiple guards no conflicts 11. `test_work_period_changes_affect_assignment` - Template vs specific changes 12. `test_overlapping_work_periods_multiple_guards` - Competition for slots

---

### ✅ FAZA 4: Score Matrix Builder Tests

**File**: `test_score_matrix.py`  
**Status**: ✅ 18/18 testova passing

**Matrix Structure (5 testova):**

1. `test_matrix_dimensions_match_guards_and_positions` - Rows = sum(availabilities)
2. `test_guard_duplication_based_on_availability` - Guard appears availability times
3. `test_score_normalization_range` - Scores in valid range
4. `test_matrix_is_numpy_array` - Matrix is numpy array
5. `test_guard_duplicated_exactly_availability_times` - Exact duplication count

**Priority Normalization (4 testa):** 6. `test_priority_values_normalized_correctly` - Min-max normalization 7. `test_guards_same_priority_get_same_normalized_value` - Same priority → same value 8. `test_priority_weight_is_60_percent` - 60% weight for priority 9. `test_single_guard_priority_normalization` - Single guard → 0.5

**Score Calculation (5 testova):** 10. `test_combined_score_calculation` - Full score composition 11. `test_score_weights_distribution` - 0.6×priority + 0.2×exh + 0.2×day 12. `test_score_range_validation` - Scores between 0 and 1 13. `test_guards_no_preferences_get_baseline_scores` - No preferences baseline 14. `test_high_preference_guards_get_higher_scores` - High preference → higher score

**Integration (4 testa):** 15. `test_score_matrix_matches_position_order` - Matrix columns match positions 16. `test_each_duplicate_has_same_scores` - Duplicates have identical scores 17. `test_duplicates_appear_consecutively` - Duplicates are consecutive 18. `test_availability_zero_means_no_entries` - Zero availability → no rows

---

### ✅ FAZA 5: Hungarian Algorithm Integration Tests

**File**: `test_hungarian_integration.py`  
**Status**: ✅ 10/10 testova passing

1. `test_hungarian_algorithm_executes_successfully` - Algorithm runs without errors
2. `test_optimal_assignment_respects_scores` - Higher scores get better assignments
3. `test_hungarian_handles_more_guards_than_positions` - Rectangular matrix handling
4. `test_assignment_records_created_correctly` - PositionHistory created
5. `test_impossible_assignments_filtered_out` - No assignments outside work periods
6. `test_no_duplicate_position_assignments` - Each position assigned once
7. `test_guard_availability_respected` - Guards not over-assigned
8. `test_no_guards_returns_gracefully` - No guards handling
9. `test_no_positions_returns_gracefully` - No positions handling
10. `test_all_guards_unavailable_for_all_positions` - All impossible assignments

---

### ✅ FAZA 6: Availability Capping Tests

**File**: `test_availability_capping.py`  
**Status**: ✅ 12/12 testova passing

**Cap Calculation (4 testa):**

1. `test_no_capping_when_supply_meets_demand` - No caps when supply ≥ demand
2. `test_proportional_capping_formula` - Proportional capping formula
3. `test_priority_weighted_capping` - Higher priority → higher cap
4. `test_capping_respects_minimum` - Cap ≥ 1 if availability > 0

**Integration (8 testova):** 5. `test_capping_reduces_guard_slots_in_matrix` - Fewer rows for capped guards 6. `test_all_guards_capped_equally_when_same_priority` - Equal caps for same priority 7. `test_high_priority_guard_gets_higher_cap` - Priority advantage visible 8. `test_capped_guard_cannot_exceed_cap` - Hard cap enforced 9. `test_capping_with_work_periods` - Caps work with work periods 10. `test_capping_recalculated_on_guard_addition` - Dynamic recalculation 11. `test_partial_capping_scenario` - Only some guards capped 12. `test_extreme_shortage_scenario` - Extreme demand > supply

---

### ✅ FAZA 7: Minimum Calculator Tests

**File**: `test_minimum_calculator.py`  
**Status**: ✅ 9/9 testova passing

1. `test_minimum_calculated_after_full_assignment` - Minimum calculated correctly
2. `test_minimum_with_many_empty_positions_and_few_guards` - Few guards scenario
3. `test_minimum_iterative_raising_logic` - Iterative raising algorithm
4. `test_minimum_never_exceeds_total_positions` - Minimum ≤ total positions
5. `test_minimum_updates_system_settings` - SystemSettings updated
6. `test_minimum_calculation_with_no_assignments` - No assignments handling
7. `test_minimum_with_partial_assignment_coverage` - Partial coverage
8. `test_minimum_with_special_event_positions` - Special events excluded
9. `test_minimum_calculation_idempotent` - Multiple calls same result

---

### ✅ FAZA 8: Edge Cases & Error Handling Tests

**File**: `test_edge_cases.py`  
**Status**: ✅ 15/15 testova passing

**Boundary Conditions (10 testova):**

1. `test_zero_positions_available` - No positions → no assignments
2. `test_one_guard_one_position` - Minimal scenario
3. `test_more_guards_than_positions` - Excess guards handled
4. `test_more_positions_than_total_availability` - Shortage handled
5. `test_all_guards_same_priority` - Tie-breaking behavior
6. `test_guard_with_availability_zero_skipped` - Zero availability skipped
7. `test_guard_with_availability_one` - Single position assignment
8. `test_guard_with_high_availability` - High availability handled
9. `test_all_positions_outside_work_periods` - No valid assignments
10. `test_guard_without_work_periods_gets_all_shifts` - No periods → all shifts

**Special Scenarios (5 testova):** 11. `test_running_assignment_twice_creates_duplicate_history` - Multiple runs handled 12. `test_special_event_excluded_from_automated_assignment` - Special events excluded 13. `test_exhibition_with_inconsistent_open_days` - Inconsistent schedules 14. `test_guard_with_preferences_for_nonexistent_exhibition` - Invalid preferences handled 15. `test_empty_score_matrix_scenario` - Empty matrix handled gracefully

---

### ⏳ FAZA 9: Full Integration & E2E Tests

**File**: `test_full_integration.py`  
**Status**: ⏳ 0/12 testova TODO

**Integration Tests (8 testova):**

1. `test_complete_assignment_workflow` - Full workflow end-to-end
2. `test_assignment_with_all_features_enabled` - All features together
3. `test_assignment_creates_history_records` - PositionHistory tracking
4. `test_assignment_with_pre_existing_assignments` - Already-assigned positions
5. `test_assignment_fairness_check` - Fair distribution verification
6. `test_assignment_logs_correctly` - Logging verification
7. `test_realistic_museum_scenario` - Real-world museum simulation
8. `test_assignment_consistency_across_runs` - Consistency check

**E2E Tests (4 testa):** 9. `test_weekly_assignment_cycle_simulation` - Multi-week simulation 10. `test_stress_test_large_dataset` - Large dataset performance 11. `test_assignment_with_varied_preferences` - Complex preferences 12. `test_performance_benchmark` - Performance benchmarking

---

## 📊 SUMMARY

| Faza       | File                            | Testova         | Status      |
| ---------- | ------------------------------- | --------------- | ----------- |
| 1          | `test_basic_assignment.py`      | 5               | ✅ PASSING  |
| 2          | `test_preference_scoring.py`    | 15              | ✅ PASSING  |
| 3          | `test_guard_work_periods.py`    | 12              | ✅ PASSING  |
| 4          | `test_score_matrix.py`          | 18              | ✅ PASSING  |
| 5          | `test_hungarian_integration.py` | 10              | ✅ PASSING  |
| 6          | `test_availability_capping.py`  | 12              | ✅ PASSING  |
| 7          | `test_minimum_calculator.py`    | 9               | ✅ PASSING  |
| 8          | `test_edge_cases.py`            | 15              | 🔄 REFACTOR |
| 9          | `test_full_integration.py`      | 12              | ⏳ TODO     |
| **UKUPNO** | **9 fajlova**                   | **108 testova** | **81/108**  |

**Note**: Tests have been updated with realistic museum data (10-50 guards avg ~30, 2-7 exhibitions avg ~3, 1-4 positions/shift, tuesday-sunday workdays).

## 🚀 EXECUTION PLAN

### Pristup implementaciji:

1. **Jedna faza po promtu** - Fokus na kvalitet, ne brzinu
2. **Red izvršavanja**: Faza 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
3. | **Svaka faza**: Kompletna implementacija + verifikacij | Status                          |
   | ------------------------------------------------------ | ------------------------------- | ------- | ---------- |
   | 1                                                      | `test_basic_assignment.py`      | 5       | ✅ PASSING |
   | 2                                                      | `test_preference_scoring.py`    | 15      | ✅ PASSING |
   | 3                                                      | `test_guard_work_periods.py`    | 12      | ✅ PASSING |
   | 4                                                      | `test_score_matrix.py`          | 18      | ✅ PASSING |
   | 5                                                      | `test_hungarian_integration.py` | 10      | ✅ PASSING |
   | 6                                                      | `test_availability_capping.py`  | 12      | ✅ PASSING |
   | 7                                                      | `test_minimum_calculator.py`    | 9       | ✅ PASSING |
   | 8                                                      | `test_edge_cases.py`            | 15      | ✅ PASSING |
   | 9                                                      | `test_full_integration.py`      | 12      | ⏳ TODO    |
   | **UKUPNO**                                             | **9 fajlova**                   | **108** | **96/108** |

**Note**: Tests use realistic museum data (10-50 guards avg ~30, 2-7 exhibitions avg ~3, 1-4 positions/shift, tuesday-sunday workdays).

---

## 🚀 NEXT STEPS

### FAZA 9: Full Integration & E2E Tests

Create `test_full_integration.py` with 12 comprehensive tests covering:

- Complete workflow validation
- Multi-week scenarios
- Large dataset performance
- Real-world museum simulations
- Consistency and fairness checks

When ready, say **"Kreni sa Fazom 9"** to begin final testing phase 6. Filter impossible assignments (-9999) 7. Create PositionHistory records 8. Update minimum positions per guard

````

The assignment system uses the **Hungarian algorithm** (linear_sum_assignment from scipy) to optimally match guards to positions based on a weighted scoring system.

### Core Components

1. **Assignment Algorithm** (`background_tasks/assignment_algorithm.py`)
   - `build_score_matrix()` - Builds weighted score matrix with guard duplication
   - `assign_positions_automatically()` - Main assignment orchestrator

2. **Minimum Calculator** (`background_tasks/minimum_calculator.py`)
   - `calculate_and_update_minimum()` - Dynamically calculates minimum positions per guard

3. **Supporting Utilities**
   - `api/utils/guard_periods.py` - Work period matching logic
   - `api/utils/preference_scoring.py` - Exhibition and day preference scoring
   - `background_tasks/tasks.py` - Task orchestration

### Scoring System (0-1 normalized range)

**Final Score = 0.6 × Priority + 0.2 × Exhibition Preference + 0.2 × Day Preference**

- **Priority (60% weight)**: Min-max normalized from priority_number (based on points history)
- **Exhibition Preference (20% weight)**: Ranked preferences (rank 1 → 2.0, rank n → 0.0) / 2.0
- **Day Preference (20% weight)**: Ranked preferences (rank 1 → 2.0, rank n → 0.0) / 2.0

### Key Features

- **Guard Duplication**: Guards appear multiple times in matrix based on availability
- **Work Period Filtering**: Guards only matched to positions in their configured work periods
- **Availability Capping**: When demand > supply, guard availability is proportionally reduced
- **Impossible Assignments**: Marked with -9999 and filtered post-assignment
- **Dynamic Minimum**: Calculated based on actual empty positions after assignment

## Test Files Overview

### ✅ test_basic_assignment.py (10 tests)

Basic assignment scenarios and fundamental functionality:

- Single guard/single position matching
- Multiple guards/multiple positions
- Priority-based assignment ordering
- Empty data handling (no guards, no positions)
- Same priority distribution

### ✅ test_score_matrix.py (12 tests)

Score matrix construction and validation:

- Matrix shape verification with guard duplication
- Impossible assignments marked as -9999
- Priority normalization (min-max scaling)
- Exhibition preference scoring
- Day preference scoring
- Weighted final score calculation (60/20/20)
- Guard duplication verification

### ✅ test_work_periods_and_capping.py (12 tests)

Work period filtering and availability capping:

- Specific week work periods override template
- Template work periods application
- Fallback to all shifts when no periods
- No matching positions scenario
- Multiple guards with different work periods
- Capping when demand exceeds supply
- Proportional capping distribution
- No capping when supply meets demand
- Capping respected in assignments

### ✅ test_preference_integration.py (12 tests)

Preference scoring integration:

- Exhibition preferences favoring specific exhibitions
- Day preferences favoring specific days
- Multiple ranked preferences scoring
- Combined exhibition + day preferences
- Preference impact on score calculation
- Same priority with different preferences
- Weighted scoring formula validation

### ✅ test_edge_cases.py (15 tests)

Edge cases and boundary conditions:

- No positions to assign
- No available guards (0 availability)
- All positions already assigned
- Special event positions excluded
- Mixed special and regular positions
- Manual assignment preservation
- Single guard/single position
- Max priority (5.0) and min priority (1.0)
- Very high availability guards
- Impossible score matrices
- Conflicting constraints
- Duplicate prevention

### ✅ test_minimum_calculator.py (15 tests)

Minimum calculation algorithm:

- Basic minimum calculation
- Minimum respects availability limits
- Iterative raising algorithm
- Few positions scenario
- Many positions scenario
- No positions edge case
- Single guard calculation
- Zero availability handling
- Total minimum doesn't exceed positions
- Persistence to database
- Updates on recalculation
- Priority independence
- Proportional to availability
- Floor rounding logic
- Uneven distribution handling

### ✅ test_hungarian_integration.py (15 tests)

Hungarian algorithm integration:

- Optimal assignment finding
- Total score maximization
- Impossible assignments filtering
- Rectangular matrix handling
- Deterministic output
- Guard duplication in matrix
- Matrix shape calculation
- Normalized score ranges
- High priority guards favored
- Preferences influence assignment
- Work periods respected
- Balanced assignment distribution
- Performance characteristics
- Large matrix handling
- Memory efficiency

### ✅ test_post_processing.py (14 tests)

Post-processing and result tracking:

- Impossible assignments filtered out
- No duplicate position assignments
- Guard availability limits respected
- PositionHistory creation for all assignments
- Correct action type (ASSIGNED)
- Guard-position linking
- Timestamps on history records
- Position.guard field updates
- Unassigned positions remain null
- Position.guard matches history
- Result tracking (assignments_created, positions_filled, etc.)
- Status reporting (success/warning/error)
- Capping occurred flag
- Partial assignment handling
- Transaction rollback on error

### ✅ test_full_integration.py (10 tests)

End-to-end integration tests:

- Complete weekly assignment workflow
- Realistic museum scenario (10 guards, 5 exhibitions, 50 positions)
- Multiple assignment cycles
- Reassignment handling
- Adding guards mid-season
- Removing positions
- Overlapping preferences and priorities
- Mixed work periods and preferences
- System robustness and recovery
- Large-scale performance (20 guards, 10 exhibitions, 100 positions)

## Running the Tests

```bash
# Run all assignment algorithm tests
pytest api/tests/0assignment_algorithm_tests/ -v

# Run specific test file
pytest api/Tests

```bash
# Run all assignment algorithm tests
pytest api/tests/0assignment_algorithm_tests/ -v

# Run specific test file
pytest api/tests/0assignment_algorithm_tests/test_basic_assignment.py -v

# Run with coverage
pytest api/tests/0assignment_algorithm_tests/ --cov=background_tasks --cov-report=html

# Run FAZA 9 when ready
pytest api/tests/0assignment_algorithm_tests/test_full_integration.py -v
````
