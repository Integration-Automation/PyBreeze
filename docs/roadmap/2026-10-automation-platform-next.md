# PyBreeze Automation Platform Roadmap

> Draft implementation plan for the next major PyBreeze evolution. This PR establishes the architecture and delivery order; feature work should land as smaller reviewable PRs.

## Goals
1. Modernise the PyBreeze UI without forking the JEditor editor core.
2. Make Windows, macOS and Linux first-class CI/test targets.
3. Turn cURL/HAR import into a reusable request-to-target pipeline, including WebRunner.
4. Standardise diagnostics, language services, MCP and execution reports around reusable contracts.
5. Align i18n with the actually supported language set.
6. Provide a complete onboarding/tutorial path.

## Current baseline
- PySide6 + JEditor desktop/editor foundation.
- Separate process executors for APITestka, AutoControl, WebRunner and LoadDensity.
- Existing cURL and HAR import tools with code generation.
- Existing Header Analyzer and JSON formatting tools.
- English and Traditional Chinese PyBreeze dictionaries with parity tests.
- Existing HTML / JSON / XML execution reports.
- Existing Sphinx documentation and architecture documents.

The plan extends these seams rather than replacing working subsystems.

## Phase 0 — Architecture contracts and CI foundation
Objective: establish contracts all later phases can depend on.
- [ ] Define a shared TargetDescriptor / import-target registry for generated automation targets.
- [ ] Define an ExecutionResult / ExecutionReport schema independent of any framework.
- [ ] Define a language-service adapter contract for AutoControl, WebRunner and LoadDensity.
- [ ] Define JSON document/editor model boundaries so the visual editor can coexist with text editing.
- [ ] Extend CI from Windows to macOS and Linux.
- [ ] Add platform smoke tests for startup, subprocess execution, filesystem paths and headless Qt.
- [ ] Add architecture decision records for the shared contracts.
Exit: CI covers Windows + macOS + Linux; shared schemas are unit-tested; existing Windows tests remain green.

## Phase 1 — UI redesign
Objective: modernise the shell while preserving existing actions and shortcuts.
- [ ] Establish a design system: spacing, typography, icon sizing, states and reusable panels.
- [ ] Introduce navigation for Automation, Tools, MCP, Reports and Settings.
- [ ] Make tool tabs/docks consume registration metadata instead of bespoke menu wiring.
- [ ] Add responsive layouts for small screens and high-DPI displays.
- [ ] Preserve existing menu actions and shortcuts during migration.
- [ ] Add UI smoke/visual coverage for the main shell.
Rule: UI consumes service/registry APIs; business logic stays in utils, executors and framework adapters.

## Phase 2 — cURL/HAR import + WebRunner
Objective: make capture/import a reusable pipeline and add WebRunner as a first-class target.
- [ ] Refactor cURL and HAR parsers around a common normalized request model.
- [ ] Add target registration so generation is capability-driven rather than hard-coded in UI branches.
- [ ] Add WebRunner target generation for cURL and HAR.
- [ ] Map HTTP request data to browser navigation/action semantics where possible.
- [ ] Report fields that cannot be represented by WebRunner instead of silently dropping them.
- [ ] Add fixtures and round-trip tests for cURL, HAR and every target.
- [ ] Keep parsing/generation pure; imports must never replay captured requests.
Targets: requests/pytest, APITestka, LoadDensity and WebRunner.

## Phase 3 — Header Analyzer → SARIF
Objective: make findings consumable by security tooling and CI.
- [ ] Define a stable finding model: rule ID, level, message, location, help URI and remediation.
- [ ] Keep existing human-readable UI output.
- [ ] Add SARIF 2.1.0 serialization.
- [ ] Support file and stdout output with deterministic ordering.
- [ ] Add tests for SARIF schema expectations and GitHub Code Scanning-compatible fields.
- [ ] Expose export from the UI and a reusable Python API.
Security: credential-bearing header values stay redacted; SARIF must never become a secret-exfiltration path.

## Phase 4 — i18n alignment
Objective: make language support explicit and consistent.
- [ ] Enumerate languages supplied by PyBreeze and JEditor separately.
- [ ] Define ownership: PyBreeze owns its strings; JEditor owns editor-core strings.
- [ ] Ensure language keys and display names are stable and correctly registered.
- [ ] Keep dictionary parity enforced for every built-in PyBreeze language.
- [ ] Decide which languages are officially supported versus merely exposed by JEditor.
- [ ] Add an automated supported-language manifest/check.
- [ ] Update README and translated README files together when the supported set changes.
Proposed initial set: English + Traditional Chinese remain the PyBreeze-maintained dictionaries until additional translations meet parity and documentation requirements.

## Phase 5 — Visual JSON editor
Objective: provide structured editing without removing the raw JSON escape hatch.
- [ ] Build a model for object, array, scalar and null nodes.
- [ ] Add tree/form navigation and editing.
- [ ] Add insert, delete, reorder and rename operations.
- [ ] Preserve formatting/options through explicit serialization.
- [ ] Validate continuously without blocking editing.
- [ ] Add undo/redo and dirty-state integration.
- [ ] Support safe Visual ↔ Text switching with conflict-safe synchronization.
- [ ] Reuse existing safe JSON-view utilities.
Non-goal: replacing the general code editor.

