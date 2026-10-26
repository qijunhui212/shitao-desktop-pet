"""启动闪屏：显示当前形象。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

class SplashScreen(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        label = QLabel(self)
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resize(pixmap.size())
        label.setGeometry(0, 0, pixmap.width(), pixmap.height())

        self.setStyleSheet("background: transparent;")

    @staticmethod
    def from_character_pixmap(pix: QPixmap, max_height: int = 200) -> "SplashScreen | None":
        if pix.isNull():
            return None
        scaled = pix.scaledToHeight(
            max_height,
            Qt.TransformationMode.SmoothTransformation,
        )
        return SplashScreen(scaled)

    def show_centered(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move(
                g.left() + (g.width() - self.width()) // 2,
                g.top() + (g.height() - self.height()) // 2,
            )
        self.show()
        self.raise_()


def show_splash_then(callback, pixmap: QPixmap, duration_ms: int = 1200) -> None:
    splash = SplashScreen.from_character_pixmap(pixmap)
    if not splash:
        callback()
        return
    splash.show_centered()

    def _done():
        splash.close()
        callback()

    QTimer.singleShot(duration_ms, _done)
