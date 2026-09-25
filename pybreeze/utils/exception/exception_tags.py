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

# URL checks (utils/network): they name no path or query, which may hold a token
url_unsafe_characters_error: str = "URL contains a backslash, whitespace or a control character."
url_unparsable_error: str = "URL cannot be parsed."
url_ambiguous_host_error: str = "URL names its host ambiguously."
url_scheme_not_allowed_error: str = "Scheme '{scheme}' is not allowed. Use http or https."
url_no_hostname_error: str = "URL has no hostname."
hostname_unresolved_error: str = "Cannot resolve hostname '{hostname}': {detail}"
hostname_without_address_error: str = "Cannot resolve hostname '{hostname}'."
address_not_public_error: str = "Access to non-public address {address} is blocked."
response_too_large_error: str = "Response body exceeds the {limit}-byte limit."

# What went wrong with a request (http_client.describe_request_error)
request_timed_out_error: str = "the request timed out"
request_tls_failed_error: str = "the secure connection could not be made"
request_no_connection_error: str = "could not connect to the server"
request_too_many_redirects_error: str = "too many redirects"
request_invalid_url_error: str = "the URL is not valid"

# Image download (diagram editor)
image_is_text_error: str = "Expected an image but the server returned '{content_type}'."
image_declared_too_large_error: str = "Image too large ({size} bytes, max {limit})."
image_too_large_error: str = "Image exceeds {megabytes} MB limit."

# SSH
host_key_rejected_error: str = "Host key for {hostname} rejected by user."
host_key_changed_error: str = (
    "The host key of {hostname} has changed: it is now {fingerprint}, not the {trusted} trusted before. "
    "Someone may be intercepting the connection. If the server's key was changed on purpose, "
    "remove its line from {known_hosts} and connect again."
)

# An answer the Skills panel got that is not 2xx
redirect_not_followed_error: str = "Redirect (not followed) to {where}"
redirect_same_server_error: str = "Redirect (not followed) to another path on this server"
redirect_nowhere_error: str = "Redirect (not followed) to an unnamed place"
authorization_failed_error: str = "Authentication/Authorization failed"
server_error_error: str = "Server error: {body}"

# A diagram file (.diagram.json) that is not one
diagram_not_an_object_error: str = "a diagram file holds an object, not a {kind}"
diagram_section_not_a_list_error: str = "a diagram's '{section}' is a list, not a {kind}"

# Why a run's report mail was not sent (mail_thunder_extend.send_after_test)
mail_not_installed_error: str = "je_mail_thunder is not installed"
mail_settings_unreadable_error: str = "the mail settings file (mail_thunder_content.json) could not be read"
mail_no_user_error: str = "no mail user is set"
mail_login_failed_error: str = "the mail server login failed"
mail_send_failed_error: str = "sending failed ({kind})"
report_missing_error: str = "the run wrote no {name}"
report_not_a_file_error: str = "{name} is not a file"
report_stale_error: str = "the run wrote no new {name}; the one there is from an earlier run"
