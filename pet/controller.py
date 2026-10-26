import random

from enum import Enum, auto



from PySide6.QtCore import QObject, QPoint, QTimer, Signal

from PySide6.QtGui import QGuiApplication



from config.settings import WALK_INTERVAL_MS, WALK_SPEED





class PetState(Enum):

    IDLE = auto()

    WALK = auto()

    DRAG = auto()





class PetController(QObject):

    position_changed = Signal(int, int)

    state_changed = Signal(PetState)

    facing_changed = Signal(int)  # 1 right, -1 left



    def __init__(self, width: int, height: int, walk_enabled: bool = True, parent=None):

        super().__init__(parent)

        self._w = width

        self._h = height

        self._walk_enabled = walk_enabled

        self._state = PetState.IDLE

        self._facing = 1

        self._pos = QPoint(200, 200)

        self._target = QPoint(200, 200)

        self._dragging = False



        self._move_timer = QTimer(self)

        self._move_timer.timeout.connect(self._tick_move)

        if walk_enabled:

            self._move_timer.start(WALK_INTERVAL_MS)



        self._idle_timer = QTimer(self)

        self._idle_timer.timeout.connect(self._pick_walk_target)

        if walk_enabled:

            self._idle_timer.start(4000)

            self._pick_walk_target()



    def set_size(self, width: int, height: int) -> None:

        self._w = max(32, width)

        self._h = max(32, height)

        self.set_position(self._pos)



    def stop(self) -> None:

        self._move_timer.stop()

        self._idle_timer.stop()



    def set_walk_enabled(self, enabled: bool) -> None:

        self._walk_enabled = enabled

        if enabled:

            if not self._move_timer.isActive():

                self._move_timer.start(WALK_INTERVAL_MS)

            if not self._idle_timer.isActive():

                self._idle_timer.start(4000)

        else:

            self._move_timer.stop()

            self._idle_timer.stop()

            self._set_state(PetState.IDLE)



    @property

    def position(self) -> QPoint:

        return self._pos



    @property

    def state(self) -> PetState:

        return self._state



    @property

    def facing(self) -> int:

        return self._facing



    def set_position(self, pos: QPoint, *, clamp: bool = True) -> None:

        self._pos = self._clamp(pos) if clamp else pos

        self.position_changed.emit(self._pos.x(), self._pos.y())



    def center_on_screen(self, screen=None) -> None:

        """Place pet at center of given screen, or screen containing current pos."""

        if screen is None:

            screen = self._screen_at(self._pos) or QGuiApplication.primaryScreen()

        if not screen:

            return

        rect = screen.availableGeometry()

        x = rect.left() + (rect.width() - self._w) // 2

        y = rect.top() + (rect.height() - self._h) // 2

        self.set_position(QPoint(x, y))



    def start_drag(self) -> None:

        self._dragging = True

        self._set_state(PetState.DRAG)



    def end_drag(self) -> None:

        self._dragging = False

        self._set_state(PetState.IDLE)

        if self._walk_enabled:

            self._idle_timer.start(2000)



    def _screen_at(self, pos: QPoint):

        for screen in QGuiApplication.screens():

            if screen.geometry().contains(pos):

                return screen

        return QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()



    def _screen_rect(self):

        screen = self._screen_at(self._pos)

        if not screen:

            return None

        return screen.availableGeometry()



    def _clamp(self, pos: QPoint) -> QPoint:

        screen = self._screen_at(pos)
        rect = screen.availableGeometry() if screen else None

        if not rect:

            return pos

        x = max(rect.left(), min(pos.x(), rect.right() - self._w + 1))

        y = max(rect.top(), min(pos.y(), rect.bottom() - self._h + 1))

        return QPoint(x, y)



    def _set_state(self, state: PetState) -> None:

        if self._state != state:

            self._state = state

            self.state_changed.emit(state)



    def _pick_walk_target(self, *, force: bool = False) -> None:

        if self._dragging:

            return

        if not self._walk_enabled:

            return

        rect = self._screen_rect()

        if not rect:

            return

        if (

            not force

            and self._state == PetState.WALK

            and random.random() < 0.3

        ):

            self._set_state(PetState.IDLE)

            return

        self._target = QPoint(

            random.randint(rect.left(), max(rect.left(), rect.right() - self._w)),

            random.randint(rect.top(), max(rect.top(), rect.bottom() - self._h)),

        )

        self._set_state(PetState.WALK)



    def _tick_move(self) -> None:

        if not self._walk_enabled or self._dragging or self._state != PetState.WALK:

            return

        dx = self._target.x() - self._pos.x()

        dy = self._target.y() - self._pos.y()

        dist = (dx * dx + dy * dy) ** 0.5

        if dist < 4:

            self._set_state(PetState.IDLE)

            return

        step = WALK_SPEED

        nx = self._pos.x() + int(step * dx / dist)

        ny = self._pos.y() + int(step * dy / dist)

        if dx > 0:

            self._facing = 1

        elif dx < 0:

            self._facing = -1

        self.facing_changed.emit(self._facing)

        self.set_position(QPoint(nx, ny))


