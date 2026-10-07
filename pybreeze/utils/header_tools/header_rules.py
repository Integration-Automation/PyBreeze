"""What each header finding is: its rule, in words a person and a tool can both use.

The analyzer reports a finding by a stable code (``cookie_not_secure``). A code
is enough for the IDE, which shows a translated sentence for it. A tool that
reads the findings elsewhere (a code-scanning service, a CI log) needs the rest
said too: a name, how serious it is by default, what it means, what to do about
it and where to read more. A :class:`HeaderRule` is that, once per code.

The English sentence the IDE shows for a finding lives here as well
(:attr:`HeaderRule.message`); the English dictionary takes it from this table,
so the IDE and an exported report cannot say different things about one finding.

Nothing here holds a header's value: a rule is about a kind of finding.
"""
from __future__ import annotations

from dataclasses import dataclass

from pybreeze.utils.header_tools.header_analyzer import LEVEL_INFO, LEVEL_WARNING

# The language-dictionary key of a finding's sentence is this followed by the rule's id
HEADER_FINDING_KEY_PREFIX = "header_finding_"

_OWASP_HEADERS = "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html"
_OWASP_LOGGING = "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html"
_MDN_HEADERS = "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/"
_MDN_SET_COOKIE = _MDN_HEADERS + "Set-Cookie"
_MDN_CORS_ORIGIN = _MDN_HEADERS + "Access-Control-Allow-Origin"


@dataclass(frozen=True)
class HeaderRule:
    """One kind of header finding.

    :param id: the finding's code, which never changes once published
    :param name: the rule's name as one capitalised word, for tools that list rules
    :param level: how serious it is unless a finding says otherwise
        (``header_analyzer.LEVEL_WARNING`` or ``LEVEL_INFO``)
    :param summary: what the rule looks for, in one sentence
    :param message: the sentence for one finding, with ``{header}`` and ``{detail}`` to fill in
    :param remediation: what to do about it
    :param help_uri: where it is explained
    """

    id: str
    name: str
    level: str
    summary: str
    message: str
    remediation: str
    help_uri: str


