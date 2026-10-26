"""Light dialog theme — avoids Windows dark-mode making list text invisible."""

from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

TEXT_PRIMARY = "#5C4033"
TEXT_SECONDARY = "#8B7355"
BG_DIALOG = "#FFF8F0"
BG_INPUT = "#FFFFFF"
BG_LIST_ITEM_HOVER = "#FAF3E8"
BG_LIST_ITEM_SELECTED = "#F5E6C8"
BORDER = "#E8D5B5"
ACCENT = "#C9A227"


def apply_light_list_palette(widget: QListWidget) -> None:
    pal = widget.palette()
    text = QColor(TEXT_PRIMARY)
    base = QColor(BG_INPUT)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.Window, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#FAF6EF"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(BG_LIST_ITEM_SELECTED))
    pal.setColor(QPalette.ColorRole.HighlightedText, text)
    widget.setPalette(pal)
    widget.setAutoFillBackground(True)


def style_list_item(item: QListWidgetItem) -> None:
    item.setForeground(QBrush(QColor(TEXT_PRIMARY)))


def picker_dialog_stylesheet() -> str:
    return f"""
            QDialog {{ background: {BG_DIALOG}; color: {TEXT_PRIMARY}; }}
            QListWidget {{
                background: {BG_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 13px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 6px;
                border-bottom: 1px solid #F0E6D8;
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item:hover {{
                background: {BG_LIST_ITEM_HOVER};
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background: {BG_LIST_ITEM_SELECTED};
                color: {TEXT_PRIMARY};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
            }}
            QLabel#heading {{
                font-size: 16px;
                font-weight: bold;
                color: {TEXT_PRIMARY};
            }}
            QLabel#previewTitle {{ font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY}; }}
            QLabel#previewSub {{ font-size: 12px; color: {TEXT_SECONDARY}; }}
            QLabel#previewBox {{
                background: {BG_INPUT};
                border: 1px solid {BORDER};
                border-radius: 10px;
                color: {TEXT_PRIMARY};
            }}
            QLabel#modeHint {{ font-size: 11px; color: {TEXT_SECONDARY}; }}
            QPushButton {{
                background: {ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: #B8922A; }}
            QPushButton#cancelBtn {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
            }}
            QPushButton#cancelBtn:hover {{ background: {BG_LIST_ITEM_SELECTED}; }}
            QCheckBox {{ color: {TEXT_PRIMARY}; font-size: 12px; }}
            QRadioButton {{ color: {TEXT_PRIMARY}; font-size: 12px; }}
            QLineEdit, QComboBox {{
                background: {BG_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #E8D5B5;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                margin: -5px 0;
                background: {ACCENT};
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background: #E6D4A8;
                border-radius: 3px;
            }}
            QLabel#sizeValue {{
                font-weight: bold;
                min-width: 56px;
            }}
            """


def apply_dialog_light_theme(dialog: QWidget) -> None:
    """Force light palette on dialog (Windows 深色系统主题下也可读)."""
    pal = dialog.palette()
    text = QColor(TEXT_PRIMARY)
    pal.setColor(QPalette.ColorRole.Window, QColor(BG_DIALOG))
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Text, text)
    dialog.setPalette(pal)
