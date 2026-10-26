from pathlib import Path

from config.pack_discovery import (
    compute_pack_signature,
    find_pack_name_by_signature,
    list_pack_folder_names,
    reconcile_character_pack,
)


def test_compute_pack_signature_from_prompt(tmp_path, monkeypatch):
    lib = tmp_path / "形象"
    pack = lib / "测试包"
    pack.mkdir(parents=True)
    (pack / "a.png").write_bytes(b"x")
    (pack / "人设.txt").write_text("你是测试角色\n", encoding="utf-8")
    monkeypatch.setenv("CHARACTER_ROOT", "形象")
    monkeypatch.setattr(
        "config.pack_discovery.character_library_root", lambda: lib
    )
    sig1 = compute_pack_signature(pack)
    assert sig1.startswith("prompt:")

    import shutil

    shutil.rmtree(pack)
    (lib / "新文件夹名").mkdir()
    (lib / "新文件夹名" / "b.png").write_bytes(b"y")
    (lib / "新文件夹名" / "人设.txt").write_text(
        "你是测试角色\n", encoding="utf-8"
    )
    assert find_pack_name_by_signature(sig1) == "新文件夹名"


def test_reconcile_after_rename(tmp_path, monkeypatch):
    lib = tmp_path / "形象"
    old = lib / "旧名"
    old.mkdir(parents=True)
    (old / "1.png").write_bytes(b"1")
    (old / "人设.txt").write_text("同一人设\n", encoding="utf-8")
    sig = compute_pack_signature(old)

    new = lib / "透明底小女孩示例"
    old.rename(new)

    env = tmp_path / ".env"
    env.write_text(
        f"CHARACTER_PACK=旧名\nCHARACTER_PACK_SIG={sig}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("config.env_update.ENV_PATH", env)
    monkeypatch.setattr(
        "config.pack_discovery.character_library_root", lambda: lib
    )
    monkeypatch.chdir(tmp_path)

    import os

    os.environ["CHARACTER_PACK"] = "旧名"
    os.environ["CHARACTER_PACK_SIG"] = sig

    result = reconcile_character_pack(write_env=True)
    assert result is not None
    assert result.pack_name == "透明底小女孩示例"
    assert result.reason == "renamed"
    assert "透明底小女孩示例" in env.read_text(encoding="utf-8")
