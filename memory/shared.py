"""Opt-in collaborative knowledge-base sync.

The server stores only reviewed event cards. A shared token grants the holder
read and write access; each write contains one operation so clients do not
overwrite cards created by somebody else.
"""
import hashlib
import json
import re
import uuid
from urllib.parse import urlsplit

import httpx

from config.paths import app_root
from memory.events import _atomic_write

MAX_BYTES = 512 * 1024


def files():
    root = app_root() / "data/persona"
    return root / "sync-config.json", root / "shared-memory.json"


def normalize_url(value):
    url = str(value).strip().rstrip("/")
    p = urlsplit(url)
    if ((p.scheme != "https" and not (p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost", "::1")))
            or not p.hostname or p.username or p.password or p.query or p.fragment):
        raise ValueError("同步地址需要 HTTPS；本机测试可用 localhost HTTP。")
    return url


def settings():
    path, _ = files()
    if not path.exists():
        return {"enabled": False, "url": "", "token": "", "client_id": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError('共享设置格式错误，请重新填写。')
    data.setdefault("client_id", "")
    return data


def configure(enabled, url, token):
    url = normalize_url(url) if url else ""
    token = str(token).strip()
    if enabled and (not url or len(token) < 16 or len(token) > 256):
        raise ValueError("请填写同步地址和有效的共享密钥。")
    try:old = settings()
    except (OSError,ValueError):old = {}
    client_id = old.get("client_id") or "client-" + uuid.uuid4().hex
    path, _ = files()
    _atomic_write(path, {"enabled": bool(enabled), "url": url, "token": token, "client_id": client_id})


def source_key(config):
    return hashlib.sha256((config.get("url", "") + "\n" + config.get("token", "")).encode()).hexdigest()


def validate_snapshot(value):
    if (not isinstance(value, dict) or value.get("schema_version") != 1
            or not isinstance(value.get("profile"), str) or len(value["profile"]) > 4000
            or not isinstance(value.get("cards"), list) or len(value["cards"]) > 300):
        raise ValueError("共享知识库格式不正确。")
    cards = []
    ids = set()
    for card in value["cards"]:
        if (not isinstance(card, dict) or not isinstance(card.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", card["id"])
                or card["id"] in ids):
            raise ValueError("共享记忆标识不正确或重复。")
        ids.add(card["id"])
        out = {"id": card["id"]}
        if card.get("updated_at") is not None:
            if not isinstance(card["updated_at"], str) or len(card["updated_at"]) > 100:
                raise ValueError("共享记忆版本标记不正确。")
            out["updated_at"] = card["updated_at"]
        for key, maximum, default in (("title", 80, ""), ("summary", 800, ""),
                                      ("status", 80, "用户补充"), ("date_note", 200, "")):
            value_text = card.get(key, default)
            if (not isinstance(value_text, str) or len(value_text) > maximum
                    or (key in ("title", "summary") and not value_text.strip())):
                raise ValueError("共享记忆文字超出限制。")
            out[key] = value_text
        event_date = card.get("event_date")
        if event_date is not None and (not isinstance(event_date, str) or len(event_date) > 80):
            raise ValueError("事件日期不正确。")
        out["event_date"] = event_date
        for key, max_count, max_length in (("tags", 12, 30), ("aliases", 12, 30), ("uncertainties", 12, 200)):
            values = card.get(key, [])
            if (not isinstance(values, list) or len(values) > max_count
                    or any(not isinstance(item, str) or len(item) > max_length for item in values)):
                raise ValueError("共享记忆关键词格式不正确。")
            out[key] = values
        cards.append(out)
    clean = {"schema_version": 1, "profile": value["profile"], "cards": cards}
    if len(json.dumps(clean, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("共享知识库超过512KB。")
    return clean


def clean_card(card):
    return validate_snapshot({"schema_version": 1, "profile": "", "cards": [card]})["cards"][0]


def cached_memory():
    try:
        config = settings()
        _, path = files()
        if not config.get("enabled") or not path.exists():
            return None
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("source_key") != source_key(config):
            return None
        return validate_snapshot(saved["memory"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _get(client, config, version=None):
    headers = {"Authorization": "Bearer " + config["token"]}
    if version is not None:
        headers["If-None-Match"] = '"' + str(version) + '"'
    with client.stream("GET", config["url"] + "/v1/knowledge", headers=headers) as response:
        if response.status_code == 304:
            return None
        if response.status_code in (401, 403):
            raise ValueError("共享密钥无效或权限已被撤销。")
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > MAX_BYTES + 1024:
                raise ValueError("同步响应超过限制。")
        body = json.loads(raw)
    if not isinstance(body.get("version"), int) or body["version"] < 0:
        raise ValueError("共享版本无效。")
    return {"version": body["version"], "memory": validate_snapshot(body["memory"])}


def sync_once(client=None):
    config = settings()
    if not config.get("enabled"):
        return "未启用共享同步"
    _, path = files()
    version = None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("source_key") == source_key(config):
            validate_snapshot(saved["memory"])
            version = saved["version"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(20, connect=8), follow_redirects=False, trust_env=False)
    try:
        result = _get(client, config, version)
        if source_key(settings()) != source_key(config) or not settings().get("enabled"):
            return "设置已变化，已忽略旧同步结果"
        if result is None:
            return f"共享知识库已是最新版本 v{version}"
        _atomic_write(path, {"source_key": source_key(config), **result})
        return f"已同步共享知识库 v{result['version']}，共 {len(result['memory']['cards'])} 条"
    finally:
        if own:
            client.close()


def _post_operation(operation, *, client=None):
    config = settings()
    if not config.get("enabled"):
        raise ValueError("请先配置并启用共享同步。")
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(20, connect=8), follow_redirects=False, trust_env=False)
    try:
        response = client.post(config["url"] + "/v1/knowledge/events",
                               headers={"Authorization": "Bearer " + config["token"]},
                               json={**operation, "client_id": config.get("client_id", "")})
        if response.status_code in (401, 403):
            raise ValueError("共享密钥无效或没有写入权限。")
        if response.status_code == 409:
            raise ValueError("共享库刚被更新，请先同步后再提交。")
        response.raise_for_status()
        body = response.json()
        if not isinstance(body.get("version"), int):
            raise ValueError("服务器返回的共享版本无效。")
        return body["version"]
    finally:
        if own:
            client.close()


def upsert_card(card, *, expected_updated_at=None, client=None):
    operation = {"op": "upsert", "card": clean_card(card)}
    if expected_updated_at is not None:
        operation["base_updated_at"] = expected_updated_at
    return _post_operation(operation, client=client)


def delete_card(card_id, *, expected_updated_at=None, client=None):
    if not isinstance(card_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", card_id):
        raise ValueError("共享记忆标识不正确。")
    if not isinstance(expected_updated_at, str) or not expected_updated_at:
        raise ValueError("请刷新共享列表后再删除，以免误删别人的新修改。")
    return _post_operation({"op": "delete", "id": card_id, "base_updated_at": expected_updated_at}, client=client)
