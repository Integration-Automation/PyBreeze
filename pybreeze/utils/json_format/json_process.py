from __future__ import annotations

import json
from json import dumps
from json import loads

from pybreeze.utils.exception.exception_tags import cant_reformat_json_error
from pybreeze.utils.exception.exception_tags import wrong_json_data_error
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.logging.logger import pybreeze_logger


def _process_json(json_string: str, **kwargs) -> str:
    try:
        return dumps(loads(json_string), indent=4, sort_keys=True, **kwargs)
    except json.JSONDecodeError as error:
        # Wrap in the project exception so reformat_json's caller sees a single,
        # documented ITEJsonException type rather than a raw JSONDecodeError.
        pybreeze_logger.error(wrong_json_data_error)
        raise ITEJsonException(wrong_json_data_error) from error
    except TypeError:
        try:
            return dumps(json_string, indent=4, sort_keys=True, **kwargs)
        except TypeError as err:
            raise ITEJsonException(wrong_json_data_error) from err


def reformat_json(json_string: str, **kwargs) -> str:
    try:
        return _process_json(json_string, **kwargs)
    except ITEJsonException as err:
        raise ITEJsonException(cant_reformat_json_error) from err


# Compact separators for minified JSON: no spaces after ',' or ':'.
_MINIFY_SEPARATORS = (",", ":")


def minify_json(json_string: str) -> str:
    """Return *json_string* re-serialised with no insignificant whitespace.

    :param json_string: the JSON text to compact
    :return: the minified JSON on a single line
    :raises ITEJsonException: when the input is not valid JSON
    """
    try:
        return dumps(loads(json_string), separators=_MINIFY_SEPARATORS)
    except json.JSONDecodeError as error:
        pybreeze_logger.error(wrong_json_data_error)
        raise ITEJsonException(wrong_json_data_error) from error
