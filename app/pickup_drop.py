"""Temporary landing plank, gravity, tumble and recovery; no network or audio."""
import logging
import math
import random
import time

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRegion, QTransform, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from pet.drop_physics import Platform, advance, landing, recovery_pose, RECOVERY_SECONDS
from config.paths import resolve_resource_path

log = logging.getLogger(__name__)
RETORTS = (
    'wcnm',
    '你冯呢',
    '找YE揍呢',
)


class LandingPlank(QWidget):
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        self.setAccessibleName('临时接住师滔的平台')

    def paintEvent(self, _):
        # Measured cream / charcoal pair is 11.18:1; opposing outlines remain
        # visible over either light or dark desktop wallpaper. No tiny text.
        p = QPainter(self)
        p.setPen(QPen(QColor('#fff7df'), 4))
        p.setBrush(QColor('#403526'))
        p.drawRect(QRectF(2, 2, self.width()-4, 14))
        p.setPen(QPen(QColor('#403526'), 2))
        p.setBrush(QColor('#fff7df'))
        p.drawRect(QRectF(5, 5, self.width()-10, 5))


class PickupDrop(QObject):
    retort = Signal(str)
    started = Signal()

    def __init__(self, window, controller, character):
        super().__init__(window)
        self.window, self.controller, self.character = window, controller, character
        self.platform = None
        self.plank = LandingPlank(window)
        self.phase = 'idle'
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.tick)
        self._pix = None
        self._feet = window.height()

    @property
    def busy(self):
        return self.phase != 'idle'

    def begin(self):
        self.cancel()
        self.controller.start_drag()
        if self.character:
            self.character.set_dragging(True)
        self.phase = 'held'
        self._pix = self.window._sprite.pixmap()
        region = QRegion(self._pix.mask()).boundingRect() if self._pix and not self._pix.isNull() else self.window.rect()
        self._crop = self._pix.copy(region) if self._pix else None
        self._feet = self.window._sprite.y() + region.bottom() + 1
        self._sprite_feet = region.bottom() + 1
        form = 'chubby' if self.character and '微胖' in str(self.character._dir_path) else 'muscle'
        self._atlas = QPixmap(str(resolve_resource_path(f'assets/ui/drop-{form}.png')))
        self._art_scale = min(region.height()/96, max(1, self.window.width()-4)/116)
        width = max(84, min(170, region.width()))
        rect = self.window.frameGeometry()
        self.platform = Platform(rect.center().x()-width/2, rect.y()+self._feet, width)
        self.plank.setGeometry(round(self.platform.left), round(self.platform.top), width, 20)
        self.plank.show()
        self.started.emit()
        log.debug('Pickup started: platform=%s', self.platform)

    def release(self):
        if self.phase != 'held':
            return
        area = (QApplication.screenAt(self.window.frameGeometry().center()) or QApplication.primaryScreen()).availableGeometry()
        self._floor = area.bottom()+1
        self._y = float(self.window.y())
        self._velocity = 0.0
        self._last = time.monotonic()
        self.phase = 'falling'
        self._timer.start()
        self.tick()

    def tick(self):
        now = time.monotonic()
        if self.phase == 'falling':
            previous = self._y + self._feet
            self._y, self._velocity = advance(self._y, self._velocity, now-self._last)
            result, feet = landing(previous, self._y+self._feet, self.window.x()+self.window.width()/2, self.platform, self._floor)
            self._y = feet-self._feet
            self.controller.set_position(QPoint(self.window.x(), round(self._y)), clamp=False)
            self.paint_frame(0)
            if result == 'safe':
                log.debug('Pickup safely landed on platform')
                self.finish(False)
            elif result == 'floor':
                self.plank.hide()
                self.phase, self._impact = 'recovering', now
                log.debug('Pickup hit floor; playing tumble and get-up')
        if self.phase == 'recovering':
            elapsed = now-self._impact
            frame, stage = recovery_pose(elapsed)
            self.paint_frame(frame, stars=stage=='prone', elapsed=elapsed)
            if elapsed >= RECOVERY_SECONDS:
                self.finish(True)
        self._last = now

    def paint_frame(self, index, *, stars=False, elapsed=0):
        if self._atlas.isNull():
            return self.paint_pose(82 if index in (1,2,3) else 0)
        cell=self._atlas.copy(index*128,0,128,128)
        bounds=QRegion(cell.mask()).boundingRect()
        pose=cell.copy(bounds).scaled(round(bounds.width()*self._art_scale),round(bounds.height()*self._art_scale),Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.FastTransformation)
        canvas=QPixmap(self.window._sprite.size());canvas.fill(Qt.GlobalColor.transparent)
        p=QPainter(canvas);x=(canvas.width()-pose.width())//2;y=self._sprite_feet-pose.height()
        p.drawPixmap(x,y,pose)
        if stars:
            for j in range(3):
                a=elapsed*5+j*math.tau/3;cx=x+pose.width()*.73+math.cos(a)*25;cy=max(10,y-10)+math.sin(a)*7
                points=QPolygonF([QPointF(cx+math.cos(-math.pi/2+k*math.pi/5)*(6 if k%2==0 else 2.8),cy+math.sin(-math.pi/2+k*math.pi/5)*(6 if k%2==0 else 2.8)) for k in range(10)])
                p.setPen(QPen(QColor('#403526'),2));p.setBrush(QColor('#ffdd57'));p.drawPolygon(points)
        p.end();self.window._sprite.setPixmap(canvas)

    def paint_pose(self, angle):
        if not self._crop:
            return
        canvas = QPixmap(self.window._sprite.size())
        canvas.fill(Qt.GlobalColor.transparent)
        pose = self._crop.transformed(QTransform().rotate(angle), Qt.TransformationMode.FastTransformation)
        if pose.width() > canvas.width()-4:
            pose = pose.scaledToWidth(canvas.width()-4, Qt.TransformationMode.FastTransformation)
        p = QPainter(canvas)
        p.drawPixmap((canvas.width()-pose.width())//2, self._sprite_feet-pose.height(), pose)
        p.end()
        self.window._sprite.setPixmap(canvas)

    def finish(self, angry):
        self.cancel()
        if self.character and angry:
            self.character.play_action('08_angry')
        if angry:
            self.retort.emit(random.choice(RETORTS))

    def cancel(self):
        self._timer.stop()
        self.plank.hide()
        self.platform = None
        was_busy = self.busy
        self.phase = 'idle'
        if was_busy:
            if self.character:
                self.character.set_hover(False)
                self.character.set_dragging(False)
                self.window._on_pixmap(self.character.current_pixmap())
            self.controller.end_drag()
