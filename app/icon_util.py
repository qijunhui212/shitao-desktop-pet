from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from config.character_config import CHARACTER_MAX_HEIGHT, load_sprite_bindings, Trigger
from pet.animator import _make_placeholder_pixmap
from pet.character_assets import CharacterAssets
from pet.image_alpha import load_transparent_pixmap


def make_tray_icon(character: CharacterAssets | None = None) -> QIcon:
    if character and character.is_ready:
        return QIcon(character.tray_pixmap())

    _, bindings = load_sprite_bindings()
    for b in bindings:
        if b.trigger == Trigger.HOVER:
            pix = load_transparent_pixmap(str(b.path), CHARACTER_MAX_HEIGHT)
            if not pix.isNull():
                scaled = pix.scaled(
                    32,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                return QIcon(scaled)
    if bindings:
        pix = load_transparent_pixmap(str(bindings[0].path), CHARACTER_MAX_HEIGHT)
        if not pix.isNull():
            return QIcon(
                pix.scaled(
                    32,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    pix = _make_placeholder_pixmap(1)
    return QIcon(
        pix.scaled(
            32,
            32,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )
