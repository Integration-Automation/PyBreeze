"""A captured request as WebRunner actions: as much of it as a browser does.

WebRunner drives a browser, and a browser does not send "a request": it goes to
an address, with its own headers, and sends the cookies it holds for that site.
So only part of a captured request can be said in WebRunner's actions:

- the URL, query included, is where the browser goes (``WR_to_url``);
- cookies are set once the browser is on the site (a browser takes a cookie
  only for the page it is on), and the page is then loaded again so that they
  are sent;
- a time limit becomes the page-load timeout.

The method (a navigation is a ``GET``), headers, a body or form, an upload and
credentials have no action here and are left out. The target says so in its
``carries`` (``builtin_targets.py``), which is what lets an importer tell the
user before the script is run, rather than have a ``POST`` quietly become a
page view.

Pure text generation: no browser is started and nothing is sent.
"""
from __future__ import annotations

import math

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.import_targets.normalized_request import NormalizedRequest, normalize
from pybreeze.utils.json_format.view_safe import dumps_for_view

# The browser the generated actions start; the one line a user is most likely to change
_DEFAULT_BROWSER = "chrome"
_START_BROWSER = "WR_get_webdriver_manager"
_GO_TO = "WR_to_url"
_ADD_COOKIE = "WR_add_cookie"
_PAGE_LOAD_TIMEOUT = "WR_set_page_load_timeout"
_QUIT = "WR_quit"


def _visit(sent: NormalizedRequest) -> list[list]:
    """The actions that take the browser to *sent*'s address, with its cookies and its time limit."""
    actions: list[list] = []
    # WebRunner takes whole seconds; curl's 0 means no limit, which is the browser's own
    if sent.timeout is not None and sent.timeout > 0:
        actions.append([_PAGE_LOAD_TIMEOUT, {"time_to_wait": math.ceil(sent.timeout)}])
    actions.append([_GO_TO, {"url": sent.url}])
    if sent.cookies:
        actions.extend([_ADD_COOKIE, {"cookie_dict": {"name": name, "value": value}}] for name, value in sent.cookies)
        actions.append([_GO_TO, {"url": sent.url}])
    return actions


def webrunner_actions(requests: list[CurlRequest]) -> list[list]:
    """The action list that starts a browser, visits each of *requests* in order and quits.

    :param requests: the captured requests, in capture order
    :return: the actions, as WebRunner's executor takes them
    """
    actions: list[list] = [[_START_BROWSER, {"webdriver_name": _DEFAULT_BROWSER}]]
    for request in requests:
        actions.extend(_visit(normalize(request)))
    actions.append([_QUIT])
    return actions


def to_webrunner_action_json(request: CurlRequest) -> str:
    """Generate a WebRunner JSON action list that visits *request*'s address.

    :param request: the captured request
    :return: a formatted JSON action list
    """
    return dumps_for_view(webrunner_actions([request]), indent=4) + "\n"


def webrunner_action_script(requests: list[CurlRequest]) -> str:
    """Generate one WebRunner JSON action list that visits every one of *requests* in one browser.

    :param requests: the captured requests, in capture order
    :return: a formatted JSON action list
    """
    return dumps_for_view(webrunner_actions(requests), indent=4) + "\n"
