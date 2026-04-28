from __future__ import annotations

api_testka_keys: list = [
    "AT_test_api_method", "AT_delegate_async_httpx", "AT_test_api_method_httpx",
    "AT_generate_html", "AT_generate_html_report", "AT_generate_json",
    "AT_generate_json_report", "AT_generate_xml", "AT_generate_xml_report", "AT_execute_action",
    "AT_execute_files", "AT_add_package_to_executor", "AT_add_package_to_callback_executor",
    "AT_flask_mock_server_add_router", "AT_start_flask_mock_server", "AT_scheduler_event_trigger",
    "AT_remove_blocking_scheduler_job", "AT_remove_nonblocking_scheduler_job",
    "AT_start_blocking_scheduler", "AT_start_nonblocking_scheduler",
    "AT_start_all_scheduler", "AT_shutdown_blocking_scheduler", "AT_shutdown_nonblocking_scheduler",
    "test_api_method", "add_command_to_executor", "execute_action", "execute_files", "executor",
    "get_dir_files_as_list", "generate_html", "generate_html_report", "read_action_json",
    "write_action_json", "reformat_json", "generate_json", "generate_json_report",
    "start_apitestka_socket_server",
    "test_record_instance", "dict_to_elements_tree", "elements_tree_to_dict",
    "XMLParser", "reformat_xml_file", "generate_xml", "generate_xml_report",
    "callback_executor", "create_project_dir", "flask_mock_server_instance",
    "request", "redirect", "SchedulerManager"
]

auto_control_keys: list = [
    "AC_mouse_left", "AC_mouse_right", "AC_mouse_middle", "AC_click_mouse", "AC_get_mouse_table",
    "AC_get_mouse_position", "AC_press_mouse", "AC_release_mouse", "AC_mouse_scroll",
    "AC_set_mouse_position", "AC_get_special_table", "AC_get_keyboard_keys_table",
    "AC_type_keyboard", "AC_press_keyboard_key", "AC_release_keyboard_key", "AC_check_key_is_press",
    "AC_write", "AC_hotkey", "AC_locate_all_image", "AC_locate_image_center",
    "AC_locate_and_click", "AC_screen_size", "AC_screenshot", "AC_set_record_enable", "AC_generate_html",
    "AC_generate_json", "AC_generate_xml", "AC_generate_html_report", "AC_generate_json_report",
    "AC_generate_xml_report", "AC_record", "AC_stop_record", "AC_execute_action",
    "AC_execute_files", "AC_add_package_to_executor", "AC_add_package_to_callback_executor",
    "AC_create_project", "AC_shell_command", "AC_execute_process", "AC_scheduler_event_trigger",
    "AC_remove_blocking_scheduler_job", "AC_remove_nonblocking_scheduler_job",
    "AC_start_blocking_scheduler", "AC_start_nonblocking_scheduler", "AC_start_all_scheduler",
    "AC_shutdown_blocking_scheduler", "AC_shutdown_nonblocking_scheduler",
    "click_mouse", "mouse_keys_table", "get_mouse_position", "press_mouse", "release_mouse",
    "mouse_scroll", "set_mouse_position", "special_mouse_keys_table",
    "keyboard_keys_table", "press_keyboard_key", "release_keyboard_key", "type_keyboard", "check_key_is_press",
    "write", "hotkey", "start_exe", "SchedulerManager", "get_keyboard_keys_table",
    "screen_size", "screenshot", "locate_all_image", "locate_image_center", "locate_and_click",
    "CriticalExit", "AutoControlException", "AutoControlKeyboardException",
    "AutoControlMouseException", "AutoControlCantFindKeyException",
    "AutoControlScreenException", "ImageNotFoundException", "AutoControlJsonActionException",
    "AutoControlRecordException", "AutoControlActionNullException", "AutoControlActionException", "record",
    "stop_record", "read_action_json", "write_action_json", "execute_action", "execute_files", "executor",
    "add_command_to_executor", "multiprocess_timeout", "test_record_instance", "screenshot", "pil_screenshot",
    "generate_html", "generate_html_report", "generate_json", "generate_json_report", "generate_xml",
    "generate_xml_report", "get_dir_files_as_list", "create_project_dir", "start_autocontrol_socket_server",
    "callback_executor", "package_manager", "get_special_table", "ShellManager", "default_shell_manager",
]

