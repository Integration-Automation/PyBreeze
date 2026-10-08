"""A tool tab that shows what a run produced, whatever ran it.

A run of an automation package, a pytest run (JUnit XML), an MCP session: each
is opened into the same view (``utils/execution_report/``). On the left, the
runs and their results as a tree, each with how it ended and how long it took;
on the right, the selected result's details, its output, what it left behind,
and the package's own record of it. A line under them counts what is shown.

Several runs can be open at once and are filtered together: by ending, by time
taken, by package, by text. A run is exported as an execution report (JSON),
as JUnit XML for a CI service, or as an HTML page for people.

A report is a file from somewhere: everything in it is shown as text, and the
paths it names are listed, not opened.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.busy_cursor import busy_cursor
from pybreeze.pybreeze_ui.design.panels import StatusLine, wrapping_row
from pybreeze.pybreeze_ui.design.tokens import State, em
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.html_report import STATUS_WORDS
from pybreeze.utils.execution_report.report_files import EXPORT_FORMATS, read_report, write_report
from pybreeze.utils.execution_report.report_filter import ReportFilter, leaf_counts, total_seconds
from pybreeze.utils.execution_report.report_schema import ExecutionReport, ExecutionResult, Status, rolled_up
from pybreeze.utils.json_format.view_safe import dumps_for_view
from pybreeze.utils.logging.logger import pybreeze_logger

# The columns of the tree
_NAME, _STATUS, _SECONDS = range(3)
# Where an item keeps the report or the result it stands for, and the report it belongs to
_SHOWN_ROLE = Qt.ItemDataRole.UserRole
_REPORT_ROLE = Qt.ItemDataRole.UserRole + 1
# How wide the Name column starts, in ems; the others take what they need
_NAME_WIDTH = 28
# The longest a result may have taken for the "at least" box to ask for
_MOST_SECONDS = 86_400.0


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _status_word(status: Status) -> str:
    return _word(STATUS_WORDS[status])


def _when(seconds: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds)) if seconds is not None else ""


def _took(seconds: float | None) -> str:
    return f"{seconds:.2f}" if seconds is not None else ""


@dataclass(frozen=True)
class _ShownRun:
    """What a run's item stands for: the results of the run that pass the filter.

    An object of its own: a tuple kept as an item's data comes back from Qt as a list.
    """

    results: tuple[ExecutionResult, ...]


def _read_only_view() -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    use_fixed_pitch_font(view)
    return view


class ReportFilterBar(QWidget):
    """The controls that say what is shown: endings, time taken, package, text."""

    def __init__(self) -> None:
        super().__init__()
        self.status_boxes: dict[Status, QCheckBox] = {}
        for status in STATUS_WORDS:
            box = QCheckBox(_status_word(status))
            box.setChecked(True)
            self.status_boxes[status] = box
        self.seconds_label = QLabel(_word("report_viewer_at_least_label"))
        self.seconds_spin = QDoubleSpinBox()
        self.seconds_spin.setRange(0.0, _MOST_SECONDS)
        self.seconds_spin.setDecimals(2)
        self.seconds_spin.setSingleStep(0.5)
        self.framework_select = QComboBox()
        self.framework_select.addItem(_word("report_viewer_every_framework"), "")
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText(_word("report_viewer_filter_placeholder"))
        self.text_edit.setClearButtonEnabled(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(wrapping_row(
            *self.status_boxes.values(), self.seconds_label, self.seconds_spin, self.framework_select,
            self.text_edit))

    def on_change(self, changed) -> None:
        """Call *changed* whenever what is asked for changes."""
        for box in self.status_boxes.values():
            box.toggled.connect(changed)
        self.seconds_spin.valueChanged.connect(changed)
        self.framework_select.currentIndexChanged.connect(changed)
        self.text_edit.textChanged.connect(changed)

    def wanted(self) -> ReportFilter:
        """What is asked for now."""
        framework = self.framework_select.currentData()
        return ReportFilter(
            statuses=frozenset(status for status, box in self.status_boxes.items() if box.isChecked()),
            at_least_seconds=self.seconds_spin.value(), text=self.text_edit.text(),
            frameworks=frozenset({framework}) if framework else frozenset())

    def offer_frameworks(self, frameworks: list[str]) -> None:
        """Offer *frameworks* to choose from, keeping the one chosen when it is still among them."""
        chosen = self.framework_select.currentData()
        self.framework_select.blockSignals(True)
        try:
            while self.framework_select.count() > 1:
                self.framework_select.removeItem(1)
            for framework in frameworks:
                self.framework_select.addItem(framework, framework)
            self.framework_select.setCurrentIndex(max(self.framework_select.findData(chosen), 0))
        finally:
            self.framework_select.blockSignals(False)


class ReportDetails(QTabWidget):
    """What is known of the selected run or result: its details, its output, what it left behind, its own record."""

    def __init__(self) -> None:
        super().__init__()
        self.detail_view = _read_only_view()
        self.output_view = _read_only_view()
        self.attachments_view = _read_only_view()
        self.raw_view = _read_only_view()
        for view, key in ((self.detail_view, "report_viewer_tab_details"), (self.output_view, "report_viewer_tab_output"),
                          (self.attachments_view, "report_viewer_tab_attachments"),
                          (self.raw_view, "report_viewer_tab_raw")):
            self.addTab(view, _word(key))

    def show_nothing(self) -> None:
        for view in (self.detail_view, self.output_view, self.attachments_view, self.raw_view):
            view.clear()

    def show_report(self, report: ExecutionReport) -> None:
        """Show a run: what ran it, how it ended, how many of each ending, and the package's own report."""
        counts = report.counts()
        lines = [report.name or report.framework, report.framework, _status_word(report.status),
                 *(f"{_status_word(status)}: {counts[status]}" for status in STATUS_WORDS if counts[status]),
                 _when(report.started),
                 _word("report_html_seconds").format(seconds=_took(report.duration))
                 if report.duration is not None else ""]
        self.detail_view.setPlainText("\n".join(line for line in lines if line))
        self.output_view.clear()
        self.attachments_view.clear()
        self.raw_view.setPlainText(dumps_for_view(report.raw, indent=2) if report.raw is not None else "")

    def show_result(self, result: ExecutionResult) -> None:
        """Show a result: how it ended and why, what it wrote, what it left behind, and its own record."""
        error = result.error
        lines = [result.name, f"{result.kind.value} · {_status_word(result.status)}", _when(result.started),
                 _word("report_html_seconds").format(seconds=_took(result.duration))
                 if result.duration is not None else "",
                 f"{error.kind}: {error.message}" if error is not None and error.kind else (
                     error.message if error is not None else ""),
                 error.trace if error is not None else "", f"id {result.id}"]
        self.detail_view.setPlainText("\n\n".join(line for line in lines if line))
        self.output_view.setPlainText("\n".join(filter(None, (result.stdout, result.stderr))))
        # The paths are a file's word: listed, never opened from here
        self.attachments_view.setPlainText("\n".join(
            " · ".join(filter(None, (attachment.name, attachment.path, attachment.media_type)))
            for attachment in result.attachments))
        self.raw_view.setPlainText(dumps_for_view(result.raw, indent=2) if result.raw is not None else "")


