import os
from datetime import datetime, timedelta

import pytest

from config.pet_mode import is_survival_memory_mode_value
from memory.store import MemoryStore
from pet.vitality import HP_MAX, PetVitality, PROFILE_LAST_TS


def test_survival_memory_env_flag():
    assert is_survival_memory_mode_value("1")
    assert not is_survival_memory_mode_value("0")


def test_offline_decay_on_load(tmp_path, monkeypatch):
    db = tmp_path / "pet.db"
    monkeypatch.setattr("config.settings.DB_PATH", db)
    monkeypatch.setenv("SURVIVAL_MEMORY_MODE", "1")

    import importlib
    import config.pet_mode as pet_mode

    importlib.reload(pet_mode)

    mem = MemoryStore()
    mem.set_profile("vitality_hp", "6.0")
    mem.set_profile("vitality_starved", "0")
    mem.set_profile("vitality_revive_feeds", "0")
    last = datetime.now() - timedelta(hours=3)
    mem.set_profile(PROFILE_LAST_TS, last.isoformat(timespec="seconds"))

    v = PetVitality(mem, enabled=True)
    assert v.hp == pytest.approx(3.0, abs=0.05)
    assert not v.is_starved
    mem.close()


def test_no_offline_decay_when_disabled(tmp_path, monkeypatch):
    db = tmp_path / "pet.db"
    monkeypatch.setattr("config.settings.DB_PATH", db)
    monkeypatch.setenv("SURVIVAL_MEMORY_MODE", "0")

    import importlib
    import config.pet_mode as pet_mode

    importlib.reload(pet_mode)

    mem = MemoryStore()
    mem.set_profile("vitality_hp", "6.0")
    mem.set_profile("vitality_starved", "0")
    last = datetime.now() - timedelta(hours=10)
    mem.set_profile(PROFILE_LAST_TS, last.isoformat(timespec="seconds"))

    v = PetVitality(mem, enabled=True)
    assert v.hp == pytest.approx(6.0, abs=0.05)
    mem.close()
