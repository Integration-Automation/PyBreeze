# 0006. A captured request becomes a browser visit, and what a visit cannot carry is said

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/import_targets/` (`normalized_request.py`, `webrunner_target.py`,
  `target_registry.py`, `builtin_targets.py`), `pybreeze/pybreeze_ui/tools_gui/import_gaps.py`;
  `test_webrunner_target.py`, `test_import_round_trip.py`, `test_import_gaps.py`

## Context

The roadmap's Phase 2 adds WebRunner as a target of the cURL and HAR importers, and asks for three
things with it: a normalized request model both importers produce, HTTP data mapped to browser
semantics "where possible", and the fields a target cannot represent reported instead of dropped.

WebRunner drives a browser. A browser does not send a request someone wrote: it goes to an address
with headers of its own and the cookies it holds for that site. Most of a captured request has no
counterpart in WebRunner's actions.

## Decision

1. **A request is normalized once.** `normalize()` turns the record of a parse (`CurlRequest`, which
   both parsers fill) into a `NormalizedRequest`: the method, the whole URL, the headers and
   cookies that go out, one payload of one kind, the credentials and the time limit. It is
   immutable and holds nothing that is curl's or HAR's.
2. **A visit carries the address, the cookies and a time limit.** The WebRunner target writes
   `WR_get_webdriver_manager`, then for each request `WR_to_url` with the whole URL, and `WR_quit`.
   Cookies are set with `WR_add_cookie` after the first visit, since a browser takes a cookie only
   for the page it is on, and the page is then loaded again so that they are sent. A time limit
   becomes `WR_set_page_load_timeout`, in whole seconds, rounded up.
3. **Everything else is declared as not carried.** The target's `carries` holds cookies and the
   time limit only. The method is a request part now (`RequestPart.METHOD`, a method other than
   `GET`), because a visit is always a `GET`; every other target carries it.
4. **Both tabs say what the chosen target leaves out.** Under the output, a line names the parts the
   requests have and the target does not send ("Not sent by this target: headers · the body"), for
   every target: it also says what LoadDensity always left out.
5. **The request is still visited when parts are left out.** A `POST` becomes a visit to its URL
   with the line above it, rather than no output at all.
6. **A script is generated for one browser, Chrome, in one list.** A session is one browser that
   visits each address in capture order.

## Alternatives considered

- **Send what a visit cannot carry through `WR_execute_script` and `fetch()`.** It would carry a
  method, headers and a body, but as a script running in the page, bound by the page's origin and
  CORS: not the captured request, and not what a WebRunner test of a page is for.
- **Put basic-auth credentials in the URL (`https://user:password@host`).** Browsers restrict or
  drop them, and a password would be written into an address that is logged and shown.
- **Refuse a request that is not a plain `GET`.** A recorded session is mostly not plain `GET`s; the
  target would be of no use on a HAR export.
- **Rewrite the four earlier generators against `NormalizedRequest`.** They read the parse record
  through the same helpers `normalize()` is built from, so the two cannot disagree, and their
  several hundred tests call them with a parse record. Moving them is possible and was not needed
  for this.
- **Report the gaps inside the generated file.** JSON has no comments, and a comment in a Python
  script is read after the script has been saved and run.

## Consequences

- A target written from now on takes a `NormalizedRequest` and needs to know neither parser.
- `test_import_round_trip.py` reads every target's output back: a Python script is run against
  stand-ins for `requests`, `je_api_testka` and `je_load_density` that record the call instead of
  making it, and what was asked for is compared with the request in the fixture
  (`test/test_utils/fixtures/import/`).
- Nothing in `curl_import/`, `har_import/` or `import_targets/` may import a package that could
  send a request; the same test fails on one (`CLAUDE.md`, Security).
- The generated list starts Chrome. Another browser is one word to change in the output; a
  setting for it would be a setting of the IDE, which nothing else about the importers is.
- The line under the output names parts, not values: it says "headers", never which.
