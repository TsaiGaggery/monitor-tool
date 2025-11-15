#!/usr/bin/env python3
"""Dark theme stylesheet for the monitoring tool."""

DARK_THEME = """
/* Main Window */
QMainWindow {
    background-color: #1e1e1e;
    color: #e0e0e0;
}

/* Central Widget */
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Ubuntu", "Arial";
    font-size: 10pt;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #3a3a3a;
    background-color: #252525;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #a0a0a0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #0d7377;
    color: #ffffff;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #3a3a3a;
    color: #ffffff;
}

/* Group Box */
QGroupBox {
    background-color: #252525;
    border: 2px solid #3a3a3a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 15px;
    font-weight: bold;
    color: #14ffec;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    background-color: #252525;
    color: #14ffec;
}

/* Labels */
QLabel {
    color: #e0e0e0;
    background-color: transparent;
}

/* Status Bar */
QStatusBar {
    background-color: #2d2d2d;
    color: #14ffec;
    border-top: 1px solid #0d7377;
    padding: 4px;
}

QStatusBar::item {
    border: none;
}

/* Menu Bar */
QMenuBar {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border-bottom: 1px solid #3a3a3a;
}

QMenuBar::item {
    padding: 6px 12px;
    background-color: transparent;
}

QMenuBar::item:selected {
    background-color: #0d7377;
    color: #ffffff;
}

QMenu {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3a3a3a;
}

QMenu::item:selected {
    background-color: #0d7377;
    color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #0d7377;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #14ffec;
    color: #1e1e1e;
}

QPushButton:pressed {
    background-color: #0a5a5d;
}

QPushButton:disabled {
    background-color: #3a3a3a;
    color: #666666;
}

/* Combo Box */
QComboBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px;
}

QComboBox:hover {
    border: 1px solid #0d7377;
}

QComboBox::drop-down {
    border: none;
    background-color: #0d7377;
    width: 20px;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #0d7377;
    selection-color: #ffffff;
    border: 1px solid #3a3a3a;
}

/* Spin Box */
QSpinBox {
    background-color: #2d2d2d;
    color: #14ffec;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px;
    font-weight: bold;
}

QSpinBox:hover {
    border: 1px solid #0d7377;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #0d7377;
    border: none;
    width: 16px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #14ffec;
}

QSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 6px solid #ffffff;
}

QSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
}

/* Scroll Bar */
QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #0d7377;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #14ffec;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #2d2d2d;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #0d7377;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #14ffec;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Message Box */
QMessageBox {
    background-color: #252525;
    color: #e0e0e0;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* Tool Tip */
QToolTip {
    background-color: #2d2d2d;
    color: #14ffec;
    border: 1px solid #0d7377;
    border-radius: 4px;
    padding: 4px;
}

/* Plot Widget (Matplotlib integration) */
QFrame {
    background-color: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
}
"""

# Accent colors for charts
CHART_COLORS = {
    'cpu': '#ff6b6b',      # Red
    'gpu': '#4ecdc4',      # Cyan
    'memory': '#ffe66d',   # Yellow
    'npu': '#a8e6cf',      # Green
    'temperature': '#ff8b94', # Pink
    'power': '#ffd93d',    # Gold
    'grid': '#3a3a3a',     # Dark grid
    'background': '#1e1e1e',  # Dark background
    'text': '#e0e0e0'      # Light text
}

def apply_dark_theme(app):
    """Apply dark theme to QApplication."""
    app.setStyleSheet(DARK_THEME)
    return CHART_COLORS
