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
