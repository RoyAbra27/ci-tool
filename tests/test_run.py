from datetime import UTC, datetime

from ci_tool.models import load_config
from ci_tool.run import _filter_now

WALL = datetime(2027, 1, 1, tzinfo=UTC)
ANCHOR = datetime(2026, 8, 14, 10, 20, 35, tzinfo=UTC)


def test_replay_uses_anchor_regardless_of_wall_clock():
    assert _filter_now(live=False, wall=WALL, anchor=ANCHOR) == ANCHOR


def test_live_always_uses_wall_clock():
    assert _filter_now(live=True, wall=WALL, anchor=ANCHOR) == WALL


def test_replay_without_anchor_falls_back_to_wall_clock():
    assert _filter_now(live=False, wall=WALL, anchor=None) == WALL


def test_config_anchor_is_pinned_and_timezone_aware():
    anchor = load_config("config.toml").settings.replay_anchor
    assert anchor == ANCHOR
    assert anchor.tzinfo is not None
