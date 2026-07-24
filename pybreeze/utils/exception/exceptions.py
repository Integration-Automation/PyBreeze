from __future__ import annotations

class ITEException(Exception):
    pass


# Executor

class ITEAddCommandException(ITEException):
    pass


class ITEExecException(ITEException):
    pass


class ITETestExecutorException(ITEException):
    pass


# HTML

class ITESendHtmlReportException(ITEException):
    pass


# UI

class ITEUIException(ITEException):
    pass


# Content

class ITEContentFileException(ITEException):
    pass


# Json

class ITEJsonException(ITEException):
    pass


# XML

class XMLException(ITEException):
    pass


class XMLTypeException(XMLException):
    pass


# cURL import

class CurlParseException(ITEException):
    pass


# JWT decode

class JwtDecodeException(ITEException):
    pass


# Timestamp conversion

class TimestampParseException(ITEException):
    pass


# Query <-> JSON conversion

class QueryConvertException(ITEException):
    pass


# Regex testing

class RegexTesterException(ITEException):
    pass
