from pybreeze.utils.manager.package_manager.package_manager_class import PackageManager, package_manager


class TestPackageManager:
    def test_instance_exists(self):
        assert package_manager is not None

    def test_syntax_check_list_is_list(self):
        assert isinstance(package_manager.syntax_check_list, list)

    def test_syntax_check_list_not_empty(self):
        assert len(package_manager.syntax_check_list) > 0

    def test_syntax_check_list_contains_expected_packages(self):
        expected = [
            "je_auto_control",
            "je_load_density",
            "je_api_testka",
            "je_web_runner",
            "automation_file",
            "mail_thunder",
        ]
        for pkg in expected:
            assert pkg in package_manager.syntax_check_list

    def test_new_instance(self):
        pm = PackageManager()
        assert isinstance(pm.syntax_check_list, list)
