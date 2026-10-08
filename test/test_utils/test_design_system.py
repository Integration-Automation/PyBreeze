"""The design system: sizes that follow the font, rows that wrap, and the panels built from them."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from pybreeze.pybreeze_ui.design import tokens
from pybreeze.pybreeze_ui.design.flow_layout import FlowLayout
from pybreeze.pybreeze_ui.design.panels import Panel, StatusLine, wrapping_row
from pybreeze.pybreeze_ui.design.tokens import IconSize, Space, State, TextRole


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _widget_with_font(points: float) -> QWidget:
    widget = QWidget()
    font = QFont(widget.font())
    font.setPointSizeF(points)
    widget.setFont(font)
    return widget


class TestTokens:
    def test_an_em_is_the_height_of_the_font_in_use(self, app):
        small, large = _widget_with_font(9), _widget_with_font(18)

        assert tokens.em(large) > tokens.em(small) > 0
        assert tokens.em() == tokens.em(QWidget())

    def test_a_gap_grows_with_the_font(self, app):
        small, large = _widget_with_font(9), _widget_with_font(18)

        for step in Space:
            assert tokens.space(step, large) > tokens.space(step, small) >= 1

    def test_the_gaps_come_in_order(self, app):
        gaps = [tokens.space(step) for step in (Space.HAIRLINE, Space.TIGHT, Space.NORMAL, Space.SECTION)]

        assert gaps == sorted(gaps)
        assert len(set(gaps)) == len(gaps)

    def test_a_gap_is_never_nothing(self, app):
        assert tokens.space(Space.HAIRLINE, _widget_with_font(1)) >= 1

    def test_text_comes_in_sizes_of_the_font_in_use(self, app):
        widget = _widget_with_font(10)

        sizes = {role: tokens.text_font(role, widget).pointSizeF() for role in TextRole}

        assert sizes[TextRole.BODY] == pytest.approx(10)
        assert sizes[TextRole.CAPTION] < sizes[TextRole.BODY] < sizes[TextRole.TITLE] < sizes[TextRole.HEADING]

    def test_titles_and_headings_are_bold_and_the_rest_is_not(self, app):
        bold = {role for role in TextRole if tokens.text_font(role).bold()}

        assert bold == {TextRole.TITLE, TextRole.HEADING}

    def test_a_font_sized_in_pixels_is_scaled_in_pixels(self, app):
        widget = QWidget()
        font = QFont(widget.font())
        font.setPixelSize(20)
        widget.setFont(font)

        assert tokens.text_font(TextRole.HEADING, widget).pixelSize() == 28

    def test_an_icon_is_a_square_that_grows_with_the_font(self, app):
        small, large = _widget_with_font(9), _widget_with_font(18)

        for size in IconSize:
            square = tokens.icon_size(size, small)
            assert square.width() == square.height() >= 1
            assert tokens.icon_size(size, large).width() > square.width()

    @pytest.mark.parametrize("state", list(State))
    def test_each_state_has_a_colour_of_the_theme(self, app, state):
        assert tokens.state_colour(state).isValid()

    def test_a_theme_without_the_colour_gives_the_text_colour(self, app, monkeypatch):
        monkeypatch.setattr(tokens, "actually_color_dict", {})

        assert tokens.state_colour(State.ERROR) == QApplication.palette().windowText().color()

    def test_a_state_takes_the_themes_own_colour(self, app, monkeypatch):
        monkeypatch.setattr(tokens, "actually_color_dict", {State.ERROR.value: QColor(1, 2, 3)})

        assert tokens.state_colour(State.ERROR) == QColor(1, 2, 3)

    def test_a_layout_gets_the_standard_gaps(self, app):
        widget = _widget_with_font(12)
        layout = QVBoxLayout(widget)

        tokens.apply_spacing(layout)

        margins = layout.contentsMargins()
        around = tokens.space(Space.NORMAL, widget)
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (around,) * 4
        assert layout.spacing() == tokens.space(Space.TIGHT, widget)


def _buttons(count: int) -> list[QPushButton]:
    buttons = [QPushButton(f"Button number {index}") for index in range(count)]
    for button in buttons:
        button.setFixedSize(100, 20)
    return buttons


def _flow(buttons: list[QPushButton], gap: int = 10) -> tuple[QWidget, FlowLayout]:
    host = QWidget()
    layout = FlowLayout(host, gap=gap)
    layout.setContentsMargins(0, 0, 0, 0)
    for button in buttons:
        layout.addWidget(button)
    return host, layout


class TestFlowLayout:
    def test_with_room_everything_is_on_one_line(self, app):
        buttons = _buttons(3)
        _host, layout = _flow(buttons)

        layout.setGeometry(QRect(0, 0, 400, 100))

        assert [button.geometry().topLeft().toTuple() for button in buttons] == [(0, 0), (110, 0), (220, 0)]
        assert layout.heightForWidth(400) == 20

    def test_without_room_the_next_starts_a_new_line(self, app):
        buttons = _buttons(3)
        _host, layout = _flow(buttons)

        layout.setGeometry(QRect(0, 0, 215, 100))

        assert [button.geometry().topLeft().toTuple() for button in buttons] == [(0, 0), (110, 0), (0, 30)]
        assert layout.heightForWidth(215) == 50

    def test_an_item_that_just_fits_stays_on_the_line(self, app):
        buttons = _buttons(2)
        _host, layout = _flow(buttons)

        layout.setGeometry(QRect(0, 0, 210, 100))

        assert buttons[1].geometry().topLeft().toTuple() == (110, 0)

    def test_narrower_than_one_item_each_has_a_line_of_its_own(self, app):
        buttons = _buttons(3)
        _host, layout = _flow(buttons)

        layout.setGeometry(QRect(0, 0, 50, 100))

        assert [button.geometry().y() for button in buttons] == [0, 30, 60]

    def test_it_needs_no_more_width_than_its_widest_item(self, app):
        _host, layout = _flow(_buttons(6))

        assert layout.minimumSize().width() == 100
        assert layout.sizeHint().width() == 6 * 100 + 5 * 10

    def test_margins_are_kept_around_the_lines(self, app):
        buttons = _buttons(2)
        _host, layout = _flow(buttons)
        layout.setContentsMargins(5, 7, 5, 9)

        layout.setGeometry(QRect(0, 0, 150, 100))

        assert buttons[0].geometry().topLeft().toTuple() == (5, 7)
        assert buttons[1].geometry().topLeft().toTuple() == (5, 37)
        assert layout.heightForWidth(150) == 7 + 20 + 10 + 20 + 9

    def test_a_hidden_item_takes_no_place(self, app):
        buttons = _buttons(3)
        host, layout = _flow(buttons)
        host.show()
        buttons[1].hide()

        layout.setGeometry(QRect(0, 0, 400, 100))

        assert buttons[2].geometry().topLeft().toTuple() == (110, 0)
        host.close()

    def test_items_are_counted_found_and_taken(self, app):
        _host, layout = _flow(_buttons(2))

        assert layout.count() == 2
        assert layout.itemAt(1) is not None
        assert layout.itemAt(2) is None and layout.itemAt(-1) is None
        assert layout.takeAt(5) is None
        taken = layout.takeAt(0)
        assert taken is not None and layout.count() == 1

    def test_it_asks_for_no_spare_room(self, app):
        _host, layout = _flow(_buttons(1))

        assert layout.expandingDirections() == Qt.Orientation(0)
        assert layout.hasHeightForWidth()

    def test_the_styles_own_gap_is_used_when_none_is_given(self, app):
        buttons = _buttons(2)
        _host, layout = _flow(buttons, gap=-1)
        layout.setSpacing(4)

        layout.setGeometry(QRect(0, 0, 400, 100))

        assert buttons[1].geometry().x() == 104

    def test_what_is_under_a_wrapped_row_moves_down(self, app):
        # In a panel: the row wraps, and the editor below starts under its last line
        host = QWidget()
        column = QVBoxLayout(host)
        row = FlowLayout(gap=10)
        buttons = _buttons(4)
        for button in buttons:
            row.addWidget(button)
        below = QTextEdit()
        column.addLayout(row)
        column.addWidget(below)
        host.resize(260, 300)
        host.show()
        QApplication.processEvents()

        try:
            lines = {button.geometry().y() for button in buttons}
            assert len(lines) == 2
            assert below.geometry().top() >= max(button.geometry().bottom() for button in buttons)
        finally:
            host.close()


class TestPanels:
    def test_a_panel_shows_its_title_as_text(self, app):
        panel = Panel("<b>Servers</b>")

        assert panel.title_label.textFormat() == Qt.TextFormat.PlainText
        assert panel.title_label.text() == "<b>Servers</b>"
        assert panel.title_label.font().bold()

    def test_a_panel_without_a_title_shows_none(self, app):
        assert Panel().title_label.isHidden()

    def test_a_panel_holds_widgets_and_layouts(self, app):
        panel = Panel("Tools")
        label, row = QLabel("first"), wrapping_row(QPushButton("second"))

        panel.add(label)
        panel.add(row)

        assert panel.body.itemAt(0).widget() is label
        assert panel.body.itemAt(1).layout() is row

    @pytest.mark.parametrize("state", list(State))
    def test_a_status_line_takes_the_colour_of_what_it_says(self, app, state):
        line = StatusLine()

        line.show_state(state, "<i>done</i>")

        assert line.state is state
        assert line.text() == "<i>done</i>"
        assert line.textFormat() == Qt.TextFormat.PlainText
        assert line.palette().color(line.foregroundRole()) == tokens.state_colour(state)

    def test_a_row_of_controls_wraps(self, app):
        buttons = _buttons(3)

        row = wrapping_row(*buttons)
        host = QWidget()
        host.setLayout(row)
        row.setGeometry(QRect(0, 0, 150, 100))

        assert row.count() == 3
        assert len({button.geometry().y() for button in buttons}) == 3
