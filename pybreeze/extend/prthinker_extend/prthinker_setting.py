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
import shlex
from pathlib import Path
from typing import Dict, List

from pybreeze.utils.app_dirs import pybreeze_data_dir
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

# 每個設定項對應的環境變數 / The environment variable each setting is given through
SETTING_ENVIRONMENT = {
    "backend": "PRTHINKER_BACKEND",
    "model_name": "PRTHINKER_MODEL_NAME",
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
    "extra_arguments": "",
    "source_path": "",
}

# 安裝時要一併帶上的 extras：runner 是只跑審查、不載模型的那一組
# The extras to install with: ``runner`` is the set that reviews without
# pulling in a model
INSTALL_EXTRAS = "runner"


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
    return pybreeze_data_dir() / SETTING_FILE_NAME


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
    if not path.is_file():
        return setting
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        pybreeze_logger.error("prthinker settings could not be read: %r", error)
        return setting
    if isinstance(stored, dict):
        setting.update(
            {key: str(value) for key, value in stored.items() if key in DEFAULT_SETTING})
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
        setting_path().write_text(
            json.dumps(to_store, indent=4, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        pybreeze_logger.error("prthinker settings could not be saved: %r", error)
        return False
    return True


def environment_for(setting: Dict[str, str]) -> Dict[str, str]:
    """
    把設定變成 prthinker 認得的環境變數
    Turn the settings into the environment variables prthinker reads.

    空白的項目不放進去，prthinker 才用得到它自己的預設值。
    A blank setting is left out, so prthinker keeps its own default for it.

    :param setting: 目前的設定 / the settings in use
    :return: 要加進子行程環境的變數 / the variables to add to the child's environment
    """
    return {
        name: setting[key].strip()
        for key, name in SETTING_ENVIRONMENT.items()
        if setting.get(key, "").strip()
    }


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
    text = setting.get("extra_arguments", "").strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError as error:
        pybreeze_logger.error("prthinker extra arguments could not be read: %r", error)
        return []


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

    :param source_path: 框架原始碼的資料夾 / the framework's source folder
    :return: pip 的安裝目標，路徑不存在時為空字串 / the target for pip, or an
        empty string when the path is not a folder
    """
    path = Path(source_path.strip()) if source_path.strip() else None
    if path is None or not path.is_dir():
        return ""
    return f"{path}[{INSTALL_EXTRAS}]"


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