web_runner_keys: list = [
    # ===== Action commands (WR_*) =====
    # webdriver manager
    "WR_get_webdriver_manager", "WR_change_index_of_webdriver", "WR_quit",
    # test object
    "WR_SaveTestObject", "WR_CleanTestObject",
    # webdriver wrapper
    "WR_set_driver", "WR_set_webdriver_options_capability",
    "WR_find_element", "WR_find_elements",
    "WR_implicitly_wait", "WR_explict_wait", "WR_sleep",
    "WR_to_url", "WR_forward", "WR_back", "WR_refresh", "WR_switch",
    "WR_set_script_timeout", "WR_set_page_load_timeout",
    "WR_get_cookies", "WR_get_cookie", "WR_add_cookie",
    "WR_delete_cookie", "WR_delete_all_cookies",
    "WR_execute", "WR_execute_script", "WR_execute_async_script",
    "WR_move_to_element", "WR_move_to_element_with_offset",
    "WR_drag_and_drop", "WR_drag_and_drop_offset",
    "WR_perform", "WR_reset_actions",
    "WR_left_click", "WR_left_click_and_hold", "WR_right_click", "WR_left_double_click",
    "WR_release", "WR_press_key", "WR_release_key",
    "WR_move_by_offset", "WR_pause",
    "WR_send_keys", "WR_send_keys_to_element", "WR_scroll",
    "WR_check_current_webdriver",
    "WR_maximize_window", "WR_fullscreen_window", "WR_minimize_window",
    "WR_set_window_size", "WR_set_window_position",
    "WR_get_window_position", "WR_get_window_rect", "WR_set_window_rect",
    "WR_get_screenshot_as_png", "WR_get_screenshot_as_base64",
    "WR_get_log", "WR_single_quit",
    # web element
    "WR_element_submit", "WR_element_clear", "WR_element_get_property",
    "WR_element_get_dom_attribute", "WR_element_get_attribute",
    "WR_element_is_selected", "WR_element_is_enabled",
    "WR_input_to_element", "WR_click_element",
    "WR_element_is_displayed", "WR_element_value_of_css_property",
    "WR_element_screenshot", "WR_element_change_web_element",
    "WR_element_check_current_web_element", "WR_element_get_select",
    "WR_element_select_by_value", "WR_element_select_by_index",
    "WR_element_select_by_visible_text",
    # record / report
    "WR_set_record_enable",
    "WR_generate_html", "WR_generate_html_report",
    "WR_generate_json", "WR_generate_json_report",
    "WR_generate_xml", "WR_generate_xml_report",
    "WR_generate_junit_xml", "WR_generate_junit_xml_report",
    "WR_generate_allure", "WR_generate_allure_report",
    "WR_generate_all_reports", "WR_report_expected_paths",
    # execute / validate
    "WR_execute_action", "WR_execute_files",
    "WR_validate_action_json", "WR_validate_action_file",
    # environment configuration
    "WR_load_env", "WR_get_env", "WR_expand_env_in_action",
    # data-driven
    "WR_load_dataset_csv", "WR_load_dataset_json",
    "WR_expand_with_row", "WR_run_with_dataset",
    # failure screenshot / retry / arbitrary-script gate
    "WR_set_failure_screenshot_dir", "WR_set_retry_policy",
    "WR_set_allow_arbitrary_script",
    # self-healing locators
    "WR_register_fallback_locator", "WR_register_fallback_locators",
    "WR_clear_fallback_locators", "WR_find_with_healing", "WR_pw_find_with_healing",
    # HTTP API testing
    "WR_http_request", "WR_http_get", "WR_http_post", "WR_http_put",
    "WR_http_patch", "WR_http_delete",
    "WR_http_assert_status", "WR_http_assert_json_contains",
    # CDP
    "WR_cdp", "WR_pw_cdp", "WR_pw_cdp_reset_sessions",
    # network throttling
    "WR_throttle", "WR_throttle_clear",
    "WR_pw_throttle", "WR_pw_throttle_clear", "WR_throttle_presets",
    # faker
    "WR_faker_seed", "WR_faker", "WR_faker_email", "WR_faker_name",
    "WR_faker_first_name", "WR_faker_last_name", "WR_faker_phone",
    "WR_faker_address", "WR_faker_uuid", "WR_faker_credit_card",
    "WR_faker_url", "WR_faker_user_agent", "WR_faker_password", "WR_faker_text",
    # browser extensions
    "WR_chrome_options_with_extension", "WR_pw_extension_args",
    # shadow DOM / iframe
    "WR_shadow_query", "WR_pw_shadow_query", "WR_pw_shadow_selector",
    "WR_iframe_switch_chain", "WR_iframe_back_to_default",
    "WR_pw_frame_locator_chain",
    # file upload / download
    "WR_upload_file", "WR_pw_upload_file",
    "WR_wait_for_download", "WR_list_new_downloads", "WR_snapshot_directory",
    # action linter / migration / schema / docs
    "WR_lint_action", "WR_lint_action_file", "WR_lint_severity_counts",
    "WR_migrate_action", "WR_migrate_action_file", "WR_migrate_directory",
    "WR_build_action_schema", "WR_export_action_schema",
    "WR_build_command_reference", "WR_export_command_reference", "WR_list_commands",
    # tracing
    "WR_set_action_span_factory",
    # database validation
    "WR_db_query", "WR_db_assert_count", "WR_db_assert_value",
    "WR_db_assert_exists", "WR_db_assert_empty",
    # scheduler
    "WR_schedule", "WR_run_scheduler_for", "WR_run_scheduler_forever",
    "WR_stop_scheduler", "WR_scheduler_counts", "WR_reset_scheduler",
    # multi-user matrix
    "WR_run_for_users",
    # failure classifier
    "WR_classify_error", "WR_classify_failure", "WR_classify_failures",
    # replay studio
    "WR_build_replay_html", "WR_export_replay_studio",
    # OAuth2 / OIDC
    "WR_oauth_client_credentials", "WR_oauth_password_grant",
    "WR_oauth_refresh_token", "WR_oauth_get_cached",
    "WR_oauth_clear_cache", "WR_oauth_bearer_header",
    # factories
    "WR_user_factory", "WR_order_factory", "WR_product_factory",
    # testcontainers
    "WR_tc_postgres", "WR_tc_redis", "WR_tc_generic",
    "WR_tc_stop", "WR_tc_cleanup_all", "WR_tc_started_count",
    # live dashboard
    "WR_dashboard_start", "WR_dashboard_stop",
    # sharding
    "WR_parse_shard_spec", "WR_partition", "WR_partition_with_spec",
    # Appium
    "WR_appium_start", "WR_appium_quit",
    "WR_appium_android_caps", "WR_appium_ios_caps",
    # LLM scaffolds
    "WR_llm_set_callable", "WR_llm_has_callable",
    "WR_llm_suggest_locator", "WR_llm_generate_actions",
    "WR_llm_self_heal_locator",
    # storage (Selenium)
    "WR_local_storage_set", "WR_local_storage_get", "WR_local_storage_remove",
    "WR_local_storage_clear", "WR_local_storage_all",
    "WR_session_storage_set", "WR_session_storage_get", "WR_session_storage_clear",
    "WR_indexed_db_drop",
    # storage (Playwright)
    "WR_pw_local_storage_set", "WR_pw_local_storage_get", "WR_pw_local_storage_remove",
    "WR_pw_local_storage_clear", "WR_pw_local_storage_all",
    "WR_pw_session_storage_set", "WR_pw_session_storage_get",
    "WR_pw_session_storage_clear", "WR_pw_indexed_db_drop",
    # service worker / cache
    "WR_sw_unregister", "WR_sw_clear_caches", "WR_sw_bypass",
    "WR_pw_sw_unregister", "WR_pw_sw_clear_caches", "WR_pw_sw_bypass",
    # console / network event capture (Playwright)
    "WR_pw_event_capture_start", "WR_pw_event_capture_stop",
    "WR_pw_event_capture_clear",
    "WR_pw_console_messages", "WR_pw_network_responses",
    "WR_pw_assert_no_console_errors",
    "WR_pw_assert_no_5xx", "WR_pw_assert_no_4xx_or_5xx",
    # secrets / security headers
    "WR_scan_secrets", "WR_scan_secrets_file", "WR_assert_no_secrets",
    "WR_audit_security_headers", "WR_audit_security_headers_url",
    # perf metrics
    "WR_perf_collect", "WR_pw_perf_collect", "WR_perf_assert_within",
    # snapshot testing
    "WR_match_snapshot", "WR_update_snapshot", "WR_delete_snapshot",
    # HAR diff
    "WR_diff_har", "WR_diff_har_files",
    # tag / dependency
    "WR_read_metadata", "WR_filter_paths",
    "WR_read_depends_on", "WR_build_dependency_graph",
    "WR_topological_order", "WR_skip_dependents_of_failed",
    # run ledger / flakiness
    "WR_ledger_record_run", "WR_ledger_failed_files",
    "WR_ledger_passed_files", "WR_ledger_clear",
    "WR_flakiness_stats", "WR_flaky_paths",
    # A/B run mode
    "WR_run_ab", "WR_diff_ab_records",
    # cloud grid (BrowserStack / Sauce Labs / LambdaTest)
    "WR_browserstack_capabilities", "WR_saucelabs_capabilities",
    "WR_lambdatest_capabilities",
    "WR_connect_browserstack", "WR_connect_saucelabs", "WR_connect_lambdatest",
    "WR_start_remote_driver",
    # JIRA / TestRail
    "WR_jira_create_issue", "WR_jira_create_failure_issues",
    "WR_testrail_send_results", "WR_testrail_results_from_pairs",
    "WR_testrail_close_run",
    # GitHub Actions annotations
    "WR_gh_format_error", "WR_gh_emit_failures", "WR_gh_emit_from_junit_xml",
    # Lighthouse / Locust
    "WR_lighthouse_run", "WR_lighthouse_assert_scores",
    "WR_locust_run", "WR_locust_build_user_class",
    # accessibility (axe-core)
    "WR_a11y_load_axe", "WR_a11y_run_audit",
    "WR_pw_a11y_run_audit", "WR_a11y_summarise",
    # webhook / Slack
    "WR_summarise_run", "WR_notify_webhook",
    "WR_notify_slack", "WR_notify_run_summary",
    # POM generator
    "WR_generate_pom_from_url", "WR_generate_pom_from_html", "WR_write_pom_to_file",
    # visual regression
    "WR_visual_capture_baseline", "WR_visual_compare",
    # browser recorder
    "WR_recorder_start", "WR_recorder_stop",
    "WR_recorder_pull_events", "WR_recorder_save",
    # Playwright — page level
    "WR_pw_launch", "WR_pw_quit",
    "WR_pw_start_har_recording", "WR_pw_stop_har_recording",
    "WR_pw_route_mock", "WR_pw_route_mock_json",
    "WR_pw_route_unmock", "WR_pw_route_clear",
    "WR_pw_emulate", "WR_pw_stop_emulate", "WR_pw_list_devices",
    "WR_pw_set_geolocation", "WR_pw_grant_permissions", "WR_pw_clear_permissions",
    "WR_pw_set_timezone",
    "WR_pw_clock_install", "WR_pw_clock_set_time", "WR_pw_clock_run_for",
    "WR_pw_set_locale",
    "WR_pw_to_url", "WR_pw_forward", "WR_pw_back", "WR_pw_refresh",
    "WR_pw_url", "WR_pw_title", "WR_pw_content",
    "WR_pw_set_default_timeout", "WR_pw_set_default_navigation_timeout",
    "WR_pw_new_page", "WR_pw_switch_to_page",
    "WR_pw_close_page", "WR_pw_page_count",
    "WR_pw_find_element", "WR_pw_find_elements",
    "WR_pw_find_element_with_test_object_record",
    "WR_pw_find_elements_with_test_object_record",
    "WR_pw_save_test_object_to_selector",
    "WR_pw_click", "WR_pw_dblclick", "WR_pw_hover",
    "WR_pw_fill", "WR_pw_type_text", "WR_pw_press",
    "WR_pw_check", "WR_pw_uncheck", "WR_pw_select_option",
    "WR_pw_drag_and_drop", "WR_pw_evaluate",
    "WR_pw_get_cookies", "WR_pw_add_cookies", "WR_pw_clear_cookies",
    "WR_pw_screenshot", "WR_pw_screenshot_bytes",
    "WR_pw_wait_for_selector", "WR_pw_wait_for_load_state",
    "WR_pw_wait_for_timeout", "WR_pw_wait_for_url",
    "WR_pw_set_viewport_size", "WR_pw_viewport_size",
    "WR_pw_mouse_click", "WR_pw_mouse_move",
    "WR_pw_mouse_down", "WR_pw_mouse_up",
    "WR_pw_keyboard_press", "WR_pw_keyboard_type",
    "WR_pw_keyboard_down", "WR_pw_keyboard_up",
    # Playwright — element level
    "WR_pw_element_click", "WR_pw_element_dblclick",
    "WR_pw_element_hover", "WR_pw_element_fill",
    "WR_pw_element_type_text", "WR_pw_element_press",
    "WR_pw_element_clear", "WR_pw_element_check", "WR_pw_element_uncheck",
    "WR_pw_element_select_option",
    "WR_pw_element_get_attribute", "WR_pw_element_get_property",
    "WR_pw_element_inner_text", "WR_pw_element_inner_html",
    "WR_pw_element_is_visible", "WR_pw_element_is_enabled", "WR_pw_element_is_checked",
    "WR_pw_element_scroll_into_view", "WR_pw_element_screenshot",
    "WR_pw_element_change",
    # add package
    "WR_add_package_to_executor", "WR_add_package_to_callback_executor",
    # naming aliases
    "WR_new_driver", "WR_quit_all", "WR_quit_current",
    "WR_explicit_wait", "WR_save_test_object", "WR_clear_test_objects",
    "WR_find_recorded_element", "WR_find_recorded_elements",
    "WR_element_input", "WR_element_click", "WR_element_assert",

    # ===== Python public API (from je_web_runner.__all__) =====
    "web_element_wrapper", "set_webdriver_options_argument",
    "webdriver_wrapper_instance", "get_webdriver_manager",
    "get_desired_capabilities", "get_desired_capabilities_keys",
    "add_command_to_executor", "execute_action", "execute_files", "executor",
    "generate_html", "generate_html_report",
    "generate_json", "generate_json_report", "read_action_json",
    "generate_xml", "generate_xml_report",
    "generate_junit_xml", "generate_junit_xml_report",
    "generate_allure", "generate_allure_report",
    "start_web_runner_socket_server", "get_dir_files_as_list",
    "TestObject", "create_test_object", "get_test_object_type_list",
    "test_record_instance", "Keys", "callback_executor", "create_project_dir",
    # env / data-driven
    "load_env", "get_env", "expand_in_action", "EnvConfigError",
    "load_dataset_csv", "load_dataset_json",
    "expand_with_row", "run_with_dataset", "DataDrivenError",
    # self-healing
    "HealingError", "HealingRegistry", "healing_registry",
    "register_fallback", "register_fallbacks", "clear_fallbacks",
    "find_with_healing_selenium", "find_with_healing_playwright",
    # HTTP
    "http_request", "http_get", "http_post", "http_put", "http_patch", "http_delete",
    "http_assert_status", "http_assert_json_contains", "get_last_response",
    "HttpAssertionError",
    # accessibility / CDP
    "AccessibilityError", "load_axe_source",
    "selenium_run_audit", "playwright_run_audit", "summarise_violations",
    "CDPError", "selenium_cdp", "playwright_cdp", "reset_playwright_cdp_sessions",
    # notifier
    "summarise_run", "notify_webhook", "notify_slack",
    "notify_run_summary", "NotifierError",
    # POM / validators
    "POMGeneratorError", "extract_elements_from_html", "generate_pom_class",
    "generate_pom_from_html", "generate_pom_from_url", "write_pom_to_file",
    "validate_action_json", "validate_action_file", "validate_action_files",
    # visual regression / recorder
    "visual_capture_baseline", "visual_compare_with_baseline",
    "recorder_start", "recorder_stop", "recorder_pull_events",
    "recorder_events_to_actions", "recorder_save_recording",
    # Playwright wrappers
    "PlaywrightBackendError", "PlaywrightWrapper", "playwright_wrapper_instance",
    "PlaywrightElementWrapper", "playwright_element_wrapper",
    "pw_launch", "pw_quit",
    "pw_start_har_recording", "pw_stop_har_recording",
    "pw_route_mock", "pw_route_mock_json", "pw_route_unmock", "pw_route_clear",
    "pw_to_url", "pw_forward", "pw_back", "pw_refresh",
    "pw_url", "pw_title", "pw_content",
    "pw_set_default_timeout", "pw_set_default_navigation_timeout",
    "pw_new_page", "pw_switch_to_page", "pw_close_page", "pw_page_count",
    "pw_find_element", "pw_find_elements",
    "pw_find_element_with_test_object_record",
    "pw_find_elements_with_test_object_record",
    "pw_save_test_object_to_selector",
    "pw_click", "pw_dblclick", "pw_hover",
    "pw_fill", "pw_type_text", "pw_press",
    "pw_check", "pw_uncheck", "pw_select_option", "pw_drag_and_drop",
    "pw_evaluate",
    "pw_get_cookies", "pw_add_cookies", "pw_clear_cookies",
    "pw_screenshot", "pw_screenshot_bytes",
    "pw_wait_for_selector", "pw_wait_for_load_state",
    "pw_wait_for_timeout", "pw_wait_for_url",
    "pw_set_viewport_size", "pw_viewport_size",
    "pw_mouse_click", "pw_mouse_move", "pw_mouse_down", "pw_mouse_up",
    "pw_keyboard_press", "pw_keyboard_type",
    "pw_keyboard_down", "pw_keyboard_up",
]

