"""SGR escape sequences read into a text style, and the format a view shows it in."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.terminal_view import style_format
from pybreeze.utils.terminal_style import PLAIN, TextStyle, apply_sgr, colour_rgb, split_styled


class TestApplySgr:
    @pytest.mark.parametrize(("parameters", "expected"), [
        ("31", TextStyle(foreground=1)),
        ("91", TextStyle(foreground=9)),
        ("44", TextStyle(background=4)),
        ("107", TextStyle(background=15)),
        ("1;4;3;7", TextStyle(bold=True, underline=True, italic=True, inverse=True)),
        ("38;5;196", TextStyle(foreground=196)),
        ("48;2;10;20;30", TextStyle(background=(10, 20, 30))),
        ("38;5;208;1", TextStyle(foreground=208, bold=True)),
    ])
    def test_sets_what_it_names(self, parameters, expected):
        assert apply_sgr(PLAIN, parameters) == expected

    @pytest.mark.parametrize("parameters", ["0", "", "00"])
    def test_zero_or_nothing_resets(self, parameters):
        styled = TextStyle(foreground=1, background=2, bold=True, underline=True)

        assert apply_sgr(styled, parameters) == PLAIN

    def test_the_off_switches_and_defaults_undo_one_thing_each(self):
        styled = TextStyle(foreground=1, background=2, bold=True, italic=True, underline=True, inverse=True)

        assert apply_sgr(styled, "22;23") == TextStyle(foreground=1, background=2, underline=True, inverse=True)
        assert apply_sgr(styled, "39;49;24;27") == TextStyle(bold=True, italic=True)

    @pytest.mark.parametrize("parameters", ["38;5", "38;5;256", "38;2;1;2", "38;2;1;2;300", "38;9;1", "38", "5", "1000"])
    def test_what_cannot_be_read_changes_nothing(self, parameters):
        styled = TextStyle(foreground=3)

        assert apply_sgr(styled, parameters).foreground == 3

    def test_a_parameter_thousands_of_digits_long_is_ignored(self):
        # int() refuses more than 4300 digits: a server could send them
        assert apply_sgr(PLAIN, "9" * 5000 + ";31") == TextStyle(foreground=1)


class TestColourRgb:
    @pytest.mark.parametrize(("colour", "on_dark", "rgb"), [
        (4, True, (36, 114, 200)),   # xterm's (0, 0, 238) was unreadable on a dark theme
        (4, False, (4, 81, 165)),
        (7, True, (229, 229, 229)),
        (7, False, (85, 85, 85)),    # "white" text stays readable on white
        (1, True, (205, 49, 49)),
    ])
    def test_the_basic_colours_suit_the_background(self, colour, on_dark, rgb):
        assert colour_rgb(colour, on_dark=on_dark) == rgb

    @pytest.mark.parametrize(("colour", "rgb"), [
        (16, (0, 0, 0)),
        (196, (255, 0, 0)),
        (231, (255, 255, 255)),
        (232, (8, 8, 8)),
        (255, (238, 238, 238)),
        ((1, 2, 3), (1, 2, 3)),
    ])
    @pytest.mark.parametrize("on_dark", [True, False])
    def test_the_rest_of_the_palette_is_xterm_on_any_background(self, colour, rgb, on_dark):
        assert colour_rgb(colour, on_dark=on_dark) == rgb


class TestSplitStyled:
    def test_each_piece_has_the_style_it_is_shown_in(self):
        pieces, style = split_styled("a\x1b[1;31mred\x1b[0m plain", PLAIN)

        assert pieces == [(PLAIN, "a"), (TextStyle(foreground=1, bold=True), "red"), (PLAIN, " plain")]
        assert style == PLAIN

    def test_the_style_carries_on_from_earlier_text(self):
        pieces, style = split_styled("still red\x1b[4m", TextStyle(foreground=1))

        assert pieces == [(TextStyle(foreground=1), "still red")]
        assert style == TextStyle(foreground=1, underline=True)

    def test_other_escapes_and_controls_stay_for_the_text_cleaning(self):
        pieces, _style = split_styled("\x1b[2Kbar\r\x1b]0;t\x07", PLAIN)

        assert pieces == [(PLAIN, "\x1b[2Kbar\r\x1b]0;t\x07")]


@pytest.fixture(scope="module")
def palette():
    QApplication.instance() or QApplication([])
    return QPalette()


class TestStyleFormat:
    def test_the_plain_style_changes_nothing(self, palette):
        text_format = style_format(PLAIN, palette)

        assert not text_format.hasProperty(text_format.Property.ForegroundBrush)
        assert not text_format.hasProperty(text_format.Property.FontWeight)

    def test_colours_and_emphasis(self, palette):
        text_format = style_format(TextStyle(foreground=1, background=(1, 2, 3), bold=True, underline=True), palette)

        assert text_format.foreground().color() == QColor(205, 49, 49)
        assert text_format.background().color() == QColor(1, 2, 3)
        assert text_format.fontWeight() == QFont.Weight.Bold
        assert text_format.fontUnderline()

    def test_inverse_swaps_the_view_colours_in_for_defaults(self, palette):
        text_format = style_format(TextStyle(foreground=1, inverse=True), palette)

        assert text_format.foreground().color() == palette.color(QPalette.ColorRole.Base)
        assert text_format.background().color() == QColor(205, 49, 49)


def _palette_with_base(colour: QColor) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Base, colour)
    return palette


@pytest.mark.parametrize(("base", "blue"), [
    (QColor(30, 30, 30), QColor(36, 114, 200)),
    (QColor(255, 255, 255), QColor(4, 81, 165)),
])
def test_the_view_background_picks_the_basic_colours(palette, base, blue):
    text_format = style_format(TextStyle(foreground=4), _palette_with_base(base))

    assert text_format.foreground().color() == blue
