from pybreeze.utils.exception.exception_tags import (
    add_command_type_exception_tag,
    add_command_not_allow_package_exception_tag,
    send_html_exception_tag,
    auto_control_process_executor_exception_tag,
    api_testka_process_executor_exception_tag,
    web_runner_process_executor_exception_tag,
    load_density_process_executor_exception_tag,
    not_install_exception,
    wrong_test_data_format_exception_tag,
    exec_error,
    file_not_fond_error,
    compiler_not_found_error,
    not_install_package_error,
    cant_reformat_json_error,
    wrong_json_data_error,
    cant_read_xml_error,
    xml_type_error,
)


class TestExceptionTags:
    def test_all_tags_are_strings(self):
        tags = [
            add_command_type_exception_tag,
            add_command_not_allow_package_exception_tag,
            send_html_exception_tag,
            auto_control_process_executor_exception_tag,
            api_testka_process_executor_exception_tag,
            web_runner_process_executor_exception_tag,
            load_density_process_executor_exception_tag,
            not_install_exception,
            wrong_test_data_format_exception_tag,
            exec_error,
            file_not_fond_error,
            compiler_not_found_error,
            not_install_package_error,
            cant_reformat_json_error,
            wrong_json_data_error,
            cant_read_xml_error,
            xml_type_error,
        ]
        for tag in tags:
            assert isinstance(tag, str)
            assert len(tag) > 0

    def test_send_html_tag_has_instructions(self):
        assert "je_mail_thunder" in send_html_exception_tag
        assert "default_name.html" in send_html_exception_tag

    def test_process_executor_tags_mention_tools(self):
        assert "AutoControl" in auto_control_process_executor_exception_tag
        assert "APITestka" in api_testka_process_executor_exception_tag
        assert "WebRunner" in web_runner_process_executor_exception_tag
        assert "LoadDensity" in load_density_process_executor_exception_tag
