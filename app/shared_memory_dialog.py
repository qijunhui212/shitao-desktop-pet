import json
import logging
import threading
from PySide6.QtCore import QObject, Signal, QTimer, Slot
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,
    QPushButton,QCheckBox,QHBoxLayout,QInputDialog,QMessageBox,QPlainTextEdit)
from PySide6.QtGui import QFont
from memory import shared
from memory.events import read_events
from config.paths import app_root

log=logging.getLogger(__name__)


class BackgroundJob(QObject):
    done=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.running=False
    def start(self,task):
        if self.running:return False
        self.running=True
        def work():
            try:message=task()
            except Exception as exc:
                log.warning('Knowledge operation failed type=%s',type(exc).__name__)
                message='操作失败：'+(str(exc) if isinstance(exc,ValueError) else '网络或文件不可用，请稍后重试；原记忆保留。')
            try:self.done.emit(message)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start();return True


class SyncController(QObject):
    status=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.callback = None
        self.job=BackgroundJob(self);self.job.done.connect(self._completed)
        self.timer=QTimer(self);self.timer.setInterval(600000);self.timer.timeout.connect(self.sync)
        self.timer.start();QTimer.singleShot(3000,self.sync)
    @Slot(str)
    def _completed(self, text):
        self.job.running = False
        callback, self.callback = self.callback, None
        self.status.emit(text)
        if callback:
            try:callback(text)
            except RuntimeError:pass
    def _start(self, task, callback=None):
        if self.job.running:
            if callback:callback('共享同步正在进行中，请稍后再试。')
            return False
        self.callback = callback
        return self.job.start(task)
    def sync(self, callback=None):
        try:
            if not shared.settings().get('enabled'):
                if callback:callback('未启用共享同步，请先配置共享知识库。')
                return
        except (OSError,ValueError):return
        if self._start(shared.sync_once, callback):self.status.emit('正在检查共享知识库…')

    def submit_card(self, card, callback=None, expected_updated_at=None):
        def task():
            version = shared.upsert_card(card, expected_updated_at=expected_updated_at)
            try:return f'已提交到共享知识库 v{version}；{shared.sync_once()}'
            except Exception:return f'已提交 v{version}，下载缓存暂时失败；请点刷新共享，不要重复新增。'
        return self._start(task, callback)

    def remove_card(self, card_id, expected_updated_at=None, callback=None):
        def task():
            version = shared.delete_card(card_id, expected_updated_at=expected_updated_at)
            try:return f'已从共享知识库删除（v{version}）；{shared.sync_once()}'
            except Exception:return f'已删除（v{version}），缓存未刷新；请点刷新共享。'
        return self._start(task, callback)


class SharedMemoryDialog(QDialog):
    def __init__(self,controller,parent=None):
        super().__init__(parent);self.controller=controller
        self.setFont(QFont('Microsoft YaHei UI',10));self.setWindowTitle('共享知识库');self.resize(580,390)
        layout=QVBoxLayout(self)
        label=QLabel('启用后，启动及每10分钟下载共享记忆。个人聊天不会自动上传。\n每个持有共享密钥的人都可以提交新增、修改和删除；每次只提交一张已确认的记忆卡，不会覆盖别人的卡。')
        label.setWordWrap(True);layout.addWidget(label)
        self.enabled=QCheckBox('启用共享知识库自动同步');layout.addWidget(self.enabled)
        form=QFormLayout();self.url=QLineEdit();self.token=QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('同步地址',self.url);form.addRow('共享密钥',self.token);layout.addLayout(form)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        self.controller.status.connect(self.status.setText)
        row=QHBoxLayout()
        for title,callback in [('保存设置',self.save),('立即同步',self.sync),('关闭',self.accept)]:
            b=QPushButton(title);b.clicked.connect(callback);row.addWidget(b)
        layout.addLayout(row)
        try:
            c=shared.settings();self.enabled.setChecked(c.get('enabled',False));self.url.setText(c.get('url',''));self.token.setText(c.get('token',''))
        except (OSError,ValueError):self.status.setText('同步设置无法读取，可重新填写。')
    def save(self):
        try:
            shared.configure(self.enabled.isChecked(),self.url.text(),self.token.text());self.status.setText('设置已保存');return True
        except (OSError,ValueError) as exc:self.status.setText(str(exc));return False
    def sync(self):
        if self.save():self.controller.sync()
