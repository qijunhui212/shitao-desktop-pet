from config.pet_mode import is_survival_mode_value, pet_mode_env_value


def test_survival_values():
    assert is_survival_mode_value("survival")
    assert is_survival_mode_value("生存")
    assert not is_survival_mode_value("normal")
    assert not is_survival_mode_value("普通")


def test_pet_mode_env_value():
    assert pet_mode_env_value(survival=True) == "survival"
    assert pet_mode_env_value(survival=False) == "normal"
