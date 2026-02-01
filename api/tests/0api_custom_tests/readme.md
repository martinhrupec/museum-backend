audit_log_summary ✅

    1. def summary(self, request): ✅

exhibition_viewset ✅

    1. next_week ✅

general_views ✅

    1. session_login ✅
    2. session_logout ✅
    3. session_check ✅

jwt_views ✅

    1. jwt_logout ✅

ostali jwt api pozivi ✅

    1. token ✅
    2. refresh ✅
    3. ... ako ima jos nesto

guard_viewset ✅

    1. set_availability (provjeri moze li admin postaviti availability za guarda) ✅

point_viewset ✅

    1. penalize_unannounced_lateness ✅

position_history_viewset ✅

    1. assign ✅
    2. cancel ✅
    3. get_this_week_assigned_schedule ✅
    4. get_next_week_assigned_schedule ✅
    5. report_lateness (to bi morali moci samo guardovi) ✅ - Admin dobiva 403/400
    6. my_work_history (to bi morali moci samo guardovi) ✅ - Admin dobiva 403/400

position_swap_request ✅

    1. all ✅
    2. all_active ✅
    3. my_requests (to mogu samo guardovi) ✅ - Admin dobiva 403/400
    4. accept_swap (samo guardovi) ✅ - Admin dobiva 403/400

position_viewset ✅

    1. next_week ✅
    2. request_swap ✅ - Admin dobiva 403/400

system_settings_viewset ✅

    1. current ✅
    2. workdays ✅

user_viewset ✅

    1. me ✅
    2. update_profile ✅
    3. change_password ✅
