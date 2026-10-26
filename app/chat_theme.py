"""Warm cream composer, with a native-system high-contrast fallback."""
from PySide6.QtGui import QColor,QPalette
TOKENS={'surface':'#FFF9E9','card':'#FFFCF4','ink':'#332B1D','muted':'#695736','border':'#9A8257','accent':'#70521A','accentHover':'#543D13'}
def apply_theme(widget):
    high=False
    try:
        import ctypes
        class HC(ctypes.Structure):
            _fields_=[('cbSize',ctypes.c_uint),('dwFlags',ctypes.c_uint),('scheme',ctypes.c_wchar_p)]
        h=HC();h.cbSize=ctypes.sizeof(h)
        high=bool(ctypes.windll.user32.SystemParametersInfoW(0x42,h.cbSize,ctypes.byref(h),0) and h.dwFlags&1)
    except (AttributeError,OSError):pass
    widget._high_contrast=high
    if high:return
    t=TOKENS
    palette=widget.palette()
    for role,color in [(QPalette.ColorRole.Window,t['surface']),(QPalette.ColorRole.WindowText,t['ink']),(QPalette.ColorRole.Text,t['ink']),(QPalette.ColorRole.Base,t['card']),(QPalette.ColorRole.Button,t['card']),(QPalette.ColorRole.ButtonText,t['ink']),(QPalette.ColorRole.PlaceholderText,t['muted']),(QPalette.ColorRole.Highlight,t['accent']),(QPalette.ColorRole.HighlightedText,t['card'])]:palette.setColor(role,QColor(color))
    widget.setPalette(palette)
    widget.setStyleSheet('''
QDialog {background:SURFACE;color:INK;}
QLabel {background:transparent;color:INK;}
QLabel#composerTitle {font-size:22px;font-weight:700;}
QLineEdit,QPlainTextEdit {background:CARD;color:INK;border:1px solid BORDER;border-radius:12px;padding:10px;selection-background-color:ACCENT;selection-color:CARD;}
QLineEdit:focus,QPlainTextEdit:focus {border:2px solid ACCENT;}
QPushButton {background:CARD;color:INK;border:1px solid BORDER;border-radius:10px;padding:8px 13px;min-height:22px;}
QPushButton:hover {background:SURFACE;border:1px solid ACCENT;}
QPushButton:focus {border:2px solid ACCENT;}
QPushButton#sendPrimary {background:ACCENT;color:CARD;border:1px solid ACCENT;font-weight:600;}
QPushButton#sendPrimary:hover {background:HOVER;}
QCheckBox {color:INK;background:transparent;spacing:7px;}
'''.replace('SURFACE',t['surface']).replace('CARD',t['card']).replace('INK',t['ink']).replace('BORDER',t['border']).replace('ACCENT',t['accent']).replace('HOVER',t['accentHover']))