class ReportViewerGUI(QWidget):
    """Open runs of any package, look through their results, filter them, and export them."""

    def __init__(self) -> None:
        super().__init__()
        self._reports: list[ExecutionReport] = []

        self.open_button = QPushButton(_word("report_viewer_open_button"))
        self.open_button.clicked.connect(self.open_reports)
        self.export_button = QPushButton(_word("report_viewer_export_button"))
        self.export_button.clicked.connect(self.export_report)
        self.close_button = QPushButton(_word("report_viewer_close_button"))
        self.close_button.clicked.connect(self.close_report)
        self.filter_bar = ReportFilterBar()
        self.filter_bar.on_change(self._show_reports)

        self.result_tree = QTreeWidget()
        self.result_tree.setColumnCount(3)
        self.result_tree.setHeaderLabels([
            _word("report_column_name"), _word("report_column_status"), _word("report_column_seconds")])
        self.result_tree.setColumnWidth(_NAME, _NAME_WIDTH * em(self.result_tree))
        self.result_tree.itemExpanded.connect(self._fill)
        self.result_tree.currentItemChanged.connect(self._show_selected)
        self.details = ReportDetails()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.result_tree)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.summary = StatusLine()

        layout = QVBoxLayout()
        layout.addLayout(wrapping_row(self.open_button, self.export_button, self.close_button))
        layout.addWidget(self.filter_bar)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.summary)
        self.setLayout(layout)
        self._show_reports()

    # ------------------------------------------------------------------
    # The runs
    # ------------------------------------------------------------------

    def reports(self) -> list[ExecutionReport]:
        """The runs that are open, in the order they were opened."""
        return list(self._reports)

    def show_report(self, report: ExecutionReport) -> None:
        """Add *report* to the runs shown: how another tool hands a run over."""
        self._reports.append(report)
        self.filter_bar.offer_frameworks(sorted({each.framework for each in self._reports}))
        self._show_reports()

    @busy_cursor()
    def open_files(self, paths: list[str]) -> int:
        """Open each of *paths* as a run; say which could not be read. Return how many were opened."""
        opened = 0
        problem = ""
        for path in paths:
            try:
                report = read_report(Path(path))
            except (ExecutionReportException, OSError) as error:
                pybreeze_logger.info("report_viewer_gui.py %s not opened: %r", Path(path).name, error)
                # A reason without the path: an OSError's own message carries it
                reason = error_text(str(error)) if isinstance(error, ExecutionReportException) else (
                    error.strerror or type(error).__name__)
                problem = _word("report_viewer_not_read").format(file=Path(path).name, reason=reason)
                continue
            self._reports.append(report)
            opened += 1
        self.filter_bar.offer_frameworks(sorted({each.framework for each in self._reports}))
        self._show_reports()
        if problem:
            self.summary.show_state(State.ERROR, problem)
        return opened

    def open_reports(self) -> int:
        """Ask for report files and open them; return how many were opened."""
        paths, _selected = QFileDialog.getOpenFileNames(
            self, _word("report_viewer_open_title"), "", _word("report_viewer_open_filter"))
        return self.open_files(paths) if paths else 0

    def selected_report(self) -> ExecutionReport | None:
        """The run the selection is in; the only run when nothing is selected and there is but one."""
        item = self.result_tree.currentItem()
        if item is not None:
            return item.data(_NAME, _REPORT_ROLE)
        return self._reports[0] if len(self._reports) == 1 else None

    def close_report(self) -> bool:
        """Take the selected run out of the view; return whether one was."""
        report = self.selected_report()
        if report is None:
            return False
        self._reports = [each for each in self._reports if each is not report]
        self.filter_bar.offer_frameworks(sorted({each.framework for each in self._reports}))
        self._show_reports()
        return True

    def export_report(self) -> str | None:
        """Save the selected run in the format chosen in the dialog; return the path, or ``None``."""
        report = self.selected_report()
        if report is None:
            return None
        filters = {f"{_word(each.label_key)} (*.{each.extension})": each for each in EXPORT_FORMATS}
        path, chosen = QFileDialog.getSaveFileName(
            self, _word("report_viewer_export_title"), report.name or report.framework, ";;".join(filters))
        if not path:
            return None
        wanted = filters.get(chosen, EXPORT_FORMATS[0])
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(f".{wanted.extension}")
        try:
            write_report(report, target, wanted, language_wrapper.language_word_dict)
        except (OSError, UnicodeEncodeError) as error:
            pybreeze_logger.error("report_viewer_gui.py report not saved: %r", error)
            reason = error.strerror if isinstance(error, OSError) and error.strerror else type(error).__name__
            self.summary.show_state(State.ERROR, _word("output_actions_save_failed_message").format(
                file=target.name, error=reason))
            return None
        self.summary.show_state(State.SUCCESS, _word("report_viewer_exported").format(file=target.name))
        return str(target)

    # ------------------------------------------------------------------
    # The tree
    # ------------------------------------------------------------------

    def _show_reports(self, *_changed) -> None:
        """Show the runs through the filter, and count what is shown."""
        wanted = self.filter_bar.wanted()
        self.result_tree.clear()
        shown: list[ExecutionResult] = []
        for report in self._reports:
            if not wanted.takes_report(report):
                continue
            results = wanted.of(report.results)
            if not results and not wanted.shows_everything():
                continue
            item = QTreeWidgetItem([
                report.name or report.framework,
                _status_word(rolled_up(result.status for result in results)), _took(report.duration)])
            item.setData(_NAME, _SHOWN_ROLE, _ShownRun(results))
            item.setData(_NAME, _REPORT_ROLE, report)
            if results:
                item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            self.result_tree.addTopLevelItem(item)
            item.setExpanded(True)
            shown.extend(results)
        self._show_summary(tuple(shown))
        has_run = bool(self._reports)
        self.export_button.setEnabled(has_run)
        self.close_button.setEnabled(has_run)
        if self.result_tree.topLevelItemCount():
            self.result_tree.setCurrentItem(self.result_tree.topLevelItem(0))
        else:
            self.details.show_nothing()

    def _fill(self, item: QTreeWidgetItem) -> None:
        """Give *item* an item for each result it holds, when it has none yet.

        Made as an item is opened, not for the whole run: a load test is tens
        of thousands of results, and a view lays out every item it is given.
        """
        if item.childCount():
            return
        shown = item.data(_NAME, _SHOWN_ROLE)
        results = shown.results if isinstance(shown, _ShownRun) else shown.children
        report = item.data(_NAME, _REPORT_ROLE)
        children = []
        for result in results:
            child = QTreeWidgetItem([result.name, _status_word(result.status), _took(result.duration)])
            child.setData(_NAME, _SHOWN_ROLE, result)
            child.setData(_NAME, _REPORT_ROLE, report)
            if result.children:
                child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            children.append(child)
        item.addChildren(children)

    def _show_selected(self, *_items) -> None:
        item = self.result_tree.currentItem()
        if item is None:
            self.details.show_nothing()
            return
        shown = item.data(_NAME, _SHOWN_ROLE)
        if isinstance(shown, ExecutionResult):
            self.details.show_result(shown)
        else:
            self.details.show_report(item.data(_NAME, _REPORT_ROLE))

    def _show_summary(self, shown: tuple[ExecutionResult, ...]) -> None:
        """Count what is shown: how many results, of how many, and how many of each ending."""
        if not self._reports:
            self.summary.show_state(State.NEUTRAL, _word("report_viewer_nothing_open"))
            return
        counts = leaf_counts(shown)
        every = sum(sum(report.counts().values()) for report in self._reports)
        endings = " · ".join(f"{_status_word(status)}: {counts[status]}" for status in STATUS_WORDS if counts[status])
        failed = counts[Status.FAILED] or counts[Status.ERROR]
        self.summary.show_state(
            State.ERROR if failed else State.SUCCESS,
            _word("report_viewer_summary").format(
                shown=sum(counts.values()), every=every, runs=len(self._reports),
                seconds=_took(total_seconds(shown))) + (f" · {endings}" if endings else ""))
