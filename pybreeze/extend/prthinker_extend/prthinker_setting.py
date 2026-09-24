"""
prthinker 這個程式碼審查框架的設定與指令組裝
Settings for the prthinker code review framework, and the commands it is run with.

prthinker 的每一個選項都可以用 ``PRTHINKER_*`` 環境變數給，因此這裡把使用者填的設定
變成環境變數交給子行程，命令列上只留「這次要審什麼」——金鑰不會出現在命令列，也就不
會出現在工作管理員或執行紀錄裡。
Every prthinker option can be given through a ``PRTHINKER_*`` environment
variable, so the settings a user fills in are handed to the child process as
environment and the command line carries only what is being reviewed this time.
A key therefore never appears on a command line, which is what a task manager or
a run log would show.

純邏輯，不含 Qt：組出來的東西可以單獨測。
Pure logic, with no Qt: what it builds can be tested on its own.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Dict, List

from pybreeze.utils.app_dirs import DATA_DIR_MODE, pybreeze_data_path
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.logging.logger import pybreeze_logger

# 設定檔名 / The settings file's name
SETTING_FILE_NAME = "prthinker_setting.json"

# 執行 prthinker 用的模組名 / The module prthinker is run as
PRTHINKER_PACKAGE = "prthinker"

# 可選的推論後端，與 prthinker 的 ``--backend`` 一致
# The inference backends on offer, matching prthinker's ``--backend``
BACKENDS = (
    "remote", "local", "openai", "anthropic", "gemini", "cohere", "mistral",
    "claude-cli", "codex-cli",
)

# 可選的程式碼託管平台 / The forges on offer
PLATFORMS = ("github", "gitlab", "gitea")

# 規則檢索（RAG）的做法：關掉，或交給伺服器的 /rag。prthinker 的本機索引只跟著它的
# 原始碼庫，不在安裝的套件裡，所以這裡裝的 prthinker 沒辦法在本機檢索。
# How rules are retrieved (RAG): not at all, or through the server's /rag.
# prthinker's local index ships with its repository and not with its package, so
# the prthinker installed from here cannot retrieve locally.
RAG_MODES = ("off", "remote")

# 每種做法交給子行程的環境變數；認不得的值一律當作關掉。兩個變數都一定送出：
# 子行程繼承 IDE 的環境，只送一個的話，使用者原本設的另一個會留下來作數。
# The variables each way is given through; an unknown value counts as off.
# Both are always sent: the child inherits the IDE's environment, so leaving
# one out would let whatever the user has exported decide it.
RAG_ENVIRONMENT = {
    "off": {"PRTHINKER_RAG_ENABLED": "false", "PRTHINKER_REMOTE_RAG": "false"},
    "remote": {"PRTHINKER_RAG_ENABLED": "true", "PRTHINKER_REMOTE_RAG": "true"},
}

# 每個後端讀模型名稱的環境變數：prthinker 各後端各讀各的
# The variable each backend reads its model from: each prthinker backend has its own
MODEL_ENVIRONMENT = {
    "remote": "PRTHINKER_MODEL_NAME",
    "local": "PRTHINKER_MODEL_NAME",
    "openai": "PRTHINKER_OPENAI_MODEL",
    "anthropic": "PRTHINKER_ANTHROPIC_MODEL",
    "gemini": "PRTHINKER_GEMINI_MODEL",
    "cohere": "PRTHINKER_COHERE_MODEL",
    "mistral": "PRTHINKER_MISTRAL_MODEL",
    "claude-cli": "PRTHINKER_CLAUDE_CLI_MODEL",
    "codex-cli": "PRTHINKER_CODEX_CLI_MODEL",
}

# 其餘每個設定項對應的環境變數；模型名稱依後端而定，見 MODEL_ENVIRONMENT
# The variable every other setting is given through; the model name's depends on
# the backend (MODEL_ENVIRONMENT)
SETTING_ENVIRONMENT = {
    "backend": "PRTHINKER_BACKEND",
    "remote_url": "PRTHINKER_REMOTE_URL",
    "remote_api_key": "PRTHINKER_REMOTE_API_KEY",
    "openai_api_key": "PRTHINKER_OPENAI_API_KEY",
    "openai_base_url": "PRTHINKER_OPENAI_BASE_URL",
    "anthropic_api_key": "PRTHINKER_ANTHROPIC_API_KEY",
    "platform": "PRTHINKER_PLATFORM",
    "platform_base_url": "PRTHINKER_PLATFORM_BASE_URL",
    "repository": "GITHUB_REPOSITORY",
    "platform_token": "GITHUB_TOKEN",
}

# 不能寫進紀錄的設定項 / The settings that must never reach a log
SECRET_SETTINGS = (
    "remote_api_key", "openai_api_key", "anthropic_api_key", "platform_token")

# 預設設定 / The settings as they start out
DEFAULT_SETTING: Dict[str, str] = {
    "backend": "remote",
    "model_name": "",
    "remote_url": "",
    "remote_api_key": "",
    "openai_api_key": "",
    "openai_base_url": "",
    "anthropic_api_key": "",
    "platform": "github",
    "platform_base_url": "",
    "repository": "",
    "platform_token": "",
    "rag": "off",
    "extra_arguments": "",
    "source_path": "",
}

# 安裝時要一併帶上的 extras：runner 是只跑審查、不載模型的那一組
# The extras to install with: ``runner`` is the set that reviews without
# pulling in a model
INSTALL_EXTRAS = "runner"
# The project name line of prthinker's pyproject.toml; parsed by hand, since the
# stdlib's tomllib arrived in 3.11 and this runs on 3.10
_PRTHINKER_PROJECT_NAME = re.compile(r'^name\s*=\s*["\']prthinker["\']\s*$', re.MULTILINE)


def setting_path() -> Path:
    """
    設定檔的位置
    Where the settings are kept.

    與 SSH 的 known_hosts、AI 審查統計放在同一個使用者層級目錄，因此從哪個資料夾啟動
    編輯器都讀得到同一份。
    Beside the SSH known hosts and the AI review stats in the same user-level
    directory, so the same settings are found whichever folder the editor was
    started from.

    :return: 設定檔路徑 / the settings file's path
    """
    return pybreeze_data_path() / SETTING_FILE_NAME


def load_setting() -> Dict[str, str]:
    """
    讀取設定，缺項與壞檔都退回預設值
    Read the settings, falling back to the defaults for anything missing or broken.

    設定檔壞掉不該擋住功能：讀不出來就當作還沒設定過。
    A broken file must not block the feature: what cannot be read counts as not
    yet configured.

    :return: 設定 / the settings
    """
    setting = dict(DEFAULT_SETTING)
    path = setting_path()
    try:
        # Reading creates nothing: a data folder that could not be made (a
        # file in its place) raised out of every prthinker menu entry
        if not path.is_file():
            return setting
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        pybreeze_logger.error("prthinker settings could not be read: %r", error)
        return setting
    if not isinstance(stored, dict):
        return setting
    for key, value in stored.items():
        if key not in DEFAULT_SETTING:
            continue
        # Every setting is text. str() made a hand-edited null the text "None",
        # which then went out as the API key, the repository and the model,
        # and a list became broken arguments; anything else keeps its default.
        if isinstance(value, str):
            setting[key] = value
        else:
            pybreeze_logger.debug("prthinker setting %s is not text; using the default", key)
    return setting


def save_setting(setting: Dict[str, str]) -> bool:
    """
    寫回設定
    Write the settings back.

    :param setting: 要寫入的設定 / the settings to store
    :return: 是否寫入成功 / whether it was written
    """
    to_store = {key: setting.get(key, "") for key in DEFAULT_SETTING}
    try:
        path = setting_path()
        path.parent.mkdir(mode=DATA_DIR_MODE, parents=True, exist_ok=True)
        # Replaced in one step, readable by its owner only: written in place, a
        # failure part-way emptied the file and every key and token in it
        replace_text(path, json.dumps(to_store, indent=4, ensure_ascii=False), private=True)
    # A lone surrogate, loaded from a hand-edited "\ud800", cannot be written
    # as UTF-8: it raised out of the install menu's slot
    except (OSError, UnicodeEncodeError) as error:
        pybreeze_logger.error("prthinker settings could not be saved: %r", error)
        return False
    return True


def environment_for(setting: Dict[str, str]) -> Dict[str, str]:
    """
    把設定變成 prthinker 認得的環境變數
    Turn the settings into the environment variables prthinker reads.

    空白的項目不放進去，prthinker 才用得到它自己的預設值。模型名稱交給所選後端自己的
    變數。規則檢索例外：prthinker 預設在本機檢索，而這裡裝的 prthinker 做不到，所以
    一定會明講要關掉或交給伺服器。
    A blank setting is left out, so prthinker keeps its own default for it. The
    model name goes to the chosen backend's own variable. Rule retrieval is the
    exception: prthinker's default is to retrieve locally, which the prthinker
    installed from here cannot do, so it is always told to go without or to ask
    the server.

    :param setting: 目前的設定 / the settings in use
    :return: 要加進子行程環境的變數 / the variables to add to the child's environment
    """
    environment = {
        name: setting[key].strip()
        for key, name in SETTING_ENVIRONMENT.items()
        if setting.get(key, "").strip()
    }
    model = setting.get("model_name", "").strip()
    backend = setting.get("backend", "").strip()
    model_variable = MODEL_ENVIRONMENT.get(backend)
    if model and model_variable:
        environment[model_variable] = model
    elif model:
        # Each backend reads its own variable, so without a backend there is
        # nowhere to put the model; say so rather than drop it quietly.
        pybreeze_logger.error(
            "prthinker model %r not sent: %r is not a backend PyBreeze offers",
            model, backend)
    rag_mode = setting.get("rag", "")
    environment.update(RAG_ENVIRONMENT.get(rag_mode, RAG_ENVIRONMENT["off"]))
    return environment


def extra_arguments(setting: Dict[str, str]) -> List[str]:
    """
    使用者自己加的命令列參數
    The command-line arguments the user added.

    以命令列的規則斷詞，引號內的空白因此不會被拆開；寫壞了就當作沒有，不要讓一次審查
    因為一個引號沒關而完全跑不起來。
    Split the way a command line is, so a space inside quotes stays put. What
    cannot be split counts as none: one unclosed quote should not stop a review
    from running at all.

    :param setting: 目前的設定 / the settings in use
    :return: 參數 / the arguments
    """
    try:
        return read_extra_arguments(setting.get("extra_arguments", ""))
    except ValueError as error:
        pybreeze_logger.error("prthinker extra arguments could not be read: %r", error)
        return []


def read_extra_arguments(text: str) -> List[str]:
    """
    把「額外參數」欄位斷成參數，斷不了就丟 ValueError；設定視窗存檔前用它先檢查
    Split the extra-arguments field into arguments, raising ValueError when it
    cannot be; the settings dialog checks with it before saving.

    :param text: 欄位內容 / what the field holds
    :return: 參數 / the arguments
    :raises ValueError: 引號沒有關上時 / when a quote is left open
    """
    text = text.strip()
    if not text:
        return []
    return split_arguments(text, backslash_escapes=os.sep != "\\")


def split_arguments(text: str, *, backslash_escapes: bool) -> List[str]:
    """
    以命令列的規則斷詞
    Split *text* into arguments the way a command line is split.

    Windows 的路徑用反斜線分隔，那裡的反斜線不能當跳脫字元，否則 ``C:\\reviews`` 會變成
    ``C:reviews``。
    Where a backslash separates path parts (Windows), it must not escape the
    next character, or ``C:\\reviews`` would come out as ``C:reviews``.

    :param text: 要斷詞的文字 / the text to split
    :param backslash_escapes: 反斜線是否為跳脫字元 / whether a backslash escapes
    :return: 參數 / the arguments
    :raises ValueError: 引號沒有關上時 / when a quote is left open
    """
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    # 不把 # 當註解：C#、網址的 #section 都是參數的一部分
    # "#" starts no comment (shlex.split clears it too): "C#" or a URL's
    # "#section" cut off every argument after it
    lexer.commenters = ""
    if not backslash_escapes:
        lexer.escape = ""
    return list(lexer)


def review_file_arguments(file_path: str, setting: Dict[str, str]) -> List[str]:
    """
    組出審查單一檔案的參數
    Build the arguments that review one file.

    :param file_path: 要審查的檔案 / the file to review
    :param setting: 目前的設定 / the settings in use
    :return: 參數 / the arguments
    """
    return ["review-file", str(file_path), *extra_arguments(setting)]


def review_pr_arguments(pull_request_number: int, setting: Dict[str, str]) -> List[str]:
    """
    組出審查一個 Pull Request 的參數
    Build the arguments that review one pull request.

    儲存庫與權杖都走環境變數，這裡只給這次要審的編號。
    The repository and the token travel as environment; only the number being
    reviewed this time is given here.

    :param pull_request_number: PR 或 MR 的編號 / the pull request's number
    :param setting: 目前的設定 / the settings in use
    :return: 參數 / the arguments
    """
    return [
        "review-pr", "--pr-number", str(pull_request_number),
        *extra_arguments(setting),
    ]


def install_target(source_path: str) -> str:
    """
    組出要交給 pip 的安裝目標
    Build what pip is asked to install.

    prthinker 是從原始碼安裝的，不在 PyPI 上，所以給的是資料夾而不是套件名。
    prthinker is installed from source rather than from PyPI, so what is given
    is a folder and not a package name.

    資料夾要是 prthinker 自己的原始碼（``pyproject.toml`` 的專案名稱是 prthinker），
    選錯資料夾才不會被記下來，之後每次都拿去跑一個一定失敗的 pip。
    The folder has to be prthinker's own source (its ``pyproject.toml`` names the
    project prthinker): a wrong one used to be saved and handed to a pip that
    could only fail, every time, until it was cleared in the settings.

    :param source_path: 框架原始碼的資料夾 / the framework's source folder
    :return: pip 的安裝目標，不是 prthinker 原始碼時為空字串 / the target for
        pip, or an empty string when the path is not prthinker's source folder
    """
    path = Path(source_path.strip()) if source_path.strip() else None
    if path is None or not _is_prthinker_source(path):
        return ""
    return f"{path}[{INSTALL_EXTRAS}]"


def _is_prthinker_source(folder: Path) -> bool:
    """Whether *folder* holds a ``pyproject.toml`` whose project is prthinker."""
    try:
        text = (folder / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        pybreeze_logger.debug("Not a prthinker source folder %s: %r", folder, error)
        return False
    return _PRTHINKER_PROJECT_NAME.search(text) is not None


def loggable(setting: Dict[str, str]) -> Dict[str, str]:
    """
    可以寫進紀錄的設定
    The settings as they may be written to a log.

    金鑰與權杖只留「有沒有設定」，不留內容。
    A key or a token is reduced to whether it is set at all.

    :param setting: 目前的設定 / the settings in use
    :return: 遮蓋過的設定 / the settings with the secrets covered
    """
    return {
        key: ("(set)" if value.strip() else "")
        if key in SECRET_SETTINGS else value
        for key, value in setting.items()
    }
