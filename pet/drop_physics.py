"""Local pickup/drop geometry. Coordinates use the pet's visible feet."""
from dataclasses import dataclass

RECOVERY_SECONDS = 3.5


def recovery_pose(elapsed):
    # Impact, prone for a full 1.5s, head lift, push-up, knees, crouch, stand.
    for end, frame, stage in [(0.22,1,'impact'), (1.72,2,'prone'), (2.0,3,'head'),
                              (2.35,4,'push'), (2.7,5,'knees'), (3.15,6,'crouch')]:
        if elapsed < end:
            return frame, stage
    return 7, 'standing'


@dataclass(frozen=True)
class Platform:
    left: float
    top: float
    width: float


def landing(previous_feet, next_feet, center_x, platform, floor):
    # Segment crossing prevents tunnelling on slow frames. The center of the
    # feet must be over the plank, rather than a transparent sprite corner.
    if (platform is not None and platform.left <= center_x <= platform.left + platform.width
            and previous_feet <= platform.top + 10 and next_feet >= platform.top - 3
            and platform.top <= floor):
        return 'safe', platform.top
    if next_feet >= floor:
        return 'floor', floor
    return None, next_feet


def advance(y, velocity, dt):
    dt = min(0.05, max(0, dt))
    return y + velocity * dt + 0.5 * 2200 * dt * dt, min(1800, velocity + 2200 * dt)
