"""The targets PyBreeze ships, and the registry the cURL and HAR importers read.

Plain ``requests``, pytest, APITestka (as Python and as a JSON action list),
LoadDensity and WebRunner. Each has what it writes (a ``.py`` or a ``.json``
file) and which parts of a request it sends said beside its generators.
``test_import_targets.py`` checks every ``carries`` below against what the
generator really writes.
"""
from __future__ import annotations

from pybreeze.utils.curl_import.request_codegen import to_requests_code
from pybreeze.utils.curl_import.script_templates import (
    to_apitestka_action_json,
    to_apitestka_python,
    to_loaddensity_python,
    to_pytest_test,
)
from pybreeze.utils.har_import.har_codegen import (
    apitestka_action_script,
    apitestka_python_script,
    loaddensity_script,
    pytest_script,
    requests_script,
)
from pybreeze.utils.import_targets.target_registry import ImportTargetRegistry, RequestPart, TargetDescriptor
from pybreeze.utils.import_targets.webrunner_target import to_webrunner_action_json, webrunner_action_script

_PYTHON = "py"
_JSON = "json"

# No target reads cookies from the file -b names: the Python ones say so in a
# comment, and the JSON action refuses the request
_SENT_BY_REQUESTS = frozenset(RequestPart) - {RequestPart.COOKIE_FILE}
# test_api_method_requests() is not given the timeout
_SENT_BY_APITESTKA = _SENT_BY_REQUESTS - {RequestPart.TIMEOUT}
# JSON cannot open a file, so an action holds neither an upload nor a body read from one
_SENT_BY_AN_ACTION = _SENT_BY_APITESTKA - {RequestPart.FILE_UPLOAD, RequestPart.BODY_FILE}
# The shared Locust task drives a request by its method and URL alone
_SENT_BY_LOADDENSITY = frozenset({RequestPart.METHOD})
# A browser goes to an address: it keeps the cookies and a time limit, and nothing else of a request
_SENT_BY_A_BROWSER = frozenset({RequestPart.COOKIES, RequestPart.TIMEOUT})

# The first target is the default: what an unknown key generates.
_BUILTIN_TARGETS = (
    TargetDescriptor(
        key="requests", label_key="curl_import_target_requests", extension=_PYTHON,
        generate_one=to_requests_code, generate_many=requests_script, carries=_SENT_BY_REQUESTS),
    TargetDescriptor(
        key="pytest", label_key="curl_import_target_pytest", extension=_PYTHON,
        generate_one=to_pytest_test, generate_many=pytest_script, carries=_SENT_BY_REQUESTS),
    TargetDescriptor(
        key="apitestka_python", label_key="curl_import_target_apitestka_python", extension=_PYTHON,
        generate_one=to_apitestka_python, generate_many=apitestka_python_script, carries=_SENT_BY_APITESTKA),
    TargetDescriptor(
        key="apitestka_action", label_key="curl_import_target_apitestka_action", extension=_JSON,
        generate_one=to_apitestka_action_json, generate_many=apitestka_action_script,
        carries=_SENT_BY_AN_ACTION, single_basename="action", batch_basename="actions"),
    TargetDescriptor(
        key="loaddensity_python", label_key="curl_import_target_loaddensity_python", extension=_PYTHON,
        generate_one=to_loaddensity_python, generate_many=loaddensity_script, carries=_SENT_BY_LOADDENSITY),
    TargetDescriptor(
        key="webrunner_action", label_key="curl_import_target_webrunner_action", extension=_JSON,
        generate_one=to_webrunner_action_json, generate_many=webrunner_action_script,
        carries=_SENT_BY_A_BROWSER, single_basename="web_action", batch_basename="web_actions"),
)

IMPORT_TARGETS = ImportTargetRegistry()
for _target in _BUILTIN_TARGETS:
    IMPORT_TARGETS.register(_target)
