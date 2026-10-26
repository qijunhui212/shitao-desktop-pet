from __future__ import annotations
import json
import os
from config.paths import app_root
from pathlib import Path
import subprocess
from threading import Event
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4

from .db_reader import GroupDatabaseReader, GROUP_ID

RUNTIME_DIR = Path(os.getenv('WECHAT_BRIDGE_RUNTIME', '').strip() or app_root()/'local-wechat-bridge')
EXPECTED_HASH = 'e0428a7b691853de496532523c2c09aa095f90941c37c9f4cfb3f137f3c66556'


class NativeGroupTransport:
    """Local DB receive + authenticated native send, with no UI dependency."""
    def __init__(self, settings, *, runtime_dir=RUNTIME_DIR, reader=None, client=None):
        self.settings = settings.validated()
        self.directory = Path(runtime_dir)
        self.reader = reader or GroupDatabaseReader(self.settings, self.directory/'private')
        self._client = client or build_opener(ProxyHandler({}))
        self._cancel = Event()
        self._session = uuid4().hex
        self._active = False
        self._next_poll = 0
        self._last_heartbeat = 0

    def cancel(self):
        self._cancel.set()

    @property
    def mention_label(self):
        return '@' + self.reader.members.get(self.reader.self_id, '当前微信账号')

    @property
    def memory_scope(self):
        return self.reader.self_id, GROUP_ID

    def _request(self, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = Request('http://127.0.0.1:30216'+path, data=data, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer '+self._token})
        try:
            with self._client.open(req, timeout=4) as response:
                return json.loads(response.read(32768))
        except HTTPError as exc:
            value = json.loads(exc.read(32768))
            error = value.get('error', str(exc.code))
            labels = {'already_listening': '另一个桌宠已经在监听，请先停止那边的监听。',
                'session_expired': '后台会话已过期，请重新开始监听。',
                'rate_limit': '发送过于频繁，本条未重试。',
                'already_submitted': '这条消息已经提交过，不会重复发送。'}
            raise RuntimeError(labels.get(error, '后台接口拒绝请求：'+error)) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError('微信后台连接中断；若刚提交消息，结果未确认，不会自动重发。') from exc

    def start(self):
        try:
            config = json.loads((self.directory/'bridge.private.json').read_text(encoding='utf-8'))
            self._token = config['token']
            if config['group'] != GROUP_ID or config['port'] != 30216 or len(self._token) < 32:
                raise ValueError('config')
        except (OSError, KeyError, ValueError) as exc:
            raise RuntimeError('本机后台接入组件尚未安装完整。') from exc
        self.reader.start()
        if self._cancel.is_set():
            return
        try:
            status = self._request('/status')
        except RuntimeError:
            loader = self.directory/'BridgeLoader.exe'
            dll = self.directory/'ShitaoWechatBridge.dll'
            result = subprocess.run([str(loader), str(self.reader.pid), str(dll)],
                capture_output=True, timeout=35, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError(f'微信后台组件加载失败（{result.returncode}），请查看本机接入日志或重新打开微信。')
            status = None
            for _ in range(20):
                if self._cancel.wait(.25):
                    return
                try:
                    status = self._request('/status')
                    break
                except RuntimeError:
                    continue
            if status is None:
                raise RuntimeError('后台自检未通过或端口不可用，未开启发送。')
        if (status.get('pid') != self.reader.pid or status.get('group') != GROUP_ID
                or status.get('sha256') != EXPECTED_HASH or not status.get('runtime_ready')):
            raise RuntimeError('微信版本、账号或后台自检不匹配，未开启发送。')
        if self._cancel.is_set():
            return
        self._request('/session', {'action': 'start', 'session': self._session})
        self._active = True
        self._last_heartbeat = time.monotonic()

    def _heartbeat(self):
        if time.monotonic() - self._last_heartbeat >= 3:
            self._request('/session', {'action': 'heartbeat', 'session': self._session})
            self._last_heartbeat = time.monotonic()

    def poll(self):
        if not self._active or self._cancel.is_set():
            return []
        self._heartbeat()
        if time.monotonic() < self._next_poll:
            return []
        self._next_poll = time.monotonic() + 2
        return self.reader.poll()

    def send(self, text):
        if not self._active or self._cancel.is_set():
            return None
        if not (self.settings.auto_reply_enabled or self.settings.idle_announcement_enabled):
            return None
        text = text.strip().encode('utf-8')[:3000].decode('utf-8', 'ignore')
        if not text or '\0' in text:
            raise RuntimeError('回复内容无效，未发送。')
        self.reader.check_identity(force=True)
        baseline = self.reader.send_baseline()
        self._heartbeat()
        if self._cancel.is_set():
            return None
        # One request only. HTTP timeout or uncertain receipt must never retry.
        result = self._request('/send', {'session': self._session, 'request_id': uuid4().hex,
            'group': GROUP_ID, 'text': text})
        if result.get('state') != 'submitted_unconfirmed':
            raise RuntimeError('后台未确认消息提交，已停止；本条不会自动重发。')
        for _ in range(8):
            if self.reader.delivered(baseline, text):
                return '已确认服务器接收回复 · 后台监听中'
            if self._cancel.wait(1):
                return None
            self._heartbeat()
        raise RuntimeError('消息已提交，但尚未确认服务器回执。已停止监听，本条不会自动重发。')

    def stop(self):
        self._cancel.set()
        if self._active:
            self._active = False
            self._request('/session', {'action': 'stop', 'session': self._session})
