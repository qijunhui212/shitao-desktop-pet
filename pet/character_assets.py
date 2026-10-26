"""Load character pack sprites and drive triggers (hover / random).

Supports per-state GIF animation when a .gif exists; PNG-only packs behave as before.

"""

from __future__ import annotations

import random

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from PySide6.QtGui import QPixmap, QTransform

from config.character_config import (

    MOOD_SWITCH_MS,

    SpriteBinding,

    Trigger,

    load_sprite_bindings,

    prefer_gif_playback,

    resolve_character_dir,

)

from config.settings import PET_HEIGHT, PET_WIDTH

from pet.animator import _make_placeholder_pixmap

from pet.gif_clip import GifClip

from pet.image_alpha import load_transparent_pixmap

@dataclass

class _StateMedia:

  static: QPixmap

  gif: GifClip | None

  animate: bool

class CharacterAssets(QObject):

    pixmap_changed = Signal(QPixmap)
    size_changed = Signal(int, int)
    action_finished = Signal(str)

    def __init__(self, parent=None):

        super().__init__(parent)

        self._dir_path = resolve_character_dir()

        self._bindings: list[SpriteBinding] = []

        self._hover: dict[str, _StateMedia] = {}

        self._random: dict[str, _StateMedia] = {}

        self._drag: dict[str, _StateMedia] = {}

        self._hovering = False

        self._dragging = False

        self._last_random: str | None = None

        self._last_hover: str | None = None

        self._last_drag: str | None = None

        self._facing = 1

        self._width = PET_WIDTH

        self._height = PET_HEIGHT

        self._manual_name = None
        self.transition_locked = False
        self._menu_open = False
        self._manual_timer = QTimer(self)
        self._manual_timer.setSingleShot(True)
        self._manual_timer.timeout.connect(self._finish_manual)
        self._ready = False

        self._active_gif: GifClip | None = None

        self._current_pix = QPixmap()

        self._mood_timer = QTimer(self)

        self._mood_timer.timeout.connect(self._pick_random)

        self._load()

        if self._ready:

            if self._random:

                self._mood_timer.start(MOOD_SWITCH_MS)

                self._pick_random()

            elif self._hover:

                self._show_state(next(iter(self._hover.values())))

        else:

            self._emit_pixmap(_make_placeholder_pixmap(1))

    def stop(self) -> None:
        self._manual_timer.stop()
        self._manual_name = None
        self._menu_open = False

        self._mood_timer.stop()

        self._stop_gif()

    def resume(self) -> None:
        """恢复随机/悬停动画（饿死复活后）。"""
        if not self._ready or self._hovering or self._dragging:
            return
        if self._random:
            if not self._mood_timer.isActive():
                self._mood_timer.start(MOOD_SWITCH_MS)
            self._pick_random()
        elif self._hover:
            self._show_state(next(iter(self._hover.values())))

    def reload(self) -> bool:
        """Reload sprites after .env / pack folder changed."""
        self.stop()
        self._hover.clear()
        self._random.clear()
        self._drag.clear()
        self._hovering = False
        self._dragging = False
        self._last_random = None
        self._last_hover = None
        self._last_drag = None
        self._ready = False
        self._current_pix = QPixmap()
        self._load()
        if self._ready:
            if self._random:
                self._mood_timer.start(MOOD_SWITCH_MS)
                self._pick_random()
            elif self._hover:
                self._show_state(next(iter(self._hover.values())))
        else:
            self._emit_pixmap(_make_placeholder_pixmap(self._facing))
        return self._ready

    @property

    def is_ready(self) -> bool:

        return self._ready

    @property

    def pack_path(self) -> str:

        return str(self._dir_path) if self._dir_path else ""

    @property

    def width(self) -> int:

        return self._width

    @property

    def height(self) -> int:

        return self._height

    def _load(self) -> None:

        from config.character_config import CHARACTER_MAX_HEIGHT

        dir_path, bindings = load_sprite_bindings()

        self._dir_path = dir_path

        self._bindings = bindings

        if not dir_path or not bindings:

            return

        use_gif = prefer_gif_playback(bindings)

        max_h = CHARACTER_MAX_HEIGHT

        for b in bindings:
            media_height = max_h * 2 if b.name == '13_group_dance' else max_h

            static = QPixmap()

            if b.png_path:

                static = load_transparent_pixmap(str(b.png_path), media_height)

            gif_clip: GifClip | None = None

            animate = False

            if b.gif_path and use_gif:

                gif_clip = GifClip(self)

                if gif_clip.load(str(b.gif_path), media_height):

                    gif_clip.frame_ready.connect(self._on_gif_frame)
                    gif_clip.finished.connect(self._finish_manual)

                    animate = True

                else:

                    gif_clip = None

            if static.isNull() and gif_clip and gif_clip.has_frames:

                static = gif_clip.poster

            if static.isNull() and not (gif_clip and gif_clip.has_frames):

                continue

            media = _StateMedia(static=static, gif=gif_clip, animate=animate)

            if b.trigger == Trigger.HOVER:

                self._hover[b.name] = media

            elif b.trigger == Trigger.DRAG:

                self._drag[b.name] = media

            else:

                self._random[b.name] = media

        self._ready = bool(self._hover or self._random or self._drag)

        if self._ready:

            sample = self._first_media()

            if sample and not sample.static.isNull():

                self._width = sample.static.width()

                self._height = sample.static.height()

    def _first_media(self) -> _StateMedia | None:

        if self._hover:

            return next(iter(self._hover.values()))

        if self._random:

            return next(iter(self._random.values()))

        return None

    def _stop_gif(self) -> None:
        if self._active_gif:

            self._active_gif.stop()

            self._active_gif = None

    def _on_gif_frame(self, pix: QPixmap) -> None:

        self._emit_pixmap(pix)

    def set_facing(self, facing: int) -> None:

        if self._facing == facing:

            return

        self._facing = facing

        if not self._current_pix.isNull():

            self._emit_pixmap(self._current_pix)

    @property
    def idle_for_sticker(self):
        return self._ready and not (self._hovering or self._dragging or self._menu_open or self._manual_name or self.transition_locked) and getattr(self, '_showing_idle', False)

    def available_actions(self) -> list[tuple[str, str]]:
        names = {
            "01_idle": "日常眨眼", "02_happy": "开心跳跃", "03_lifting": "举铁",
            "04_hover_petting": "害羞", "05_drag_happy": "拖动开心",
            "06_video_flex": "秀肌肉", "07_sprite_treadmill": "雪碧雪糕跑步机累晕",
            "08_angry": "急眼跺脚", "09_annoyed": "不爽叉腰", "10_cooldown": "抱臂消气",
            "13_group_dance": "群舞 · 六人烟雾登场",
            "14_costume_laugh": "穿黄皮套 · 捂肚大笑",
            "15_messi_siu": "梅西十号 · SIU",
            "16_protein": "蛋白粉 · 害羞挠头",
            "17_dj": "DJ · 窗外的天气",
            "18_coding": "坐下敲代码",
            "19_pigeon": "放鸽子",
        }
        pool = {**self._random, **self._hover, **self._drag}
        return [(key, names.get(key, key)) for key in sorted(pool) if not key.startswith(('11_transform','12_transform'))]

    def begin_action_menu(self) -> None:
        self._menu_open = True
        self._mood_timer.stop()

    def end_action_menu(self) -> None:
        self._menu_open = False
        if not self._manual_name:
            self._resume_automatic()

    def play_action(self, name: str) -> bool:
        if self.transition_locked or self._dragging:
            return False
        media = {**self._random, **self._hover, **self._drag}.get(name)
        if not media or not self._ready:
            return False
        self._manual_timer.stop()
        self._mood_timer.stop()
        self._stop_gif()
        self._manual_name = name
        if media.animate and media.gif:
            self._active_gif = media.gif
            media.gif.start(loop=False)
        else:
            self._emit_pixmap(media.static)
            self._manual_timer.start(1500)
        return True

    def _finish_manual(self) -> None:
        if not self._manual_name:
            return
        completed = self._manual_name
        self._manual_name = None
        self.transition_locked = False
        self._manual_timer.stop()
        self._resume_automatic()
        self.action_finished.emit(completed)

    def _resume_automatic(self) -> None:
        if not self._ready or self._menu_open or self._manual_name or self._dragging:
            return
        if self._hovering and self._hover:
            self._pick_hover()
        elif self._random:
            idle = self._random.get("01_idle")
            if idle:
                self._show_state(idle)
            else:
                self._pick_random()
            self._mood_timer.start(MOOD_SWITCH_MS)

    def set_hover(self, hovering: bool) -> None:
        if not self._ready or self._hovering == hovering:
            return
        self._hovering = hovering
        if self._dragging or self._manual_name or self._menu_open:
            return
        self._mood_timer.stop()
        self._resume_automatic()

    def set_dragging(self, dragging: bool) -> None:
        if self.transition_locked:
            return
        if not self._ready or self._dragging == dragging:
            return
        self._dragging = dragging
        if dragging:
            self._manual_name = None
            self._manual_timer.stop()
            self._mood_timer.stop()
            if self._drag:
                self._pick_drag()
            elif self._hover:
                self._pick_hover()
        else:
            self._resume_automatic()

    def _pick_from_pool(

        self,

        pool: dict[str, _StateMedia],

        last_key: str | None,

    ) -> str:

        keys = list(pool.keys())

        if len(keys) > 1 and last_key in keys:

            keys = [k for k in keys if k != last_key]

        return random.choice(keys)

    def _pick_hover(self) -> None:

        if not self._hover:

            return

        name = self._pick_from_pool(self._hover, self._last_hover)

        self._last_hover = name

        self._show_state(self._hover[name])

    def _pick_drag(self) -> None:

        if not self._drag:

            return

        name = self._pick_from_pool(self._drag, self._last_drag)

        self._last_drag = name

        self._show_state(self._drag[name])

    def _pick_random(self) -> None:

        if not self._ready or self._hovering or self._dragging or self._menu_open or self._manual_name or not self._random:

            return

        keys = [key for key in self._random if key not in ('08_angry','09_annoyed','10_cooldown','11_transform_chubby','12_transform_muscle','13_group_dance','14_costume_laugh','15_messi_siu','16_protein','17_dj','18_coding','19_pigeon')]
        if not keys:
            return

        if len(keys) > 1 and self._last_random in keys:

            keys = [k for k in keys if k != self._last_random]

        name = random.choice(keys)

        self._last_random = name

        self._show_state(self._random[name])

    def _show_state(self, media: _StateMedia, *, force: bool = False) -> None:
        self._showing_idle = media is self._random.get("01_idle")

        if (
            not force
            and media.animate
            and media.gif
            and self._active_gif is media.gif
            and media.gif.is_playing
        ):
            return

        self._stop_gif()

        if media.animate and media.gif:

            self._active_gif = media.gif

            media.gif.start(loop=True)

        elif not media.static.isNull():

            self._emit_pixmap(media.static)

    def _flip(self, pix: QPixmap) -> QPixmap:

        if self._facing >= 0:

            return pix

        return pix.transformed(QTransform().scale(-1, 1))

    def _emit_pixmap(self, pix: QPixmap) -> None:

        if pix.isNull():

            return

        self._current_pix = pix

        out = self._flip(pix)

        new_w, new_h = out.width(), out.height()

        if new_w != self._width or new_h != self._height:

            self._width = new_w

            self._height = new_h

            self.size_changed.emit(self._width, self._height)

        self.pixmap_changed.emit(out)

    def current_pixmap(self) -> QPixmap:

        if not self._current_pix.isNull():

            return self._flip(self._current_pix)

        media = None

        if self._dragging and self._drag:

            media = next(iter(self._drag.values()))

        elif self._hovering and self._hover:

            media = next(iter(self._hover.values()))

        elif self._random:

            media = next(iter(self._random.values()))

        elif self._hover:

            media = next(iter(self._hover.values()))

        if media and not media.static.isNull():

            return self._flip(media.static)

        return _make_placeholder_pixmap(self._facing)

    def tray_pixmap(self) -> QPixmap:

        media = self._first_media()

        src = media.static if media else QPixmap()

        if src.isNull():

            return _make_placeholder_pixmap(1).scaled(32, 32)

        return src.scaled(

            32,

            32,

            Qt.AspectRatioMode.KeepAspectRatio,

            Qt.TransformationMode.SmoothTransformation,

        )

