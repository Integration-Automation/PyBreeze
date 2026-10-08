# 0008. PyBreeze supports the languages it maintains, and passes the editor's others on

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/extend_multi_language/supported_languages.py`, `update_language_dict.py`;
  `test_supported_languages.py`

## Context

The Language menu belongs to JEditor and lists every language JEditor knows: English, Traditional
Chinese, Simplified Chinese and Japanese, and any language a translation plugin registers. PyBreeze
adds its own strings for two of them. Picked, either of the other two changes the editor's own
menus and leaves PyBreeze's in English.

Nothing said so. Which languages PyBreeze translated was a matter of which dictionary files
existed and which two functions `update_language_dict()` happened to call; the README described the
result in a sentence. The roadmap's Phase 4 asks for the languages to be listed by who supplies
them, for ownership to be defined, for a decision on what is supported, and for a check that keeps
the list and the documents honest.

## Decision

1. **Supported means maintained.** PyBreeze supports the languages it translates every one of its
   strings into: English and Traditional Chinese. `MAINTAINED` lists them, with the name the menu
   shows and the dictionary.
2. **The editor's other languages are passed on, and said to be.** `EDITOR_ONLY` lists Japanese and
   Simplified Chinese. They stay in the menu; PyBreeze's strings in them are English; a string
   untranslated there is not a defect of PyBreeze.
3. **A string belongs to whoever defines its key.** JEditor's keys are JEditor's in every language,
   PyBreeze's are PyBreeze's. The two overlap in three places only, named in
   `REWORDED_JEDITOR_KEYS`: the application's name, and the plugin browser and Plugins menu, which
   PyBreeze words its own way in the languages it maintains.
4. **The list is what is merged.** `update_language_dict()` adds each maintained language's strings
   to JEditor's dictionary of that key. The two dictionary modules hold strings and import nothing
   of the editor.
5. **Every language JEditor offers has to be placed.** A test reads JEditor's own list and fails
   when a language is in neither `MAINTAINED` nor `EDITOR_ONLY`.
6. **A language joins `MAINTAINED` whole or not at all**: every key, the README's three versions
   naming it, and the checks that hold for the others (`test_language_parity.py`).

## Alternatives considered

- **Hide the languages PyBreeze does not translate.** They are the editor's and they work for the
  editor's own menus; removing them from a menu PyBreeze does not own would take something from a
  user who reads Japanese and can live with English tool names.
- **Translate them by machine to close the gap.** The Traditional Chinese dictionary is held to
  Taiwan's terms and to full-width punctuation by tests written from real corrections. Text nobody
  who reads the language has checked would not meet that, and would be presented as supported.
- **Override JEditor's wording where it differs from PyBreeze's** (the Run menu's 運行 beside
  PyBreeze's 執行, `progress.md` #108). It would copy JEditor's entries into PyBreeze's dictionaries
  and make PyBreeze answerable for them. The wording is JEditor's to change; the three overlaps
  above are the ones PyBreeze shows as its own.
- **Mark the passed-on languages in the menu.** A tooltip or a suffix would have to be put on
  actions JEditor builds, in a menu that would then show a tooltip on every entry. The README says
  it instead.
- **Let a missing dictionary fail the start.** If JEditor ever drops a language PyBreeze maintains,
  the IDE logs it and starts in the languages that are left.

## Consequences

- Adding a language is: its dictionary with every key, a `MaintainedLanguage` line, and the three
  READMEs. The parity test then covers it without being told, since it compares every maintained
  dictionary with the first.
- A JEditor release that adds a language fails `test_supported_languages.py` until the language is
  placed. That is the point: the decision is made when the language appears, not found out later.
- The READMEs name each language as the menu shows it (English, 繁體中文, 日本語, 简体中文), and a
  test holds the three files to the list.
- A translation plugin's language is neither maintained nor the editor's; `who_translates()` calls
  its owner the plugin.
