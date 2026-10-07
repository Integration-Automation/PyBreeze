"""The pieces PyBreeze's own panels are put together from.

- :class:`Panel`: a titled group, with the standard gaps around its content;
- :class:`StatusLine`: one line that says how something went, in the theme's
  colour for it;
- :func:`wrapping_row`: controls side by side that wrap when the panel is narrow.

Each takes its sizes from ``design/tokens.py``, so a panel made of them looks
like the others and follows the font and the theme without a number of its
own. Text given to them is shown as text: a title or a message may come from a
file or a server (``plain_text.py``).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QLayout, QVBoxLayout, QWidget

from pybreeze.pybreeze_ui.design.flow_layout import FlowLayout
from pybreeze.pybreeze_ui.design.tokens import Space, State, TextRole, apply_spacing, space, state_colour, text_font


class Panel(QFrame):
    """A titled group of controls.

    :param title: what the group is, shown above it; none when empty
    :param parent: the widget it belongs to
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.title_label = QLabel(title)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setFont(text_font(TextRole.TITLE, self))
        self.title_label.setVisible(bool(title))
        self.body = QVBoxLayout()
        self.body.setSpacing(space(Space.TIGHT, self))
        outer = QVBoxLayout(self)
        apply_spacing(outer)
        outer.addWidget(self.title_label)
        outer.addLayout(self.body)

    def add(self, item: QWidget | QLayout) -> None:
        """Put *item* under what the panel already holds."""
        if isinstance(item, QLayout):
            self.body.addLayout(item)
        else:
            self.body.addWidget(item)


class StatusLine(QLabel):
    """One line that says how something went.

    :param parent: the widget it belongs to
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.state = State.NEUTRAL

    def show_state(self, state: State, text: str) -> None:
        """Show *text* in the theme's colour for *state*."""
        self.state = state
        palette = self.palette()
        palette.setColor(self.foregroundRole(), state_colour(state))
        self.setPalette(palette)
        self.setText(text)


def wrapping_row(*controls: QWidget) -> FlowLayout:
    """*controls* side by side, wrapping onto further lines when the panel is too narrow."""
    row = FlowLayout(gap=space(Space.TIGHT))
    row.setContentsMargins(0, 0, 0, 0)
    for control in controls:
        row.addWidget(control)
    return row
