import json.decoder
from json import dumps
from json import loads

from pybreeze.utils.exception.exception_tags import cant_reformat_json_error
from pybreeze.utils.exception.exception_tags import wrong_json_data_error
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.logging.logger import pybreeze_logger


def __process_json(json_string: str, **kwargs) -> str:
    try:
        return dumps(loads(json_string), indent=4, sort_keys=True, **kwargs)
    except json.JSONDecodeError as error:
        pybreeze_logger.error(wrong_json_data_error)
        raise error
    except TypeError:
        try:
            return dumps(json_string, indent=4, sort_keys=True, **kwargs)
        except TypeError as err:
            raise ITEJsonException(wrong_json_data_error) from err


def reformat_json(json_string: str, **kwargs) -> str:
    try:
        return __process_json(json_string, **kwargs)
    except ITEJsonException as err:
        raise ITEJsonException(cant_reformat_json_error) from err
