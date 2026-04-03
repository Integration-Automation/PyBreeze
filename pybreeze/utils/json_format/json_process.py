import json.decoder
import sys
from json import dumps
from json import loads

from pybreeze.utils.exception.exception_tags import cant_reformat_json_error
from pybreeze.utils.exception.exception_tags import wrong_json_data_error
from pybreeze.utils.exception.exceptions import ITEJsonException


def __process_json(json_string: str, **kwargs) -> str:
    try:
        return dumps(loads(json_string), indent=4, sort_keys=True, **kwargs)
    except json.JSONDecodeError as error:
        print(wrong_json_data_error, file=sys.stderr)
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
