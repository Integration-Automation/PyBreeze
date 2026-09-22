# PyBreeze Plugin Guide / 插件開發指南

PyBreeze is built on JEditor and uses its plugin system unchanged: the `je_editor.plugins` API
(`register_programming_language`, `register_natural_language`, `PLUGIN_RUN_CONFIG`), the
`jeditor_plugins/` directory and the *Plugins → Plugin Browser* menu. There is therefore one guide
for both editors, kept in the JEditor repository:

**→ [JEditor `PLUGIN_GUIDE.md`](https://github.com/Integration-Automation/JEDITOR/blob/main/PLUGIN_GUIDE.md)**

Ready-made plugins (C, C++, Go, Java and Rust highlighting with run support, a French UI
translation) live in [IDE_Plugins](https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins).

---

PyBreeze 建立在 JEditor 之上，原封不動地使用它的插件系統：`je_editor.plugins` API
（`register_programming_language`、`register_natural_language`、`PLUGIN_RUN_CONFIG`）、
`jeditor_plugins/` 目錄，以及 *插件 → Plugin Browser* 選單。所以兩個編輯器共用一份指南，放在 JEditor repo：

**→ [JEditor `PLUGIN_GUIDE.md`](https://github.com/Integration-Automation/JEDITOR/blob/main/PLUGIN_GUIDE.md)**

現成的插件（C、C++、Go、Java、Rust 語法高亮與執行設定，以及法文介面翻譯）放在
[IDE_Plugins](https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins)。
