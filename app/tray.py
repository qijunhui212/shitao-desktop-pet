from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.icon_util import make_tray_icon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, app_controller, parent=None):
        super().__init__(parent)
        self._app = app_controller
        icon = make_tray_icon(getattr(app_controller, "character", None))
        self.setIcon(icon)
        name = getattr(app_controller, "_pet_name", None) or "桌宠"
        self.setToolTip(f"桌面宠物 · {name}")

        menu = QMenu()
        chat_action = QAction("聊天", menu)
        chat_action.triggered.connect(self._app.open_chat)
        menu.addAction(chat_action)

        wechat_action = QAction("微信群接入…", menu)
        wechat_action.triggered.connect(self._app.open_wechat_bridge)
        menu.addAction(wechat_action)

        remind_action = QAction("管理提醒", menu)
        remind_action.triggered.connect(self._app.show_reminders)
        menu.addAction(remind_action)

        center_action = QAction("居中到当前屏幕", menu)
        center_action.triggered.connect(self._app.center_pet)
        menu.addAction(center_action)

        import_action = QAction("导入形象文件夹…", menu)
        import_action.triggered.connect(self._app.pick_and_import_pack)
        menu.addAction(import_action)

        switch_action = QAction("切换形象", menu)
        switch_action.triggered.connect(self._app.switch_character)
        menu.addAction(switch_action)

        settings_action = QAction("设置…", menu)
        settings_action.triggered.connect(self._app.open_settings)
        menu.addAction(settings_action)

        help_action = QAction("使用说明", menu)
        help_action.triggered.connect(self._app.show_help)
        menu.addAction(help_action)

        about_action = QAction("关于", menu)
        about_action.triggered.connect(self._app.show_about)
        menu.addAction(about_action)

        clear_action = QAction("清空对话记录", menu)
        clear_action.triggered.connect(self._app.clear_chat_history)
        menu.addAction(clear_action)

        menu.addSeparator()
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._app.open_chat()

    def notify(self, title: str, message: str) -> None:
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)
