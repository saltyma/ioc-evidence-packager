"""Obsidian, violet, and amber visual system for the desktop workspace."""

from pathlib import Path

_COMBO_ARROW = (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()

APP_STYLESHEET = """
QWidget {
    color: #EEEAF6;
    background: #0D0A12;
    font-size: 13px;
}

QDialog#DetailDialog {
    background: #13101B;
}

QDialog#RelationshipGraphWindow {
    background: #0D0A12;
}

QLabel {
    background: transparent;
}

QToolTip {
    color: #F3EFFA;
    background: #211B2E;
    border: 1px solid #4B3F60;
    padding: 6px;
}

QFrame#StatusBar {
    background: #13101B;
    border: none;
}

QFrame#WorkspaceSurface {
    background: #0D0A12;
}

QFrame#StatusBar {
    border-top: 1px solid #2B2538;
}

QFrame#Sidebar {
    background: #12101A;
    border-right: 1px solid #2B2538;
}

QWidget#SidebarGap {
    background: transparent;
}

QFrame#FloatingActions {
    background: #191522;
    border: 1px solid #3E3550;
    border-radius: 12px;
}

QFrame#Panel, QFrame#HeroPanel, QFrame#MetricCard, QFrame#NoticeCard {
    background: #191522;
    border: 1px solid #352E44;
    border-radius: 10px;
}

QFrame#HeroPanel {
    background: #211936;
    border: 1px solid #5B4788;
}

QFrame#NoticeCard {
    background: #1C1726;
    border-left: 3px solid #F2B84B;
}

QLabel#BrandTitle {
    color: #F6F2FC;
    font-size: 15px;
    font-weight: 700;
}

QLabel#Muted, QLabel#FieldHint, QLabel#MetricLabel {
    color: #A49CB5;
}

QLabel#GraphZoomLabel {
    color: #D7CBFF;
    background: #17131E;
    border: 1px solid #352E44;
    border-radius: 6px;
    padding: 5px 7px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#SectionEyebrow {
    color: #E3B760;
    font-size: 11px;
    font-weight: 700;
}

QLabel#PageTitle {
    color: #F7F3FC;
    font-size: 27px;
    font-weight: 750;
}

QLabel#DetailTitle {
    color: #F7F3FC;
    font-size: 20px;
    font-weight: 700;
}

QLabel#PageSubtitle {
    color: #B1A9C0;
    font-size: 14px;
}

QLabel#MetricValue {
    color: #F4F0FA;
    font-size: 24px;
    font-weight: 750;
}

QLabel#CaseBadge {
    color: #B9F4D6;
    background: #14261E;
    border: 1px solid #35624E;
    border-radius: 10px;
    padding: 6px 11px;
    font-weight: 700;
}

QLabel#JobBadge {
    color: #9E96AC;
    background: #121019;
    border: 1px solid #302A3B;
    border-radius: 9px;
    padding: 5px 9px;
    font-size: 11px;
    font-weight: 650;
}

QLabel#JobBadge[active="true"] {
    color: #82E7B5;
    background: #12231E;
    border-color: #315D4C;
}

QLabel#StatusPill {
    color: #FFD98E;
    background: #2C2114;
    border: 1px solid #72552A;
    border-radius: 9px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#StepPill {
    color: #D7CBFF;
    background: #241C3B;
    border: 1px solid #604B91;
    border-radius: 9px;
    padding: 5px 9px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#MissionStep {
    color: #AAA2B8;
    background: #15121C;
    border: 1px solid #302A3C;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 20px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#MissionStep[state="done"] {
    color: #8EE7D9;
    background: #122521;
    border-color: #2F645B;
}

QLabel#MissionStep[state="current"] {
    color: #F8F3FF;
    background: #3A2B60;
    border-color: #8B6BE8;
}

QLabel#GraphLegendChip {
    color: #BDB4CB;
    background: #17131F;
    border: 1px solid #30293D;
    border-radius: 7px;
    padding: 5px 6px;
    font-size: 10px;
    font-weight: 650;
}

QFrame#GraphToolbar, QFrame#GraphLegendPanel {
    background: #15111C;
    border: 1px solid #30293D;
    border-radius: 9px;
}

QFrame#GraphLegendPanel {
    background: #121019;
}

QLabel#ValidationGood {
    color: #C9B8FF;
}

QLabel#ValidationError {
    color: #FFCA75;
}

QPushButton {
    background: #211B2E;
    border: 1px solid #443A56;
    border-radius: 7px;
    color: #E7E1F0;
    padding: 8px 13px;
    font-weight: 600;
}

QPushButton:hover {
    background: #2D2540;
    border-color: #695889;
}

QPushButton:pressed {
    background: #191421;
}

QPushButton:disabled {
    color: #716A7E;
    background: #17131E;
    border-color: #2A2434;
}

QPushButton#PrimaryButton {
    color: #130D1E;
    background: #9B7BFF;
    border-color: #9B7BFF;
}

QPushButton#PrimaryButton:hover {
    background: #B29BFF;
    border-color: #B29BFF;
}

QPushButton#GraphToolButton {
    padding: 6px 10px;
    min-height: 22px;
}

QPushButton#GraphOpenButton {
    color: #DCD1FF;
    background: #211A31;
    border-color: #554371;
    padding: 5px 11px;
}

QPushButton#GraphOpenButton:hover {
    color: #FFFFFF;
    background: #34264F;
    border-color: #8A6FBC;
}

QCheckBox {
    color: #B8B0C6;
    spacing: 7px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    background: #110E17;
    border: 1px solid #514461;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background: #8B6BE8;
    border-color: #B29BFF;
}

QPushButton#NavButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    color: #B0A8BE;
    padding: 9px 10px;
    text-align: left;
    font-weight: 550;
    min-height: 20px;
}

QPushButton#NavButton[collapsed="true"] {
    padding: 9px 0;
    text-align: center;
}

QPushButton#NavButton:hover {
    color: #F2EDF8;
    background: #1C1726;
}

QPushButton#NavButton:checked {
    color: #F6F1FF;
    background: #2A2145;
    border-color: #5D498E;
}

QPushButton#SidebarToggle {
    background: transparent;
    border: 1px solid transparent;
    padding: 6px;
}

QPushButton#SidebarToggle:hover {
    background: #211B2E;
    border-color: #443A56;
}

QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox {
    color: #EFEAF6;
    background: #110E17;
    border: 1px solid #443A56;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #584187;
}

QComboBox {
    padding-right: 34px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    border-left: 1px solid #352E44;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
    background: #17131F;
}

QComboBox::drop-down:hover {
    background: #241D32;
}

QComboBox::down-arrow {
    image: url("__COMBO_ARROW__");
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    color: #F0EAF7;
    background: #17131F;
    border: 1px solid #514363;
    selection-background-color: #443364;
    selection-color: #FFFFFF;
    outline: 0;
    padding: 4px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: #A78BFA;
}

QTextBrowser#DetailContent {
    background: #0E0B14;
    border-color: #4B3F60;
    padding: 12px;
}

QLabel#SemanticGood { color: #67D7A4; font-weight: 700; }
QLabel#SemanticWarn { color: #F2B84B; font-weight: 700; }
QLabel#SemanticDanger { color: #FF7F9F; font-weight: 700; }
QLabel#SemanticInfo { color: #70D6E8; font-weight: 700; }

QTableWidget {
    color: #E8E2F1;
    background: #120F19;
    alternate-background-color: #181420;
    border: 1px solid #352E44;
    border-radius: 8px;
    gridline-color: #2A2435;
    selection-background-color: #40305F;
    selection-color: #FAF7FF;
}

QTableWidget::item {
    padding: 4px;
}

QGraphicsView#RelationshipGraphCanvas {
    background: #0C0911;
    border: 1px solid #2D2738;
    border-radius: 10px;
}

QHeaderView::section {
    color: #A49CB5;
    background: #191522;
    border: none;
    border-bottom: 1px solid #352E44;
    padding: 8px;
    font-weight: 650;
}

QTabWidget::pane {
    border: 1px solid #352E44;
    border-radius: 8px;
    background: #100D16;
}

QTabWidget#RelationshipTabs::pane {
    border: none;
    background: transparent;
}

QWidget#RelationshipGraphPage {
    background: transparent;
}

QTabBar::tab {
    color: #AFA6BF;
    background: #17131E;
    border: 1px solid #352E44;
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}

QTabBar::tab:selected {
    color: #F5F0FC;
    background: #2A2145;
    border-color: #604B91;
}

QProgressBar {
    color: #EEEAF6;
    background: #110E17;
    border: 1px solid #443A56;
    border-radius: 6px;
    text-align: center;
    min-height: 18px;
}

QProgressBar::chunk {
    background: #8B6BE8;
    border-radius: 5px;
}

QScrollBar:vertical {
    background: #13101B;
    width: 11px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #4B405E;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #13101B;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #4B405E;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""

APP_STYLESHEET = APP_STYLESHEET.replace("__COMBO_ARROW__", _COMBO_ARROW)


def desktop_stylesheet(*, compact: bool, high_contrast: bool) -> str:
    """Return the visual system plus small device-local accessibility preferences."""

    additions: list[str] = []
    if compact:
        additions.append(
            """
            QWidget { font-size: 12px; }
            QPushButton { padding: 5px 10px; }
            QHeaderView::section { padding: 5px; }
            QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox {
                padding: 5px;
            }
            """
        )
    if not high_contrast:
        additions.append(
            """
            QLabel#SemanticGood, QLabel#SemanticWarn, QLabel#SemanticDanger,
            QLabel#SemanticInfo { color: #C9C1D5; }
            """
        )
    return APP_STYLESHEET + "\n".join(additions)
