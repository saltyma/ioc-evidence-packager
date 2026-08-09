"""Obsidian, violet, and amber visual system for the desktop workspace."""

APP_STYLESHEET = """
QWidget {
    color: #EEEAF6;
    background: #0D0A12;
    font-size: 13px;
}

QDialog#DetailDialog {
    background: #13101B;
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

QFrame#TopBar, QFrame#StatusBar {
    background: #13101B;
    border: none;
}

QFrame#TopBar {
    border-bottom: 1px solid #2B2538;
}

QFrame#StatusBar {
    border-top: 1px solid #2B2538;
}

QFrame#Sidebar {
    background: #13101B;
    border-right: 1px solid #2B2538;
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

QLabel#PrivacyBadge {
    color: #D7CBFF;
    background: #241C3B;
    border: 1px solid #604B91;
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 650;
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

QPushButton#NavButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    color: #B0A8BE;
    padding: 9px 12px;
    text-align: left;
    font-weight: 550;
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

QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox {
    color: #EFEAF6;
    background: #110E17;
    border: 1px solid #443A56;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #584187;
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

QTabBar::tab {
    color: #AFA6BF;
    background: #17131E;
    border: 1px solid #352E44;
    padding: 8px 14px;
    margin-right: 3px;
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
"""


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