## Phase 6 — LSP for AutoControl / WebRunner / LoadDensity
Objective: give the three frameworks one consistent language-service experience.
- [ ] Define a common LSP-facing capability contract.
- [ ] Start with completion and diagnostics.
- [ ] Add hover/documentation and go-to-definition where metadata permits.
- [ ] Source schemas/keyword metadata from installed framework packages instead of duplicating it in the UI.
- [ ] Add version-aware capability discovery.
- [ ] Isolate language services so framework failures cannot crash the IDE.
- [ ] Add protocol fixture tests independent of Qt.
Rollout: WebRunner → AutoControl → LoadDensity.

## Phase 7 — MCP client tab
Objective: make MCP a first-class IDE integration surface.
- [ ] Define MCP connection/profile model with per-user persistence.
- [ ] Add a client tab for server discovery, connection status, tools, resources and prompts.
- [ ] Add permission/confirmation UI before side-effecting tool calls.
- [ ] Stream calls and results into the unified execution model.
- [ ] Redact secrets and sensitive arguments in logs/reports.
- [ ] Support reconnect, timeout and cancellation.
- [ ] Keep transport/client logic independent of Qt.

## Phase 8 — Unified execution report viewer
Objective: one report experience for all automation frameworks.
- [ ] Normalize framework outputs into ExecutionResult.
- [ ] Capture suite/test/case/step status, timing, stdout/stderr, attachments and errors.
- [ ] Preserve framework-specific raw output as an expandable payload.
- [ ] Build one viewer with summary, hierarchy, details and artifacts.
- [ ] Support HTML/JSON/XML import/export through adapters.
- [ ] Add filtering by status, duration, framework and failure.
- [ ] Add stable IDs so future report comparison does not require a redesign.
- [ ] Integrate MCP results and future LSP diagnostics where appropriate.

## Phase 9 — Complete tutorials
Objective: turn existing docs into a progressive learning path.
- [ ] Installation and first launch.
- [ ] First API test with APITestka.
- [ ] First browser test with WebRunner.
- [ ] First desktop automation with AutoControl.
- [ ] First load scenario with LoadDensity.
- [ ] cURL → test and HAR → suite workflows.
- [ ] Header Analyzer → SARIF in CI.
- [ ] Visual JSON editing.
- [ ] LSP workflow.
- [ ] MCP client workflow.
- [ ] Unified reports and CI consumption.
- [ ] Plugin/developer guide.
- [ ] Troubleshooting and platform-specific setup.
Each tutorial should include a runnable minimal example and expected result.

## Cross-cutting quality gates
- ruff remains clean.
- Existing unit/startup coverage is preserved and expanded for changed surfaces.
- Windows/macOS/Linux CI coverage is mandatory after Phase 0.
- No UI mutation from worker threads.
- Existing SSRF, secret-redaction and subprocess hardening remains intact.
- Architecture docs are updated whenever boundaries or extension points change.
- README and translated README parity is maintained for user-visible changes.
- No untracked TODO/FIXME without an issue reference.

## Dependency map
CI + shared contracts → UI redesign
CI + shared contracts → import/target registry → WebRunner import
Shared contracts → JSON model → visual editor
Shared contracts → language-service adapters → LSP rollout
Shared execution model → MCP → unified reports
Unified reports + all shipped features → complete tutorials

## Suggested PR slicing
1. Draft roadmap / architecture contracts — this PR.
2. CI: macOS + Linux matrix and platform smoke tests.
3. Core: normalized execution result + target registry.
4. UI: navigation shell and design system.
5. Import: WebRunner target for cURL/HAR.
6. Security: SARIF output for Header Analyzer.
7. i18n: supported-language manifest and parity.
8. Editor: visual JSON model/editor.
9. Language services: WebRunner → AutoControl → LoadDensity.
10. Integration: MCP client tab.
11. Reports: unified viewer and adapters.
12. Docs: complete tutorials.
Large UI/editor/LSP features should not be combined into one implementation PR.

## Risks and proposed decisions
| Topic | Risk | Proposed decision |
| --- | --- | --- |
| JEditor boundary | UI redesign forks editor behavior | Keep JEditor as editor core; PyBreeze owns shell/navigation |
| LSP scope | Framework metadata differs | Common minimum contract + optional capabilities |
| WebRunner import | HTTP request is not always a browser action | Generate representable actions and report explicit gaps |
| Reports | Framework outputs differ | Stable common core + raw framework payload |
| i18n | JEditor and PyBreeze languages diverge | Separate ownership + supported manifest |
| MCP | Tool calls may have side effects | Explicit confirmation + cancellation |
| JSON editor | Visual/text edits can conflict | One document model + explicit serialization boundary |
| CI | GUI dependencies vary by OS | Headless tests first; platform GUI smoke tests second |

## Definition of done
The roadmap is complete when every requested capability has a named phase, cross-feature contracts are explicit, every phase has testable exit criteria, dependencies and PR boundaries are documented, and the work can proceed incrementally without a monolithic rewrite.