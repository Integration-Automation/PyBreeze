# docs/adr: architecture decision records

Why the shared contracts are shaped as they are. Each record says what was decided, what it was
decided against, and what follows from it.

They are reference material. A rule that follows from a decision is stated in `CLAUDE.md`; what a
module does is in `architecture_explore.md`; what changed and when is in `docs/updates/`.

| No. | Decision | Status | Roadmap phases that build on it |
|---|---|---|---|
| [0001](0001-import-target-registry.md) | Import targets are described once, in a registry | Accepted | 2 |
| [0002](0002-execution-report-schema.md) | A run is reported in one schema, the framework's own record kept beside it | Accepted | 7, 8 |
| [0003](0003-json-document-boundary.md) | A JSON file is one document: its text is the truth, its tree is read from it | Accepted | 5 |
| [0004](0004-language-service-adapter.md) | Language features are asked through one adapter contract, behind a guard | Accepted | 6 |
| [0005](0005-navigation-and-design-system.md) | The shell gets a navigation panel that mirrors the menus, and panels are sized in ems | Accepted | 1 (and the tabs of 5, 7, 8) |
| [0006](0006-webrunner-import-target.md) | A captured request becomes a browser visit, and what a visit cannot carry is said | Accepted | 2 |
| [0007](0007-header-findings-as-sarif.md) | A header finding has a rule, and the findings are exported as SARIF | Accepted | 3 |
| [0008](0008-supported-languages.md) | PyBreeze supports the languages it maintains, and passes the editor's others on | Accepted | 4 |
| [0009](0009-visual-json-editor.md) | The JSON editor is two views of one document, with one history | Accepted | 5 |
| [0010](0010-action-language-server.md) | One language server for the three frameworks' action scripts, fed by the installed packages | Accepted | 6 |
| [0011](0011-mcp-client.md) | An MCP client that asks before every call, over the standard transport only | Accepted | 7 |

"Roadmap" is the automation platform roadmap of pull request #141
(`docs/roadmap/2026-10-automation-platform-next.md`); 0001 to 0004 are its Phase 0 contracts, and the
later records belong to the phase their last column names.

## Format

```markdown
# NNNN. The decision, as a sentence

- **Status**: Accepted | Superseded by NNNN
- **Date**: YYYY-MM-DD
- **Code**: where it is implemented and tested

## Context
What made a decision necessary.

## Decision
What was decided, numbered so that a later record can name one point.

## Alternatives considered
What else was weighed, and why it lost.

## Consequences
What this makes easy, what it costs, and what it leaves to a later phase.
```

A record is "Accepted" from the merge of the change that adds it.
