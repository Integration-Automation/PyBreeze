# add command exception
add_command_type_exception_tag: str = "command execute_return_value type must be a method or function"
add_command_not_allow_package_exception_tag: str = "chosen command package is not allowed"

# send html report exception
send_html_exception_tag: str = """
make sure you have installed je_mail_thunder
can't send HTML report: check that the login username and password are correct
and that the current working folder contains default_name.html (the default HTML report execute_detail)
or use the file_path function to read
"""

# test executor exception
auto_control_process_executor_exception_tag: str = "can't run AutoControl"
api_testka_process_executor_exception_tag: str = "can't run APITestka"
web_runner_process_executor_exception_tag: str = "can't run WebRunner"
load_density_process_executor_exception_tag: str = "can't run LoadDensity"

# Install
not_install_exception: str = "please install the package first; can't find the package"

# ui exception
wrong_test_data_format_exception_tag: str = "incorrect test data format"

# exec exception
exec_error: str = "AutomationEditor execution error"
file_not_fond_error: str = "File not found"
compiler_not_found_error: str = "Compiler not found"
not_install_package_error: str = "required package not installed"

# json exception
cant_reformat_json_error: str = "can't reformat JSON: is the type correct?"
wrong_json_data_error: str = "can't parse JSON"

# XML
cant_read_xml_error: str = "can't read XML"
xml_type_error: str = "XML type error"
