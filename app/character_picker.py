"""Startup / tray character selection dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from config.character_presets import (
    CharacterPreset,
    all_presets,
    detect_current_preset_id,
    preview_image_path,
)
from app.dialog_theme import (
    apply_dialog_light_theme,
    apply_light_list_palette,
    picker_dialog_stylesheet,
    style_list_item,
)
from config.chat_api_config import (
    ChatApiConfig,
    EXAMPLE_BASE_URLS,
    EXAMPLE_MODELS,
    load_chat_api_config,
)
from config.pet_mode import is_survival_memory_mode, is_survival_mode


class CharacterPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected: CharacterPreset | None = None
        self._remember = False
        self._survival_mode = True
        self._survival_memory = is_survival_memory_mode()

        self.setWindowTitle("选择形象")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(540, 580)
        apply_dialog_light_theme(self)
        self.setStyleSheet(picker_dialog_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        heading = QLabel("请选择桌面宠物形象")
        heading.setObjectName("heading")
        root.addWidget(heading)

        mode_title = QLabel("运行模式")
        mode_title.setObjectName("previewTitle")
        root.addWidget(mode_title)
        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._rb_survival = QRadioButton("生存模式")
        self._rb_normal = QRadioButton("普通模式")
        self._mode_group.addButton(self._rb_survival, 1)
        self._mode_group.addButton(self._rb_normal, 0)
        if is_survival_mode():
            self._rb_survival.setChecked(True)
        else:
            self._rb_normal.setChecked(True)
        self._mode_group.idClicked.connect(self._on_mode_clicked)
        mode_row.addWidget(self._rb_survival)
        mode_row.addWidget(self._rb_normal)
        mode_row.addStretch()
        root.addLayout(mode_row)
        mode_hint = QLabel(
            "生存：顶部 HP 条、喂食与饿死复活 · 普通：仅陪伴与聊天，无 HP"
        )
        mode_hint.setObjectName("modeHint")
        mode_hint.setWordWrap(True)
        root.addWidget(mode_hint)

        self._memory_cb = QCheckBox("生存记忆（关闭程序也计时，可能离线饿死）")
        self._memory_cb.setChecked(self._survival_memory)
        root.addWidget(self._memory_cb)
        self._rb_normal.toggled.connect(
            lambda on: self._memory_cb.setEnabled(not on)
        )
        self._memory_cb.setEnabled(self._rb_survival.isChecked())

        api_title = QLabel("聊天 API（OpenAI 兼容）")
        api_title.setObjectName("previewTitle")
        root.addWidget(api_title)
        api_cfg = load_chat_api_config()
        api_form = QFormLayout()
        api_form.setSpacing(8)
        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("各平台提供的 API Key")
        self._api_key.setText(api_cfg.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setClearButtonEnabled(True)
        api_form.addRow("API Key *", self._api_key)
        self._api_base = QLineEdit()
        self._api_base.setPlaceholderText(
            "例如 " + " / ".join(EXAMPLE_BASE_URLS[:2])
        )
        self._api_base.setText(api_cfg.base_url)
        api_form.addRow("API 地址 *", self._api_base)
        self._api_model = QLineEdit()
        self._api_model.setPlaceholderText(
            "例如 " + "、".join(EXAMPLE_MODELS[:3])
        )
        self._api_model.setText(api_cfg.model)
        api_form.addRow("模型名称 *", self._api_model)
        root.addLayout(api_form)
        api_hint = QLabel(
            "支持 DeepSeek、OpenAI、Ollama、国内中转等任意 OpenAI 兼容接口；"
            "三项都填好才能聊天，可先留空仅使用桌宠。密钥仅保存在本机 .env。"
        )
        api_hint.setObjectName("modeHint")
        api_hint.setWordWrap(True)
        root.addWidget(api_hint)

        body = QHBoxLayout()
        root.addLayout(body, stretch=1)

        self._list = QListWidget()
        self._list.setIconSize(QSize(48, 48))
        self._list.setSpacing(4)
        apply_light_list_palette(self._list)
        body.addWidget(self._list, stretch=3)

        preview_col = QVBoxLayout()
        self._preview_img = QLabel()
        self._preview_img.setObjectName("previewBox")
        self._preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_img.setFixedSize(180, 200)
        self._preview_title = QLabel("")
        self._preview_title.setObjectName("previewTitle")
        self._preview_title.setWordWrap(True)
        self._preview_sub = QLabel("")
        self._preview_sub.setObjectName("previewSub")
        self._preview_sub.setWordWrap(True)
        preview_col.addWidget(self._preview_img, alignment=Qt.AlignmentFlag.AlignHCenter)
        preview_col.addWidget(self._preview_title)
        preview_col.addWidget(self._preview_sub)
        preview_col.addStretch()
        body.addLayout(preview_col, stretch=2)

        self._remember_cb = QCheckBox(
            "下次启动不再询问（仍可在托盘「设置」或「切换形象」里修改）"
        )
        root.addWidget(self._remember_cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton("开始陪伴")
        self._start_btn.setDefault(True)
        self._start_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._start_btn)
        root.addLayout(btn_row)

        self._presets = all_presets()
        current_id = detect_current_preset_id()
        select_row = 0
        for i, preset in enumerate(self._presets):
            item = QListWidgetItem(f"{preset.title}\n{preset.subtitle}")
            style_list_item(item)
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            thumb = preview_image_path(preset)
            if thumb and thumb.suffix.lower() in (
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp",
            ):
                pix = QPixmap(str(thumb))
                if not pix.isNull():
                    item.setIcon(
                        QIcon(
                            pix.scaled(
                                48,
                                48,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    )
            self._list.addItem(item)
            if preset.id == current_id:
                select_row = i

        self._list.currentRowChanged.connect(self._on_row_changed)
        if self._presets:
            self._list.setCurrentRow(select_row)
            self._on_row_changed(select_row)

        self._list.itemDoubleClicked.connect(lambda _: self._on_accept())

    def selected_preset(self) -> CharacterPreset | None:
        return self._selected

    def remember_skip_picker(self) -> bool:
        return self._remember

    def survival_mode_selected(self) -> bool:
        return self._survival_mode

    def survival_memory_selected(self) -> bool:
        return self._memory_cb.isChecked()

    def chat_api_config(self) -> ChatApiConfig:
        return ChatApiConfig(
            api_key=self._api_key.text().strip(),
            base_url=self._api_base.text().strip(),
            model=self._api_model.text().strip(),
        )

    def _on_mode_clicked(self, button_id: int) -> None:
        self._survival_mode = button_id == 1

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._presets):
            return
        preset = self._presets[row]
        self._preview_title.setText(preset.title)
        self._preview_sub.setText(preset.subtitle)
        path = preview_image_path(preset)
        if path and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._preview_img.setPixmap(
                    pix.scaled(
                        170,
                        190,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._preview_img.setPixmap(QPixmap())
        self._preview_img.setText("预览")

    def _on_accept(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        self._selected = self._presets[row]
        self._remember = self._remember_cb.isChecked()
        self._survival_mode = self._rb_survival.isChecked()
        self._survival_memory = self._memory_cb.isChecked()
        self.accept()


def run_startup_character_selection() -> bool:
    """Show picker when enabled. Returns False if user cancelled."""
    from config.env_update import apply_preset, should_show_character_picker

    if not should_show_character_picker():
        return True

    dlg = CharacterPickerDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False
    preset = dlg.selected_preset()
    if preset is None:
        return False
    apply_preset(
        preset,
        remember_skip_picker=dlg.remember_skip_picker(),
        survival_mode=dlg.survival_mode_selected(),
        chat_api=dlg.chat_api_config(),
        survival_memory=dlg.survival_memory_selected(),
    )
    return True


def run_switch_character_dialog(parent=None) -> bool:
    """Tray menu: pick new character; caller should quit app after True."""
    from config.env_update import apply_preset

    dlg = CharacterPickerDialog(parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False
    preset = dlg.selected_preset()
    if preset is None:
        return False
    apply_preset(
        preset,
        remember_skip_picker=dlg.remember_skip_picker(),
        survival_mode=dlg.survival_mode_selected(),
        chat_api=dlg.chat_api_config(),
        survival_memory=dlg.survival_memory_selected(),
    )
    return True
