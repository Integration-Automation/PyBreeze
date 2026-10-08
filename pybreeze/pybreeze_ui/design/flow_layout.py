"""A row of controls that wraps onto the next line when the panel is too narrow for it.

A ``QHBoxLayout`` of buttons is as wide as all of them side by side, and its
panel cannot be made narrower: the Response Inspector's four hand-over buttons
and the diagram editor's toolbar kept their tabs from fitting a small screen,
and a tab that does not fit pushes the whole window wider than the display. A
:class:`FlowLayout` lays the same controls out left to right and starts a new
line when the next one would not fit, so the panel's least width is that of
its widest control.
"""
from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    """Lays its items out in lines, left to right, as many to a line as fit.

    :param parent: the widget to lay out, when the layout is not added to another
    :param gap: pixels between two items and between two lines; the style's own when negative
    """

    def __init__(self, parent: QWidget | None = None, gap: int = -1) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = gap

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, move=True)

    def sizeHint(self) -> QSize:
        """All on one line: what the row takes when there is room."""
        margins = self.contentsMargins()
        hints = [item.sizeHint() for item in self._items if not item.isEmpty()]
        width = sum(hint.width() for hint in hints) + self._gap_pixels() * max(0, len(hints) - 1)
        height = max((hint.height() for hint in hints), default=0)
        return QSize(width + margins.left() + margins.right(), height + margins.top() + margins.bottom())

    def minimumSize(self) -> QSize:
        """One item to a line: the widest item, and the tallest."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _gap_pixels(self) -> int:
        if self._gap >= 0:
            return self._gap
        spacing = self.spacing()
        return spacing if spacing >= 0 else 0

    def _arrange(self, rect: QRect, *, move: bool) -> int:
        """Place the items in *rect* line by line, or only measure when *move* is off.

        :return: the height the lines take, margins included
        """
        margins: QMargins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        gap = self._gap_pixels()
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            # The first item of a line stays on it however wide it is
            if x > area.x() and x + hint.width() > area.right() + 1:
                x, y, line_height = area.x(), y + line_height + gap, 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + gap
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()
