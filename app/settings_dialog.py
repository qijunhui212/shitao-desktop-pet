"""Tray settings: run mode, chat API, startup picker."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)

from config.chat_api_config import (
    EXAMPLE_BASE_URLS,
    EXAMPLE_MODELS,
    ChatApiConfig,
    load_chat_api_config,
)
from config.env_update import should_show_character_picker
from app.dialog_theme import apply_dialog_light_theme, picker_dialog_stylesheet
from config.character_config import (
    CHARACTER_MAX_HEIGHT,
    CHARACTER_SIZE_MAX,
    CHARACTER_SIZE_MIN,
    clamp_character_height,
)
from config.pet_mode import is_survival_memory_mode, is_survival_mode


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        on_height_preview: Callable[[int], None] | None = None,
    ):
        super().__init__(parent)
        self._survival_mode = is_survival_mode()
        self._initial_survival = self._survival_mode
        self._show_picker = should_show_character_picker()
        self._on_height_preview = on_height_preview
        self._initial_height = clamp_character_height(CHARACTER_MAX_HEIGHT)
        self._survival_memory = is_survival_memory_mode()
        self._initial_survival_memory = self._survival_memory

        self.setWindowTitle("设置")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(480)
        apply_dialog_light_theme(self)
        self.setStyleSheet(
            picker_dialog_stylesheet()
            + """
            QLabel#sectionTitle { font-size: 14px; font-weight: bold; }
            QLabel#hint { font-size: 11px; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        heading = QLabel("桌面宠物设置")
        heading.setObjectName("heading")
        root.addWidget(heading)

        mode_title = QLabel("运行模式")
        mode_title.setObjectName("sectionTitle")
        root.addWidget(mode_title)
        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._rb_survival = QRadioButton("生存模式")
        self._rb_normal = QRadioButton("普通模式")
        self._mode_group.addButton(self._rb_survival, 1)
        self._mode_group.addButton(self._rb_normal, 0)
        if self._survival_mode:
            self._rb_survival.setChecked(True)
        else:
            self._rb_normal.setChecked(True)
        self._mode_group.idClicked.connect(self._on_mode_clicked)
        mode_row.addWidget(self._rb_survival)
        mode_row.addWidget(self._rb_normal)
        mode_row.addStretch()
        root.addLayout(mode_row)
        mode_hint = QLabel(
            "生存：HP 条、喂食与饿死复活 · 普通：仅陪伴与聊天。"
            "切换模式后需重新启动程序。"
        )
        mode_hint.setObjectName("hint")
        mode_hint.setWordWrap(True)
        root.addWidget(mode_hint)

        self._memory_cb = QCheckBox("生存记忆模式（关闭程序后仍按真实时间扣 HP）")
        self._memory_cb.setChecked(self._survival_memory)
        self._memory_cb.setToolTip(
            "开启：退出或未退出期间都会继续计时，久不打开可能离线饿死。\n"
            "关闭：仅桌宠程序在运行时扣 HP（原逻辑）。"
        )
        root.addWidget(self._memory_cb)
        memory_hint = QLabel("仅生存模式有效；保存后立即按新规则结算离线时间。")
        memory_hint.setObjectName("hint")
        memory_hint.setWordWrap(True)
        root.addWidget(memory_hint)
        self._rb_normal.toggled.connect(self._sync_memory_cb_enabled)
        self._rb_survival.toggled.connect(self._sync_memory_cb_enabled)
        self._sync_memory_cb_enabled()

        size_title = QLabel("宠物大小")
        size_title.setObjectName("sectionTitle")
        root.addWidget(size_title)
        size_row = QHBoxLayout()
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setMinimum(CHARACTER_SIZE_MIN)
        self._size_slider.setMaximum(CHARACTER_SIZE_MAX)
        self._size_slider.setValue(self._initial_height)
        self._size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._size_slider.setTickInterval(40)
        self._size_slider.valueChanged.connect(self._on_size_slider)
        self._size_label = QLabel()
        self._size_label.setObjectName("sizeValue")
        self._update_size_label(self._initial_height)
        size_row.addWidget(self._size_slider, stretch=1)
        size_row.addWidget(self._size_label)
        root.addLayout(size_row)
        size_hint = QLabel(
            f"拖动滑块调节立绘高度（{CHARACTER_SIZE_MIN}～{CHARACTER_SIZE_MAX} 像素），"
            "拖动时即时预览；点「保存」写入配置。"
        )
        size_hint.setObjectName("hint")
        size_hint.setWordWrap(True)
        root.addWidget(size_hint)

        api_title = QLabel("聊天 API（OpenAI 兼容）")
        api_title.setObjectName("sectionTitle")
        root.addWidget(api_title)
        api_cfg = load_chat_api_config()
        api_form = QFormLayout()
        api_form.setSpacing(8)
        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("各平台提供的 API Key")
        self._api_key.setText(api_cfg.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setClearButtonEnabled(True)
        api_form.addRow("API Key", self._api_key)
        self._api_base = QLineEdit()
        self._api_base.setPlaceholderText(
            "例如 " + " / ".join(EXAMPLE_BASE_URLS[:2])
        )
        self._api_base.setText(api_cfg.base_url)
        api_form.addRow("API 地址", self._api_base)
        self._api_model = QLineEdit()
        self._api_model.setPlaceholderText(
            "例如 " + "、".join(EXAMPLE_MODELS[:3])
        )
        self._api_model.setText(api_cfg.model)
        api_form.addRow("模型名称", self._api_model)
        root.addLayout(api_form)
        api_hint = QLabel(
            "支持 DeepSeek、OpenAI、Ollama、国内中转等；三项都填好才能聊天。"
            "密钥仅保存在本机 .env，不会上传。"
        )
        api_hint.setObjectName("hint")
        api_hint.setWordWrap(True)
        root.addWidget(api_hint)

        self._picker_cb = QCheckBox("每次启动时显示形象选择界面")
        self._picker_cb.setChecked(self._show_picker)
        root.addWidget(self._picker_cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def survival_mode_selected(self) -> bool:
        return self._survival_mode

    def mode_changed(self) -> bool:
        return self._survival_mode != self._initial_survival

    def survival_memory_selected(self) -> bool:
        return self._memory_cb.isChecked()

    def survival_memory_changed(self) -> bool:
        return self.survival_memory_selected() != self._initial_survival_memory

    def _sync_memory_cb_enabled(self) -> None:
        self._memory_cb.setEnabled(self._rb_survival.isChecked())

    def chat_api_config(self) -> ChatApiConfig:
        return ChatApiConfig(
            api_key=self._api_key.text().strip(),
            base_url=self._api_base.text().strip(),
            model=self._api_model.text().strip(),
        )

    def show_character_picker(self) -> bool:
        return self._picker_cb.isChecked()

    def max_height_selected(self) -> int:
        return clamp_character_height(self._size_slider.value())

    def max_height_changed(self) -> bool:
        return self.max_height_selected() != self._initial_height

    def _update_size_label(self, value: int) -> None:
        self._size_label.setText(f"{value} px")

    def _on_size_slider(self, value: int) -> None:
        v = clamp_character_height(value)
        self._update_size_label(v)
        if self._on_height_preview:
            self._on_height_preview(v)

    def _on_mode_clicked(self, button_id: int) -> None:
        self._survival_mode = button_id == 1

    def reject(self) -> None:
        if self._on_height_preview and self.max_height_changed():
            self._on_height_preview(self._initial_height)
        super().reject()

    def _on_save(self) -> None:
        self._survival_mode = self._rb_survival.isChecked()
        self._survival_memory = self._memory_cb.isChecked()
        self.accept()


def run_settings_dialog(
    parent=None,
    *,
    on_height_preview: Callable[[int], None] | None = None,
) -> SettingsDialog | None:
    dlg = SettingsDialog(parent, on_height_preview=on_height_preview)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg
