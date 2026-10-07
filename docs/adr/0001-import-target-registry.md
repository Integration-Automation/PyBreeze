# 0001. Import targets are described once, in a registry

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/import_targets/` (`target_registry.py`, `builtin_targets.py`),
  `test/test_utils/test_import_targets.py`

## Context

The cURL and HAR importers parse what was captured into a `CurlRequest` and then generate it for a
*target*: a `requests` script, a pytest test, an APITestka call or JSON action list, a LoadDensity
run. What the IDE knew about a target was spread over four places keyed by the same string:

- `TEMPLATE_TARGETS` in `script_templates.py`: the key and the label's language key;
- `_GENERATORS` in `script_templates.py`: the generator for one request;
- `_BATCH_GENERATORS` in `har_codegen.py`: the generator for several;
- a `_JSON_TARGET` constant in each of the two tabs, to know which target writes JSON and so what
  a saved file is called.

Nothing tied the four together, and a new target meant editing two modules in `utils/` and both
tabs. The roadmap's Phase 2 adds a WebRunner target, which cannot express everything an HTTP request
holds, and asks that what a target cannot carry be reported instead of silently dropped. That was
already happening: LoadDensity's output sends only a method and a URL, and only a comment in the
generated script said so.

## Decision

1. **One description per target.** A `TargetDescriptor` holds a target's key, the language key of
   its label, the extension and suggested names of its output, its generator for one request and
   its generator for several, and the request parts its output sends (`carries`).
2. **One registry.** `ImportTargetRegistry` keeps the descriptors in registration order;
   `IMPORT_TARGETS` is the one the importers read. The first target registered is the default, and
   an unknown key gets it, as `generate_template()` and `generate_har_script()` gave an unknown key
   the `requests` script.
3. **The tabs read the registry and name no target.** What to list, how to generate and what to
   call a saved file all come from the selected descriptor.
4. **A target declares what it carries, and the declaration is tested.** `RequestPart` lists the
   parts not every target can write. `carries` is the set a target's output sends, and
   `unrepresented(request)` gives the parts of a request it leaves out. One test checks, for every
   target and every part, that the generator writes the part exactly when the descriptor says so.
5. **What is carried is listed, not what is missing.** A part added to `RequestPart` later is
   unrepresented by every target until someone adds it to a `carries`, so a forgotten declaration
   errs towards telling the user rather than towards silence.
6. **The request model stays `CurlRequest`.** Both importers already produce it. Phase 2 may
   generalise it; the generator signatures on the descriptor are then the one place that changes.

## Alternatives considered

- **Keep the tables and add one for the extension.** Each new attribute would be another table
  keyed by a string, with nothing to say they agree.
- **Discover targets through entry points or the plugin loader.** Nothing outside the package
  provides a target today. The registry is an object anything can call `register()` on, so
  discovery can be added later without changing this contract.
- **Have a generator return its gaps with its output.** The gaps would be known only after
  generating, each generator would work them out its own way, and a target that refuses a request
  (the JSON action, for a file upload) would report nothing at all. A declaration can be asked
  before generating and checked by one test.
- **Raise on an unknown key.** More usual for a registry, but it would change what the tabs do
  today, and this change was meant to move no behaviour.

## Consequences

- A new target is one `TargetDescriptor` in `builtin_targets.py`. `test_import_targets.py` fails
  when its `carries` is not what its generators write, and when a file in `tools_gui/` names a
  target by its key (`CLAUDE.md`, Conventions).
- `generate_template()` and `generate_har_script()` are gone; `IMPORT_TARGETS.generate(key,
  requests)` writes one request in the single form and several in the batch form, so the two tabs
  cannot disagree about one request.
- Registering a key twice raises: replacing a target is not supported.
- Nothing shows a user the unrepresented parts yet. Phase 2 adds that to the tabs, and the
  WebRunner target with it.
- A generator that leaves a part out and one that refuses the request both count as "not carried".
  Which of the two a target does is not part of the contract.
