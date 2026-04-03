# PyBreeze Plugin Guide / 插件開發指南

PyBreeze (jeditor) supports external plugins for adding **syntax highlighting** and **UI translations**.

PyBreeze (jeditor) 支援外部插件，可用於新增**語法高亮**和 **UI 翻譯**。

---

## Quick Start / 快速開始

1. Create a `.py` file in the `jeditor_plugins/` directory (under your working directory).
2. Define a `register()` function.
3. Optionally define `PLUGIN_NAME`, `PLUGIN_AUTHOR`, `PLUGIN_VERSION` for the Plugins menu.

<!-- -->

1. 在工作目錄下的 `jeditor_plugins/` 建立一個 `.py` 檔案。
2. 定義一個 `register()` 函式。
3. 可選：定義 `PLUGIN_NAME`、`PLUGIN_AUTHOR`、`PLUGIN_VERSION`，會顯示在插件選單中。

---

## Plugin Metadata / 插件元資料

```python
PLUGIN_NAME = "My Plugin"       # Display name in the Plugins menu / 插件選單顯示名稱
PLUGIN_AUTHOR = "Your Name"     # Author / 作者
PLUGIN_VERSION = "1.0.0"        # Version / 版本號
```

All three are optional. If omitted, the filename is used as the plugin name.

三者皆為可選。若未定義，則以檔名作為插件名稱。

---

## Syntax Highlighting Plugin / 語法高亮插件

Use `register_programming_language()` to add syntax highlighting for file types.

使用 `register_programming_language()` 為檔案類型新增語法高亮。

### API

```python
from je_editor.plugins import register_programming_language

register_programming_language(
    suffix=".ext",              # File extension / 副檔名
    syntax_words={...},         # Keyword groups / 關鍵字群組
    syntax_rules={...},         # Regex rules (optional) / 正則規則（可選）
)
```

### syntax_words format / syntax_words 格式

```python
from PySide6.QtGui import QColor

syntax_words = {
    "group_name": {
        "words": ("keyword1", "keyword2", ...),   # Tuple or set of keywords / 關鍵字元組或集合
        "color": QColor(r, g, b),                  # Highlight color / 高亮顏色
    },
    # More groups...
}
```

### syntax_rules format / syntax_rules 格式

```python
syntax_rules = {
    "rule_name": {
        "rules": (r"regex_pattern", ...),   # Tuple of regex patterns / 正則表達式元組
        "color": QColor(r, g, b),           # Highlight color / 高亮顏色
    },
}
```

### Full Example / 完整範例

```python
"""Go syntax highlighting plugin."""
from PySide6.QtGui import QColor
from je_editor.plugins import register_programming_language

PLUGIN_NAME = "Go Syntax Highlighting"
PLUGIN_AUTHOR = "Your Name"
PLUGIN_VERSION = "1.0.0"

go_syntax_words = {
    "keywords": {
        "words": (
            "break", "case", "chan", "const", "continue",
            "default", "defer", "else", "fallthrough", "for",
            "func", "go", "goto", "if", "import",
            "interface", "map", "package", "range", "return",
            "select", "struct", "switch", "type", "var",
        ),
        "color": QColor(86, 156, 214),
    },
    "types": {
        "words": (
            "bool", "byte", "complex64", "complex128",
            "float32", "float64", "int", "int8", "int16",
            "int32", "int64", "rune", "string", "uint",
            "uint8", "uint16", "uint32", "uint64", "uintptr",
            "error", "nil", "true", "false", "iota",
        ),
        "color": QColor(78, 201, 176),
    },
}

go_syntax_rules = {
    "single_line_comment": {
        "rules": (r"//[^\n]*",),
        "color": QColor(106, 153, 85),
    },
}


def register() -> None:
    register_programming_language(
        suffix=".go",
        syntax_words=go_syntax_words,
        syntax_rules=go_syntax_rules,
    )
```

### Multiple Suffixes / 多個副檔名

If a language uses multiple file extensions, register each suffix with the same `syntax_words`:

若一個語言使用多個副檔名，用相同的 `syntax_words` 分別註冊每個副檔名：

```python
def register() -> None:
    for suffix in (".cpp", ".cxx", ".cc", ".h", ".hpp", ".hxx"):
        register_programming_language(
            suffix=suffix,
            syntax_words=cpp_syntax_words,
            syntax_rules=cpp_syntax_rules,
        )
```

They will be grouped under one submenu in the Plugins menu.

它們會在插件選單中合併顯示在同一個子選單下。

---

## Translation Plugin / 翻譯插件

Use `register_natural_language()` to add a new UI language.

使用 `register_natural_language()` 新增 UI 語言。

### API

```python
from je_editor.plugins import register_natural_language

register_natural_language(
    language_key="French",          # Internal key / 內部鍵值
    display_name="Francais",        # Shown in Language menu / 語言選單顯示名稱
    word_dict={...},                # Translation dictionary / 翻譯字典
)
```

### word_dict keys / word_dict 鍵值

The `word_dict` should contain the same keys as jeditor's built-in `english_word_dict`.
Common keys include:

