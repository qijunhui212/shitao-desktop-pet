"""切换形象弹窗：从已安装形象包中选择并切换。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.dialog_theme import (
    apply_dialog_light_theme,
    apply_light_list_palette,
    picker_dialog_stylesheet,
    style_list_item,
)
from config.pack_discovery import list_pack_folder_names, pack_preview_image


class SwitchPackDialog(QDialog):
    switch_requested = Signal(str)

    def __init__(self, *, current_pack: str = "", parent=None):
        super().__init__(parent)
        self._current_pack = current_pack.strip()
        self._packs = list_pack_folder_names()

        self.setWindowTitle("切换形象")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(420, 380)
        apply_dialog_light_theme(self)
        self.setStyleSheet(picker_dialog_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        heading = QLabel("选择要使用的形象")
        heading.setObjectName("heading")
        root.addWidget(heading)

        current = self._current_pack or "（尚未选择）"
        self._current_lbl = QLabel(f"当前形象：{current}")
        self._current_lbl.setObjectName("hint")
        self._current_lbl.setWordWrap(True)
        root.addWidget(self._current_lbl)

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.setIconSize(QSize(40, 40))
        self._list.setSpacing(4)
        apply_light_list_palette(self._list)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(lambda _: self._on_switch())
        body.addWidget(self._list, stretch=3)

        preview_col = QVBoxLayout()
        self._preview_img = QLabel()
        self._preview_img.setObjectName("previewBox")
        self._preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_img.setFixedSize(140, 160)
        self._preview_title = QLabel("")
        self._preview_title.setObjectName("sectionTitle")
        self._preview_title.setWordWrap(True)
        preview_col.addWidget(self._preview_img, alignment=Qt.AlignmentFlag.AlignHCenter)
        preview_col.addWidget(self._preview_title)
        preview_col.addStretch()
        body.addLayout(preview_col, stretch=2)
        root.addLayout(body, stretch=1)

        hint = QLabel("选中后点「切换」或双击列表项；切换后立即生效，无需重启。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        self._switch_btn = QPushButton("切换")
        self._switch_btn.setDefault(True)
        self._switch_btn.clicked.connect(self._on_switch)
        btn_row.addWidget(close_btn)
        btn_row.addWidget(self._switch_btn)
        root.addLayout(btn_row)

        self._populate()

    def refresh(self, current_pack: str = "") -> None:
        self._current_pack = current_pack.strip()
        current = self._current_pack or "（尚未选择）"
        self._current_lbl.setText(f"当前形象：{current}")
        self._packs = list_pack_folder_names()
        self._populate()

    def _populate(self) -> None:
        self._list.clear()
        if not self._packs:
            item = QListWidgetItem("（暂无形象包，请先在设置里导入）")
            style_list_item(item)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            self._switch_btn.setEnabled(False)
            self._preview_img.setPixmap(QPixmap())
            self._preview_img.setText("预览")
            self._preview_title.setText("")
            return

        select_row = 0
        for i, name in enumerate(self._packs):
            label = f"{name}  ← 当前" if name == self._current_pack else name
            item = QListWidgetItem(label)
            style_list_item(item)
            item.setData(Qt.ItemDataRole.UserRole, name)
            thumb = pack_preview_image(name)
            if thumb and thumb.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                pix = QPixmap(str(thumb))
                if not pix.isNull():
                    item.setIcon(
                        QIcon(
                            pix.scaled(
                                40,
                                40,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    )
            self._list.addItem(item)
            if name == self._current_pack:
                select_row = i

        self._list.setCurrentRow(select_row)
        self._on_row_changed(select_row)

    def _selected_pack(self) -> str:
        item = self._list.currentItem()
        if not item:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._packs):
            self._switch_btn.setEnabled(False)
            return
        name = self._packs[row]
        self._preview_title.setText(name)
        self._switch_btn.setEnabled(bool(name) and name != self._current_pack)
        path = pack_preview_image(name)
        if path and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._preview_img.setPixmap(
                    pix.scaled(
                        130,
                        150,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._preview_img.setPixmap(QPixmap())
        self._preview_img.setText("预览")

    def _on_switch(self) -> None:
        name = self._selected_pack()
        if name and name != self._current_pack:
            self.switch_requested.emit(name)
            self._current_pack = name
            self.refresh(self._current_pack)
