"""Explicit review/confirm flow. All memory operations work without an API."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPlainTextEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QPushButton, QComboBox, QMessageBox)
from memory.events import STATUSES, read_events, save_event, delete_event


class EventMemoryDialog(QDialog):
    def __init__(self, parent=None, *, draft='', history=(), card=None):
        super().__init__(parent)
        self.setWindowTitle('编辑记忆' if card else '存为记忆')
        self.setFont(QFont('Microsoft YaHei UI', 10))
        self.resize(590, 650)
        self.card, self.history, self.saved_card = card, list(history), None
        self.source = card.get('source_excerpt', '') if card else draft
        layout = QVBoxLayout(self)
        note = QLabel('确认事件经过后保存。请写清人物和时间，不确定就标待核实。\n保存不调用 API；以后聊到相关话题时会发送少量摘要给已配置的 API。')
        note.setWordWrap(True); layout.addWidget(note)
        if not card:
            layout.addWidget(QLabel('可多选最近聊天（Ctrl / Shift），再提取所选内容：'))
            self.messages = QListWidget()
            self.messages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.messages.setMaximumHeight(125)
            self.messages.setAccessibleName('选择要保存的聊天内容')
            for index, message in enumerate(self.history):
                role = '用户' if message['role'] == 'user' else '师滔回复（需核实）'
                item = QListWidgetItem(f'{role}：{message["content"][:180]}')
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.messages.addItem(item)
            extract = QPushButton('使用选中内容')
            extract.clicked.connect(self.use_selection)
            layout.addWidget(self.messages); layout.addWidget(extract)
        form = QFormLayout()
        self.title_input = QLineEdit(); self.title_input.setMaxLength(80)
        self.summary_input = QPlainTextEdit(); self.summary_input.setMinimumHeight(125)
        self.tags_input = QLineEdit(); self.tags_input.setPlaceholderText('用逗号分隔，以后提到这些词就能检索')
        self.date_input = QLineEdit(); self.date_input.setMaxLength(80)
        self.date_input.setPlaceholderText('可填大概时间；留空表示不知道')
        self.kind_input = QComboBox(); self.kind_input.addItems(STATUSES)
        for label, widget in [('事件标题',self.title_input),('记忆内容（最多800字）',self.summary_input),('关键词',self.tags_input),('发生时间',self.date_input),('记忆性质',self.kind_input)]:
            form.addRow(label,widget); widget.setAccessibleName(label)
        layout.addLayout(form)
        self.error_label = QLabel(); self.error_label.setWordWrap(True); layout.addWidget(self.error_label)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton('取消'); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        save = QPushButton('更新记忆' if card else '确认存入知识库'); save.clicked.connect(self.save); row.addWidget(save)
        layout.addLayout(row)
        if card:
            self.title_input.setText(card['title']); self.summary_input.setPlainText(card['summary'])
            self.tags_input.setText('，'.join(card.get('tags',[])))
            self.date_input.setText(card.get('event_date') or '')
            self.kind_input.setCurrentText(card.get('status','用户补充'))
        else:
            self.summary_input.setPlainText(draft)
            if not draft and self.history:
                index = next((i for i in range(len(self.history)-1,-1,-1) if self.history[i]['role']=='user'),None)
                if index is not None:
                    self.messages.item(index).setSelected(True); self.use_selection()

    def use_selection(self):
        messages = [self.history[item.data(Qt.ItemDataRole.UserRole)] for item in self.messages.selectedItems()]
        if not messages:
            self.error_label.setText('请先选择聊天内容。'); return
        self.source = '\n'.join(('用户：' if m['role']=='user' else '师滔回复：')+m['content'] for m in messages)
        self.summary_input.setPlainText('\n'.join(m['content'] for m in messages))
        self.kind_input.setCurrentText('待核实' if any(m['role']!='user' for m in messages) else '用户补充')
        self.error_label.setText('请整理成完整事件，尤其检查“他”“那天”等指代。')

    def save(self):
        try:
            payload = dict(title=self.title_input.text(),summary=self.summary_input.toPlainText(),
                tags=self.tags_input.text(),event_date=self.date_input.text(),status=self.kind_input.currentText())
            self.saved_card, changed = save_event(payload,card_id=self.card['id'] if self.card else None,
                expected_updated_at=self.card.get('updated_at') if self.card else None,source=self.source)
            self.duplicate = not changed
            self.accept()
        except (OSError,ValueError) as exc:
            self.error_label.setText('保存失败：'+str(exc))


class EventMemoryManager(QDialog):
    def __init__(self,parent=None, sync_controller=None):
        super().__init__(parent)
        self.setWindowTitle('管理本地记忆'); self.resize(720,450)
        self.setFont(QFont('Microsoft YaHei UI',10))
        layout=QVBoxLayout(self)
        label=QLabel('这里管理本机保存的事件记忆；聊天记录和记忆不会自动上传。')
        label.setWordWrap(True);layout.addWidget(label)
        self.list=QListWidget();self.list.setAccessibleName('新增记忆列表');layout.addWidget(self.list)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout()
        buttons = [('新增',self.add),('查看 / 编辑',self.edit),('删除',self.delete),('关闭',self.accept)]
        for title,callback in buttons:
            b=QPushButton(title);b.clicked.connect(callback);row.addWidget(b)
        layout.addLayout(row);self.list.itemDoubleClicked.connect(lambda _:self.edit());self.refresh()
    def refresh(self):
        self.list.clear()
        try:
            for card in reversed(read_events()['cards']):
                item=QListWidgetItem(f'{card["title"]}  ·  本地 · {card["status"]}')
                item.setData(Qt.ItemDataRole.UserRole,{'card':card,'shared':False});self.list.addItem(item)
            self.status.setText(f'共 {self.list.count()} 条新增记忆')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))
    def completed(self, message):
        self.refresh()
        self.status.setText(message)
    def sync(self):
        if self.sync_controller:
            self.sync_controller.sync(self.completed)
    def add(self):
        editor = EventMemoryDialog(self)
        self.refresh()
    def edit(self):
        if item:=self.list.currentItem():
            data = item.data(Qt.ItemDataRole.UserRole)
            editor = EventMemoryDialog(self,card=data['card'])
            self.refresh()
    def delete(self):
        item=self.list.currentItem()
        if not item:return
        data=item.data(Qt.ItemDataRole.UserRole); card=data['card']
        if QMessageBox.question(self,'删除记忆',f'删除“{card["title"]}”？原聊天记录会保留。',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:delete_event(card['id'],card.get('updated_at'));self.refresh()
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

