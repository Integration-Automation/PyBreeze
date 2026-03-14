import os


class PackageManager(object):

    def __init__(self):
        os.environ["WDM_LOG"] = "0"
        self.syntax_check_list = [
            "je_auto_control",
            "je_load_density",
            "je_api_testka",
            "je_web_runner",
            "automation_file",
            "mail_thunder"
        ]


package_manager = PackageManager()
