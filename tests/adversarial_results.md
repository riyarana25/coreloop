# Test results (actually run)

Command: `python -m pytest -v` on the final tree. Result lines are copied from that run.

## tests/test_adversarial.py: 31/31 passed

- PASS `test_A1_latent_draws_cannot_change_any_assessment`
- PASS `test_A2_observe_hides_everything_after_t`
- PASS `test_B1_ship_by_boundary`
- PASS `test_B2_window_shorter_than_transit_is_lost_immediately`
- PASS `test_B3_credit_exactly_at_entitlement_and_within_tolerance`
- PASS `test_B4_credit_larger_than_entitlement_is_not_a_dispute`
- PASS `test_B5_dispute_window_closing_exactly`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw0]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw1]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw2]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw3]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw4]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw5]`
- PASS `test_C1_bad_records_never_crash_and_never_become_disputes[kw6]`
- PASS `test_C2_extreme_outlier_in_history_cannot_make_us_wait_past_the_deadline`
- PASS `test_C3_history_of_only_instant_posting_does_not_flag_inside_grace`
- PASS `test_C4_thin_history_waits_instead_of_guessing_when_safe`
- PASS `test_C5_materiality_boundary`
- PASS `test_C6_zero_credit_good_condition_is_disputed_but_damaged_is_reviewed`
- PASS `test_D1_planned_days_are_business_days_and_meet_deadlines`
- PASS `test_D2_empty_ledger_plans_nothing`
- PASS `test_D3_waiting_longer_never_saves_cores`
- PASS `test_D4_late_reship_forfeits_and_on_time_reship_recovers`
- PASS `test_D5_freight_is_never_negative_and_capacity_overflow_adds_a_load`
- PASS `test_E1_queue_respects_daily_minutes_and_runs_fast_under_flood`
- PASS `test_E2_double_click_submits_once`
- PASS `test_E3_sql_metacharacters_in_notes_are_stored_literally`
- PASS `test_F1_same_seed_same_world`
- PASS `test_F2_policy_results_do_not_depend_on_which_other_policies_ran`
- PASS `test_F3_simulator_does_not_mutate_the_input_lives`
- PASS `test_F4_no_audit_reference_recovers_nothing`

## tests/test_app.py: 11/11 passed

- PASS `test_every_screen_renders[Operations overview]`
- PASS `test_every_screen_renders[Core inventory & deadlines]`
- PASS `test_every_screen_renders[Shipment optimisation]`
- PASS `test_every_screen_renders[Credit monitoring]`
- PASS `test_every_screen_renders[Dispute queue]`
- PASS `test_every_screen_renders[Audit-frequency simulator]`
- PASS `test_every_screen_renders[Audit trail]`
- PASS `test_ship_decision_changes_state_and_persists`
- PASS `test_dispute_decisions_remove_from_queue_and_defer_expires`
- PASS `test_counterfactual_wait_never_improves_saved_cores`
- PASS `test_world_ignores_future_decisions`

## tests/test_classifier.py: 4/4 passed

- PASS `test_manual_cases_all_pass`
- PASS `test_information_gating_future_fields_do_not_change_assessment`
- PASS `test_truth_label_is_never_used`
- PASS `test_freight_split_respects_capacity_and_cost_monotone`

## tests/test_engine.py: 20/20 passed

- PASS `test_same_seed_same_ledger`
- PASS `test_different_seed_differs`
- PASS `test_nothing_visible_after_audit_day`
- PASS `test_leak_shortfalls_exceed_tolerance`
- PASS `test_audit_never_reads_truth`
- PASS `test_audit_scores_high_on_synthetic_but_not_by_magic`
- PASS `test_clean_ledger_has_no_credit_findings`
- PASS `test_legit_damage_deduction_not_flagged`
- PASS `test_wrong_number_detected_via_supersession`
- PASS `test_stabbing_matches_brute_force`
- PASS `test_all_policies_cover_every_core_and_coreloop_never_ships_late`
- PASS `test_coreloop_beats_naive_policies_on_freight_without_missing`
- PASS `test_buffer_reduces_expected_misses_and_costs_shipments`
- PASS `test_ship_days_are_business_days_and_after_removal`
- PASS `test_queue_matches_brute_force`
- PASS `test_queue_respects_capacity_and_deadlines`
- PASS `test_queue_never_worse_than_greedy_baselines`
- PASS `test_expired_findings_are_not_queued`
- PASS `test_dispute_draft_uses_only_ledger_facts`
- PASS `test_cross_process_determinism`

## tests/test_refactor_parity.py: 1/1 passed

- PASS `test_ledgers_identical_to_pre_refactor`

**Total: 67 tests, 67 passed.**
