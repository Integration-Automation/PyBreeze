from __future__ import annotations

# add command exception
add_command_type_exception_tag: str = "command execute_return_value type must be a method or function"
add_command_not_allow_package_exception_tag: str = "chosen command package is not allowed"

# send html report exception
send_html_exception_tag: str = """
make sure you have installed je_mail_thunder
can't send HTML report: check that the login username and password are correct
and that the current working folder contains default_name.html (the default HTML report execute_detail)
or use the file_path function to read
"""

# test executor exception
auto_control_process_executor_exception_tag: str = "can't run AutoControl"
api_testka_process_executor_exception_tag: str = "can't run APITestka"
web_runner_process_executor_exception_tag: str = "can't run WebRunner"
load_density_process_executor_exception_tag: str = "can't run LoadDensity"

# Install
not_install_exception: str = "please install the package first; can't find the package"

# ui exception
wrong_test_data_format_exception_tag: str = "incorrect test data format"

exec_error: str = "AutomationEditor execution error"
file_not_fond_error: str = "File not found"
compiler_not_found_error: str = "Compiler not found"
not_install_package_error: str = "required package not installed"

# json exception
cant_reformat_json_error: str = "can't reformat JSON: is the type correct?"
wrong_json_data_error: str = "can't parse JSON"

# XML
cant_read_xml_error: str = "can't read XML"
xml_type_error: str = "XML type error"

# cURL import
empty_curl_command_error: str = "no curl command provided"
not_a_curl_command_error: str = "the command does not look like a curl command"
malformed_curl_command_error: str = "can't parse the curl command: check quoting"
no_url_in_curl_error: str = "no URL found in the curl command"

# HAR import
empty_har_error: str = "no HAR content provided"
invalid_har_json_error: str = "can't parse the file as JSON: it is not a valid HAR export"
not_a_har_document_error: str = "the JSON has no log.entries list, so it is not a HAR export"
no_entries_in_har_error: str = "the HAR export contains no requests"

# JWT decode
empty_jwt_error: str = "no token provided"
malformed_jwt_error: str = "a JWT must have three dot-separated parts"
jwt_segment_decode_error: str = "can't decode a JWT segment: invalid base64url or JSON"

# Timestamp conversion
empty_timestamp_error: str = "no value provided"
unrecognized_timestamp_error: str = "not a recognized epoch number or ISO-8601 date-time"

# Query <-> JSON conversion
invalid_json_object_error: str = "the input must be a JSON object of key/value pairs"
invalid_json_for_query_error: str = "can't parse the input as JSON"

# Regex testing
empty_regex_pattern_error: str = "no pattern provided"
invalid_regex_pattern_error: str = "invalid regular expression: {detail}"

# URL parse / build
invalid_json_for_url_error: str = "can't parse the input as JSON"
invalid_url_components_error: str = "the input must be a JSON object of URL parts"
