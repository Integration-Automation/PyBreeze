from pybreeze.utils.exception.exception_tags import (
    send_html_exception_tag,
    cant_reformat_json_error,
    wrong_json_data_error,
)


class TestExceptionTags:
    def test_all_tags_are_strings(self):
        tags = [
            send_html_exception_tag,
            cant_reformat_json_error,
            wrong_json_data_error,
        ]
        for tag in tags:
            assert isinstance(tag, str)
            assert len(tag) > 0

    def test_send_html_tag_has_instructions(self):
        assert "je_mail_thunder" in send_html_exception_tag
        assert "default_name.html" in send_html_exception_tag
