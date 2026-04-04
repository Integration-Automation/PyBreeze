import pytest

from pybreeze.utils.exception.exceptions import (
    ITEException,
    ITEAddCommandException,
    ITEExecException,
    ITETestExecutorException,
    ITESendHtmlReportException,
    ITEUIException,
    ITEContentFileException,
    ITEJsonException,
    XMLException,
    XMLTypeException,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_ite_exception(self):
        for exc_cls in [
            ITEAddCommandException,
            ITEExecException,
            ITETestExecutorException,
            ITESendHtmlReportException,
            ITEUIException,
            ITEContentFileException,
            ITEJsonException,
        ]:
            assert issubclass(exc_cls, ITEException)

    def test_xml_exceptions_inherit_from_ite(self):
        assert issubclass(XMLException, ITEException)
        assert issubclass(XMLTypeException, XMLException)
        assert issubclass(XMLTypeException, ITEException)

    def test_ite_exception_is_exception(self):
        assert issubclass(ITEException, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(ITEException):
            raise ITEAddCommandException("test")

    def test_exception_message(self):
        exc = ITEJsonException("bad json")
        assert str(exc) == "bad json"

    def test_xml_type_caught_by_xml_exception(self):
        with pytest.raises(XMLException):
            raise XMLTypeException("type error")
