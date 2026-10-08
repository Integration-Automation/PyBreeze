# 0005. The shell gets a navigation panel that mirrors the menus, and panels are sized in ems

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/pybreeze_ui/navigation/`, `pybreeze/pybreeze_ui/design/`,
  `pybreeze/pybreeze_ui/menu/tools/tools_menu.py` (`TOOLS`), `pybreeze/utils/ui_state.py`;
  `test_navigation.py`, `test_design_system.py`, `test_tools_fit_small_screens.py`, `test_ui_state.py`

## Context

The roadmap's Phase 1 asks for a modern shell without forking the editor core: a design system,
navigation for Automation, Tools, MCP, Reports and Settings, tools registered by metadata instead of
bespoke menu wiring, layouts that fit small screens and dense displays, and every existing menu
entry and shortcut kept.

Three things stood in the way:

- Everything PyBreeze adds is reached through menus up to four levels deep
  (Automation ▸ APITestka ▸ Run ▸ ...). A menu shows nothing until it is opened and cannot be
  searched.
- A tool was a row in four tables of `tools_menu.py`, as an import target had been a row in three
  (0001).
- Each panel chose its own pixels. Three tool tabs asked for more width than a 1280-pixel display
  has (1382, 1176 and 994 pixels with a 12-pixel font), because a row of buttons side by side is as
  wide as all of them.

## Decision

1. **The navigation panel shows what the menus hold; it defines nothing.** A dock at the left lists
   five categories as one tree. Automation and Settings are read from the menus themselves; Tools,
   MCP and Reports from the tool descriptors. Choosing a line triggers the action the menu entry
   triggers, so the panel cannot offer what the menus do not, or do it differently.
2. **A category with nothing in it is not listed.** MCP and Reports appear when a tool of that
   category is registered.
3. **The panel can be searched.** Typing keeps the lines that hold the text, with the lines they
   are under; a category's own title is not searched, since "Tools" would then list every tool.
4. **One descriptor per tool.** `ToolDescriptor` holds a tool's factory, the stem of its four
   language keys, its submenu and its navigation category. The Tools menu, the Dock menu and the
   panel are built from the one table `TOOLS`.
5. **Sizes are counted in ems.** `design/tokens.py` gives gaps, text sizes and icon sizes as
   multiples of the height of the font in use, and a state's colour as one of the theme's. A tool
   opened from a menu gets the standard gaps around its content in one place.
6. **A row that may be long wraps.** `FlowLayout` starts a new line when the next control does not
   fit, so a panel's least width is that of its widest control. A test holds every tool to 60 ems
   of width and 30 of height.
7. **Whether the panel is shown is remembered only when the user says so**: its entry in the Dock
   menu, or its own close button. It is kept in `~/.pybreeze/ui_state.json`.

## Alternatives considered

- **A side bar of icons with pages (the "activity bar" of other IDEs).** It needs an icon per area
  and a page per area, and would put a second, different list of functions beside the menus. A
  tree that mirrors the menus needs neither and cannot drift from them.
- **Replace the menus with the panel.** The roadmap keeps every menu entry and shortcut, and a
  menu bar is where a user of a desktop IDE looks first.
- **Wrap each tool in a scroll area for small screens.** A tab's page would then be the scroll
  area, not the tool: `may_close()`, the tab-closing code and forty tests look at the page itself.
  Rows that wrap fix the cause instead of scrolling past it.
- **Ask `QAction.menu()` for an entry's submenu.** Under PySide6 6.11.0 the object it returns takes
  the menu with it when it is dropped, which is what fails 11 menu tests on that release. The
  submenus are found through `findChildren(QMenu)` and each menu's `menuAction()`, which reads a
  menu and leaves it as it was on every release.
- **Remember the panel's visibility from the dock's own signal.** The Dock menu entry's checked
  state also changes as the IDE closes, so every exit would have recorded the panel as hidden.

## Consequences

- A new tool is one `_tool(...)` line in `TOOLS`; it is in the Tools menu, the Dock menu and the
  navigation panel at once. `test_language_keys_used.py` reads a tool's four words from that line.
- A new panel takes its gaps and fonts from `design/tokens.py` and builds a long row with
  `wrapping_row()`; `Panel` and `StatusLine` are there for a titled group and a one-line result.
  The phases that add tabs (MCP, reports, the JSON editor) use them.
- The existing tool tabs keep their own layouts. Only the gaps around their content and the three
  rows that were too wide changed; restyling each tab is not part of this.
- The main window itself still asks for about 1770 pixels of width at a 12-pixel font, all of it
  from JEditor's Git panel inside the editor tab. That is the editor core's to change
  (`progress.md` #126).
- The panel depends on three things of JEditor's: its `language_menu` and `venv_menu` attributes
  and the `style_menu_label` word that titles its UI Style menu (`architecture.md` §6). One it does
  not find is left out of Settings; nothing fails.