_RULES = (
    HeaderRule(
        "duplicate_header", "DuplicateHeader", LEVEL_WARNING,
        "A header that is meant to appear once is sent more than once.",
        "{header}: sent {detail} times; the receiver joins the values into one.",
        "Send the header once. If several values are meant, write them as one comma-separated value.",
        "https://www.rfc-editor.org/rfc/rfc9110#section-5.3"),
    HeaderRule(
        "content_type_options_not_nosniff", "ContentTypeOptionsNotNosniff", LEVEL_WARNING,
        "X-Content-Type-Options is set to something other than nosniff.",
        "{header}: '{detail}' has no effect, only 'nosniff' stops MIME sniffing.",
        "Set X-Content-Type-Options: nosniff.",
        _MDN_HEADERS + "X-Content-Type-Options"),
    HeaderRule(
        "hsts_weak_max_age", "HstsWeakMaxAge", LEVEL_WARNING,
        "The Strict-Transport-Security policy expires too soon to protect a returning visitor.",
        "{header}: max-age={detail} is short; 15552000 (180 days) is the usual minimum.",
        "Raise max-age to at least 15552000, and add includeSubDomains once every subdomain serves HTTPS.",
        _MDN_HEADERS + "Strict-Transport-Security"),
    HeaderRule(
        "csp_unsafe_directive", "CspUnsafeDirective", LEVEL_WARNING,
        "The Content-Security-Policy allows inline scripts or eval.",
        "{header}: contains '{detail}', which re-allows what the policy should block.",
        "Remove 'unsafe-inline' and 'unsafe-eval'; allow the scripts that are needed with a nonce or a hash.",
        _MDN_HEADERS + "Content-Security-Policy"),
    HeaderRule(
        "cors_wildcard_origin", "CorsWildcardOrigin", LEVEL_INFO,
        "Access-Control-Allow-Origin allows every origin.",
        "{header}: every origin is allowed (*).",
        "Name the origins that need the resource, unless it is meant to be public.",
        _MDN_CORS_ORIGIN),
    HeaderRule(
        "cors_wildcard_with_credentials", "CorsWildcardWithCredentials", LEVEL_WARNING,
        "A wildcard origin is combined with Access-Control-Allow-Credentials: true.",
        "{header}: '*' with Access-Control-Allow-Credentials: true is rejected by browsers.",
        "Answer with the one origin that asked, checked against a list, instead of the wildcard.",
        _MDN_CORS_ORIGIN),
    HeaderRule(
        "cookie_not_secure", "CookieNotSecure", LEVEL_WARNING,
        "A cookie is set without the Secure attribute.",
        "{header}: cookie '{detail}' has no Secure attribute, so it can travel over plain HTTP.",
        "Add the Secure attribute to the cookie.",
        _MDN_SET_COOKIE),
    HeaderRule(
        "cookie_not_httponly", "CookieNotHttpOnly", LEVEL_WARNING,
        "A cookie is set without the HttpOnly attribute.",
        "{header}: cookie '{detail}' has no HttpOnly attribute, so scripts can read it.",
        "Add the HttpOnly attribute, unless a script of the page has to read the cookie.",
        _MDN_SET_COOKIE),
    HeaderRule(
        "cookie_no_samesite", "CookieNoSameSite", LEVEL_INFO,
        "A cookie is set without a SameSite attribute.",
        "{header}: cookie '{detail}' has no SameSite attribute; browsers default it to Lax.",
        "Say which is meant: SameSite=Strict, Lax, or None together with Secure.",
        _MDN_SET_COOKIE),
    HeaderRule(
        "cookie_prefix_rejected", "CookiePrefixRejected", LEVEL_WARNING,
        "A cookie's name has a prefix whose rules its attributes break, so browsers drop it.",
        "{header}: cookie '{detail}' breaks its prefix's rules (__Secure- needs Secure; __Host- needs "
        "Secure, Path=/ and no Domain), so browsers drop it.",
        "Give the cookie what its prefix requires, or rename it without the prefix.",
        _MDN_SET_COOKIE),
    HeaderRule(
        "cookie_samesite_none_not_secure", "CookieSameSiteNoneNotSecure", LEVEL_WARNING,
        "A cookie is SameSite=None without Secure, so browsers drop it.",
        "{header}: cookie '{detail}' is SameSite=None without Secure, so browsers drop it.",
        "Add the Secure attribute, or choose SameSite=Lax or Strict.",
        _MDN_SET_COOKIE),
    HeaderRule(
        "content_type_no_charset", "ContentTypeNoCharset", LEVEL_INFO,
        "A textual Content-Type names no charset.",
        "{header}: '{detail}' names no charset, so the client has to guess the encoding.",
        "Add the charset, for example Content-Type: text/html; charset=utf-8.",
        _MDN_HEADERS + "Content-Type"),
    HeaderRule(
        "server_banner", "ServerBanner", LEVEL_INFO,
        "A header names the software that answered.",
        "{header}: '{detail}' reveals the software in use.",
        "Remove the header, or set it to a value that names no product or version.",
        _OWASP_HEADERS),
    HeaderRule(
        "deprecated_header", "DeprecatedHeader", LEVEL_INFO,
        "A header that current browsers ignore is still sent.",
        "{header}: '{detail}' is deprecated and ignored by current browsers.",
        "Remove the header and use what replaced it (a Content-Security-Policy for the old XSS and CSP headers).",
        _OWASP_HEADERS),
    HeaderRule(
        "sensitive_header", "SensitiveHeader", LEVEL_INFO,
        "A header carries a credential.",
        "{header}: carries a credential; mask it before sharing this output.",
        "Mask or remove the value before the headers are shared, logged or committed.",
        _OWASP_LOGGING),
    HeaderRule(
        "missing_hsts", "MissingHsts", LEVEL_INFO,
        "A response sets no Strict-Transport-Security policy.",
        "{header}: not set, so a browser may fall back to plain HTTP.",
        "Send Strict-Transport-Security: max-age=15552000; includeSubDomains on HTTPS responses.",
        _MDN_HEADERS + "Strict-Transport-Security"),
    HeaderRule(
        "missing_csp", "MissingCsp", LEVEL_INFO,
        "A response sets no Content-Security-Policy.",
        "{header}: not set, so nothing limits where scripts may be loaded from.",
        "Send a Content-Security-Policy that names where scripts, styles and frames may come from.",
        _MDN_HEADERS + "Content-Security-Policy"),
    HeaderRule(
        "missing_content_type_options", "MissingContentTypeOptions", LEVEL_INFO,
        "A response sets no X-Content-Type-Options.",
        "{header}: not set, so a browser may MIME-sniff the response.",
        "Send X-Content-Type-Options: nosniff.",
        _MDN_HEADERS + "X-Content-Type-Options"),
    HeaderRule(
        "missing_frame_options", "MissingFrameOptions", LEVEL_INFO,
        "A response says neither X-Frame-Options nor a CSP frame-ancestors directive.",
        "{header}: not set; it (or CSP frame-ancestors) controls who may frame the page.",
        "Send Content-Security-Policy: frame-ancestors 'none' (or the origins allowed to frame the page).",
        _MDN_HEADERS + "X-Frame-Options"),
    HeaderRule(
        "missing_referrer_policy", "MissingReferrerPolicy", LEVEL_INFO,
        "A response sets no Referrer-Policy.",
        "{header}: not set, so full URLs may leak to other sites.",
        "Send Referrer-Policy: strict-origin-when-cross-origin, or no-referrer.",
        _MDN_HEADERS + "Referrer-Policy"),
)

# Every rule by its id, in the order above
RULES: dict[str, HeaderRule] = {rule.id: rule for rule in _RULES}