load_density_keys: list = [
    "LD_start_test", "LD_generate_html", "LD_generate_html_report", "LD_generate_json", "LD_generate_json_report",
    "LD_generate_xml", "LD_generate_xml_report", "LD_execute_action", "LD_execute_files",
    "LD_add_package_to_executor", "LD_scheduler_event_trigger", "LD_remove_blocking_scheduler_job",
    "LD_remove_nonblocking_scheduler_job", "LD_start_blocking_scheduler", "LD_start_nonblocking_scheduler",
    "LD_start_all_scheduler", "LD_shutdown_blocking_scheduler", "LD_shutdown_nonblocking_scheduler",
    "create_env", "SchedulerManager",
    "locust_wrapper_proxy",
    "prepare_env",
    "test_record_instance",
    "execute_action", "execute_files", "executor", "add_command_to_executor",
    "get_dir_files_as_list",
    "generate_html", "generate_html_report",
    "generate_json", "generate_json_report", "read_action_json",
    "generate_xml", "generate_xml_report",
    "start_load_density_socket_server",
    "SequentialTaskSet", "task", "TaskSet",
    "callback_executor", "create_project_dir"
]

automation_file_keys: list = [
    # Core executor
    "FA_execute_action", "FA_execute_files", "FA_execute_action_parallel",
    "FA_execute_action_dag", "FA_validate",
    # Files
    "FA_create_file", "FA_copy_file", "FA_rename_file", "FA_remove_file",
    "FA_copy_all_file_to_dir", "FA_copy_specify_extension_file",
    # Directories
    "FA_copy_dir", "FA_create_dir", "FA_remove_dir_tree", "FA_rename_dir", "FA_sync_dir",
    # Shell
    "FA_run_shell",
    # JSON edit
    "FA_json_get", "FA_json_set", "FA_json_delete",
    # Tar
    "FA_create_tar", "FA_extract_tar",
    # Zip
    "FA_zip_dir", "FA_zip_file", "FA_zip_info", "FA_zip_file_info",
    "FA_set_zip_password", "FA_unzip_file", "FA_read_zip_file", "FA_unzip_all",
    # Conditional
    "FA_if_exists", "FA_if_newer", "FA_if_size_gt",
    # Text / encoding
    "FA_file_split", "FA_file_merge", "FA_encoding_convert", "FA_line_count", "FA_sed_replace",
    # Diff / patch
    "FA_diff_files", "FA_diff_dirs", "FA_apply_patch",
    # CSV / JSONL
    "FA_csv_filter", "FA_csv_to_jsonl", "FA_jsonl_iter", "FA_jsonl_append",
    # YAML
    "FA_yaml_get", "FA_yaml_set", "FA_yaml_delete",
    # Parquet
    "FA_parquet_read", "FA_parquet_write", "FA_csv_to_parquet",
    # HTTP
    "FA_download_file",
    # Utils / integrity / crypto
    "FA_fast_find", "FA_file_checksum", "FA_verify_checksum", "FA_find_duplicates",
    "FA_write_manifest", "FA_verify_manifest", "FA_grep", "FA_rotate_backups",
    "FA_copy_between", "FA_encrypt_file", "FA_decrypt_file", "FA_tracing_init",
    # Google Drive
    "FA_drive_later_init", "FA_drive_search_all_file", "FA_drive_search_field",
    "FA_drive_search_file_mimetype", "FA_drive_upload_dir_to_folder",
    "FA_drive_upload_to_folder", "FA_drive_upload_dir_to_drive", "FA_drive_upload_to_drive",
    "FA_drive_add_folder", "FA_drive_share_file_to_anyone", "FA_drive_share_file_to_domain",
    "FA_drive_share_file_to_user", "FA_drive_delete_file", "FA_drive_download_file",
    "FA_drive_download_file_from_folder",
    # S3
    "FA_s3_later_init", "FA_s3_upload_file", "FA_s3_upload_dir",
    "FA_s3_download_file", "FA_s3_delete_object", "FA_s3_list_bucket",
    # Azure Blob
    "FA_azure_blob_later_init", "FA_azure_blob_upload_file", "FA_azure_blob_upload_dir",
    "FA_azure_blob_download_file", "FA_azure_blob_delete_blob", "FA_azure_blob_list_container",
    # Dropbox
    "FA_dropbox_later_init", "FA_dropbox_upload_file", "FA_dropbox_upload_dir",
    "FA_dropbox_download_file", "FA_dropbox_delete_path", "FA_dropbox_list_folder",
    # SFTP
    "FA_sftp_later_init", "FA_sftp_close", "FA_sftp_upload_file", "FA_sftp_upload_dir",
    "FA_sftp_download_file", "FA_sftp_delete_path", "FA_sftp_list_dir",
    # FTP
    "FA_ftp_later_init", "FA_ftp_close", "FA_ftp_upload_file", "FA_ftp_upload_dir",
    "FA_ftp_download_file", "FA_ftp_delete_path", "FA_ftp_list_dir",
    # OneDrive
    "FA_onedrive_later_init", "FA_onedrive_device_code_login", "FA_onedrive_upload_file",
    "FA_onedrive_upload_dir", "FA_onedrive_download_file", "FA_onedrive_delete_item",
    "FA_onedrive_list_folder", "FA_onedrive_close",
    # Box
    "FA_box_later_init", "FA_box_upload_file", "FA_box_upload_dir", "FA_box_download_file",
    "FA_box_delete_file", "FA_box_delete_folder", "FA_box_list_folder",
    # Triggers
    "FA_watch_start", "FA_watch_stop", "FA_watch_stop_all", "FA_watch_list",
    # Scheduler
    "FA_schedule_add", "FA_schedule_remove", "FA_schedule_remove_all", "FA_schedule_list",
    # Progress / cancellation
    "FA_progress_list", "FA_progress_cancel", "FA_progress_clear",
    # Notifications
    "FA_notify_send", "FA_notify_list",
    # Public Python API symbols
    "copy_file", "rename_file", "remove_file", "copy_all_file_to_dir",
    "copy_specify_extension_file", "create_file",
    "copy_dir", "create_dir", "remove_dir_tree", "rename_dir", "sync_dir",
    "zip_dir", "zip_file", "zip_info", "zip_file_info", "set_zip_password",
    "unzip_file", "read_zip_file", "unzip_all",
    "driver_instance", "drive_search_all_file", "drive_search_field",
    "drive_search_file_mimetype", "drive_upload_dir_to_folder", "drive_upload_to_folder",
    "drive_upload_dir_to_drive", "drive_upload_to_drive", "drive_add_folder",
    "drive_share_file_to_anyone", "drive_share_file_to_domain", "drive_share_file_to_user",
    "drive_delete_file", "drive_download_file", "drive_download_file_from_folder",
    "download_file", "validate_http_url",
    "execute_action", "execute_action_parallel", "execute_files", "validate_action",
    "add_command_to_executor", "read_action_json", "write_action_json",
    "get_dir_files_as_list", "create_project_dir",
    "ActionExecutor", "ActionRegistry", "CallbackExecutor", "PackageLoader",
    "Quota", "retry_on_transient", "safe_join", "is_within",
    "executor", "callback_executor", "package_manager",
    "build_default_registry",
    "GoogleDriveClient", "S3Client", "s3_instance", "register_s3_ops",
    "AzureBlobClient", "azure_blob_instance", "register_azure_blob_ops",
    "DropboxClient", "dropbox_instance", "register_dropbox_ops",
    "SFTPClient", "sftp_instance", "register_sftp_ops",
    "FTPClient", "ftp_instance", "register_ftp_ops",
    "OneDriveClient", "onedrive_instance", "register_onedrive_ops",
    "BoxClient", "box_instance", "register_box_ops",
    "TCPActionServer", "start_autocontrol_socket_server",
    "HTTPActionServer", "start_http_action_server",
    "HTTPActionClient", "ProjectBuilder",
    "scheduler", "schedule_add", "schedule_remove", "schedule_remove_all", "schedule_list",
    "trigger_manager", "watch_start", "watch_stop", "watch_stop_all", "watch_list",
    "notification_manager", "notify_send",
    "launch_ui",
]