`word_dict` 應包含與 jeditor 內建 `english_word_dict` 相同的鍵值。
常用鍵值包括：

| Key | Description / 說明 |
|---|---|
| `application_name` | Window title / 視窗標題 |
| `file_menu_label` | File menu / 檔案選單 |
| `run_menu_label` | Run menu / 執行選單 |
| `tab_name_editor` | Editor tab / 編輯器分頁 |
| `language_menu_label` | Language menu / 語言選單 |
| `help_menu_label` | Help menu / 幫助選單 |

For a complete list, refer to `je_editor.utils.multi_language.english.english_word_dict`
or see the example plugin `exe/jeditor_plugins/french.py`.

完整鍵值列表請參考 `je_editor.utils.multi_language.english.english_word_dict`，
或參考範例插件 `exe/jeditor_plugins/french.py`。

### Full Example / 完整範例

```python
"""Japanese translation plugin."""
from je_editor.plugins import register_natural_language

PLUGIN_NAME = "Japanese Translation"
PLUGIN_AUTHOR = "Your Name"
PLUGIN_VERSION = "1.0.0"

japanese_word_dict = {
    "application_name": "JEditor",
    "file_menu_label": "ファイル",
    "run_menu_label": "実行",
    "tab_name_editor": "エディタ",
    "language_menu_label": "言語",
    "language_menu_bar_english": "英語",
    "language_menu_bar_traditional_chinese": "繁体字中国語",
    "language_menu_bar_please_restart_messagebox": "アプリケーションを再起動してください",
    # ... more keys
}


def register() -> None:
    register_natural_language(
        language_key="Japanese",
        display_name="日本語",
        word_dict=japanese_word_dict,
    )
```

---

## Run Config (Execute Files) / 執行設定

Plugins can register a `PLUGIN_RUN_CONFIG` to enable running files from the **Run with...** menu.

插件可定義 `PLUGIN_RUN_CONFIG`，讓使用者可以從 **以...執行** 選單執行檔案。

### Interpreted Languages / 直譯式語言

For languages that run directly (Go, Java 11+, Python):

直接執行的語言（Go、Java 11+、Python）：

```python
PLUGIN_RUN_CONFIG = {
    "name": "Go",                   # Display name in menu / 選單顯示名稱
    "suffixes": (".go",),           # Supported file types / 支援的副檔名
    "compiler": "go",               # Executable / 執行檔
    "args": ("run",),               # Args before file path / 檔案路徑前的參數
}
# Runs: go run file.go
```

### Compiled Languages / 編譯式語言

For languages that need compile-then-run (C, C++, Rust):

需要先編譯再執行的語言（C、C++、Rust）：

```python
PLUGIN_RUN_CONFIG = {
    "name": "C (GCC)",
    "suffixes": (".c",),
    "compiler": "gcc",
    "args": (),
    "compile_then_run": True,       # Compile first, then run output / 先編譯再執行
    "output_flag": "-o",            # Flag for output binary / 輸出檔案的旗標
}
# Compiles: gcc file.c -o file
# Then runs: ./file (Linux/Mac) or file.exe (Windows)
```

### Config Keys / 設定鍵值

| Key | Required | Description |
|---|---|---|
| `name` | Yes | Display name / 顯示名稱 |
| `suffixes` | Yes | Tuple of file extensions / 副檔名元組 |
| `compiler` | Yes | Compiler/interpreter executable / 編譯器或直譯器 |
| `args` | No | Extra args before file path / 檔案路徑前的額外參數 |
| `compile_then_run` | No | If `True`, compile first / 若為 `True` 則先編譯 |
| `output_flag` | No | Output file flag (default `"-o"`) / 輸出旗標 |

---

## Directory Structure / 目錄結構

```
working_directory/
  jeditor_plugins/
    my_syntax.py            # Single-file plugin / 單檔插件
    my_language.py
    my_package/             # Package plugin / 套件插件
      __init__.py
```

- Plugins are auto-discovered from `jeditor_plugins/` under the current working directory.
- Files starting with `_` or `.` are ignored.
- Each plugin must have a `register()` function.

<!-- -->

- 插件會從工作目錄下的 `jeditor_plugins/` 自動載入。
- 以 `_` 或 `.` 開頭的檔案會被忽略。
- 每個插件必須有 `register()` 函式。

---

## Existing Plugins / 現有插件

| Plugin | File | Type | Run Support |
|---|---|---|---|
| C Syntax Highlighting | `c_syntax.py` | Syntax (`.c`) | GCC compile & run |
| C++ Syntax Highlighting | `cpp_syntax.py` | Syntax (`.cpp`, `.cxx`, `.cc`, `.h`, `.hpp`, `.hxx`) | G++ compile & run |
| Go Syntax Highlighting | `go_syntax.py` | Syntax (`.go`) | `go run` |
| Java Syntax Highlighting | `java_syntax.py` | Syntax (`.java`) | `java` |
| Rust Syntax Highlighting | `rust_syntax.py` | Syntax (`.rs`) | rustc compile & run |
| French Translation | `french.py` | Language | - |

All plugins are located in `exe/jeditor_plugins/`.
