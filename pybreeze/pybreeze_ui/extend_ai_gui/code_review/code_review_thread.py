# Worker Thread 負責傳送資料
import requests
from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_RELATION
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.global_rule import \
    build_global_rule_template


class SenderThread(QThread):
    update_response = Signal(str, str)  # (filename, response)

    def __init__(self, files: list, code: str, url: str):
        super().__init__()
        self.files = files
        self.code = code
        self.url = url

    def run(self):
        code = self.code
        first_code_review_result = None
        first_summary_result = None
        linter_result = None
        code_smell_result = None
        for file in self.files:
            match file:
                case "first_summary_prompt.md":
                    first_summary_prompt = COT_TEMPLATE_RELATION.get("first_summary_prompt.md")
                    prompt = build_global_rule_template(
                        prompt=first_summary_prompt.format(code_diff=code)
                    )
                case "first_code_review.md":
                    first_code_review_prompt = COT_TEMPLATE_RELATION.get("first_code_review.md")
                    prompt = build_global_rule_template(
                        prompt=first_code_review_prompt.format(code_diff=code)
                    )
                case "linter.md":
                    linter_prompt = COT_TEMPLATE_RELATION.get("linter.md")
                    prompt = build_global_rule_template(
                        prompt=linter_prompt.format(code_diff=code)
                    )
                case "code_smell_detector.md":
                    code_smell_detector_prompt = COT_TEMPLATE_RELATION.get("code_smell_detector.md")
                    prompt = build_global_rule_template(
                        prompt=code_smell_detector_prompt.format(code_diff=code)
                    )
                case "total_summary.md":
                    total_summary_prompt = COT_TEMPLATE_RELATION.get("total_summary.md")
                    prompt = build_global_rule_template(
                        prompt=total_summary_prompt.format(
                            first_code_review=first_code_review_result,
                            first_summary=first_summary_result,
                            linter_result=linter_result,
                            code_smell_result=code_smell_result,
                            code_diff=code,
                        )
                    )
                case _:
                    continue

            try:
                # 傳送到指定 URL
                resp = requests.post(self.url, json={"prompt": prompt})
                reply_text = resp.text
                match file:
                    case "first_summary_prompt.md":
                        first_summary_result = reply_text
                    case "first_code_review.md":
                        first_code_review_result = reply_text
                    case "linter.md":
                        linter_result = reply_text
                    case "code_smell_detector.md":
                        code_smell_result = reply_text
                    case _:
                        continue
            except Exception as e:
                reply_text = f"{language_wrapper.language_word_dict.get("cot_gui_error_sending")} {file} {e}"

            # 發送訊號更新 UI
            self.update_response.emit(file, reply_text)