mail_thunder_keys: list = [
    "MT_smtp_later_init", "MT_smtp_create_message_with_attach_and_send", "MT_smtp_create_message_and_send",
    "MT_smtp_quit", "MT_imap_later_init", "MT_imap_select_mailbox", "MT_imap_search_mailbox",
    "MT_imap_mail_content_list", "MT_imap_output_all_mail_as_file", "MT_imap_quit",
    "MT_set_mail_thunder_os_environ", "MT_get_mail_thunder_os_environ", "MT_add_package_to_executor",
    "MT_scheduler_event_trigger", "MT_remove_blocking_scheduler_job", "MT_remove_nonblocking_scheduler_job",
    "MT_start_blocking_scheduler", "MT_start_nonblocking_scheduler", "MT_start_all_scheduler",
    "MT_shutdown_blocking_scheduler", "MT_shutdown_nonblocking_scheduler",
    "IMAPWrapper", "imap_instance", "SMTPWrapper", "smtp_instance", "is_need_to_save_content",
    "mail_thunder_content_data_dict", "read_output_content", "write_output_content", "get_mail_thunder_os_environ",
    "set_mail_thunder_os_environ", "read_action_json", "get_dir_files_as_list", "execute_action", "execute_files",
    "add_command_to_executor", "create_project_dir"
]

test_pioneer_keys: list = [
    "jobs", "pioneer_log",
    "steps",
    "name",
    "run", "with", "run_folder",
    "wait",
    "open_url",
    "open_program", "close_program", "redirect_stdout", "redirect_stderr",
]

package_keyword_list = {
    "je_auto_control": auto_control_keys,
    "je_load_density": load_density_keys,
    "je_api_testka": api_testka_keys,
    "je_web_runner": web_runner_keys,
    "automation_file": automation_file_keys,
    "mail_thunder": mail_thunder_keys,
    "test_pioneer": test_pioneer_keys
}
