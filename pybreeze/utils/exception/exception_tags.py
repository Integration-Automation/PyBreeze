from __future__ import annotations

# send html report exception
send_html_exception_tag: str = """
make sure you have installed je_mail_thunder
can't send HTML report: check that the login username and password are correct
and that the current working folder contains default_name.html (the default HTML report execute_detail)
or use the file_path function to read
"""

# json exception
cant_reformat_json_error: str = "can't reformat JSON: is the type correct?"
wrong_json_data_error: str = "can't parse JSON"
json_duplicate_key_error: str = "the JSON gives the key {key!r} twice in one object"

# cURL import
empty_curl_command_error: str = "no curl command provided"
not_a_curl_command_error: str = "the command does not look like a curl command"
malformed_curl_command_error: str = "can't parse the curl command: check quoting"
no_url_in_curl_error: str = "no URL found in the curl command"
get_with_file_body_error: str = (
    "-G sends the data as the query string, which a generated script cannot read from a file: give it inline"
)
action_cannot_read_files_error: str = (
    "an APITestka JSON action cannot upload a file or read a body or cookies from one: choose a Python target"
)
malformed_url_error: str = "the URL is malformed (for example an unclosed [ or a port that is not a number)"
invalid_http_method_error: str = (
    "not an HTTP method: a method is one word of letters, digits and !#$%&'*+.^_`|~-")

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
nested_query_value_error: str = (
    "a query value must be a string, number, true/false or null, or a list of them")
invalid_json_for_query_error: str = "can't parse the input as JSON"
query_not_utf8_error: str = (
    "a percent-escape in the query is not UTF-8 text (for example %B0), so it has no JSON form")
unencodable_text_error: str = (
    "a value holds a character that cannot be written in a URL (a lone surrogate such as \\ud83d)"
)

# Regex testing
empty_regex_pattern_error: str = "no pattern provided"
invalid_regex_pattern_error: str = "invalid regular expression: {detail}"

# URL parse / build
invalid_json_for_url_error: str = "can't parse the input as JSON"
invalid_url_components_error: str = "the input must be a JSON object of URL parts"
unreadable_url_error: str = "the input is not a URL that can be read"
url_port_out_of_range_error: str = "the port must be a number from 0 to 65535"
regex_timeout_error: str = (
    "the pattern was still running after {seconds} s and was stopped; nested "
    "repetition such as (a+)+ can take exponentially long on text that almost matches")
regex_worker_error: str = "the pattern could not be run: {detail}"
