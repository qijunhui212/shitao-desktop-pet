from pet.drop_physics import Platform, advance, landing
from pet.drop_physics import recovery_pose, RECOVERY_SECONDS


def test_complete_getup_and_full_one_and_half_seconds_prone():
    assert recovery_pose(.21)[1]=='impact'
    assert recovery_pose(.22)[1]=='prone'
    assert recovery_pose(1.719)[1]=='prone'
    assert recovery_pose(1.72)[1]=='head'
    assert [recovery_pose(t)[0] for t in (2.1,2.4,2.8,3.3)]==[4,5,6,7]
    assert RECOVERY_SECONDS==3.5


def test_crossing_platform_catches_even_at_high_speed():
    assert landing(100, 500, 150, Platform(100, 300, 100), 800) == ('safe', 300)


def test_direct_placement_and_edges():
    p = Platform(100, 300, 100)
    assert landing(307, 308, 100, p, 800) == ('safe', 300)
    assert landing(311, 320, 150, p, 800)[0] is None
    assert landing(100, 400, 99, p, 800)[0] is None


def test_missed_platform_lands_on_floor():
    assert landing(700, 900, 350, Platform(100, 300, 100), 800) == ('floor', 800)


def test_gravity_accelerates_and_caps_elapsed_time():
    y, v = advance(0, 0, .016)
    next_y, next_v = advance(y, v, .016)
    assert 0 < y < next_y and 0 < v < next_v
    assert advance(0, 0, 10) == advance(0, 0, .05)
