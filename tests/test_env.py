import os

import pytest

from ci_tool.env import load_env


def load(tmp_path, monkeypatch, content: str, present: dict | None = None):
    for key in ("GOOD", "EMPTY", "PASTED", "SHAPED"):
        monkeypatch.delenv(key, raising=False)
    for k, v in (present or {}).items():
        monkeypatch.setenv(k, v)
    env = tmp_path / ".env"
    env.write_text(content, encoding="utf-8")
    load_env(env)


def test_loads_plain_and_quoted_values(tmp_path, monkeypatch, capsys):
    load(tmp_path, monkeypatch, 'GOOD="value1"\nPASTED=value2\n')
    assert os.environ["GOOD"] == "value1"
    assert os.environ["PASTED"] == "value2"
    assert capsys.readouterr().err == ""


def test_never_overrides_real_environment(tmp_path, monkeypatch):
    load(tmp_path, monkeypatch, "GOOD=from_file\n", present={"GOOD": "from_env"})
    assert os.environ["GOOD"] == "from_env"


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("#PASTED=actualkeyvalue", "PASTED"),  # the 2026-08 NewsData incident shape
        ("EMPTY=", "EMPTY"),
        ("SHAPED=# paste your key here", "SHAPED"),
    ],
)
def test_misconfigured_lines_warn_and_do_not_load(tmp_path, monkeypatch, capsys, line, key):
    load(tmp_path, monkeypatch, line + "\n")
    assert key not in os.environ
    assert key in capsys.readouterr().err


@pytest.mark.parametrize(
    "line",
    [
        "# a plain comment, even one with = in it",
        "#PASTED=",  # .env.example template shape: commented key, no value
        "",
        "not an assignment at all",
    ],
)
def test_benign_lines_stay_silent(tmp_path, monkeypatch, capsys, line):
    load(tmp_path, monkeypatch, line + "\n")
    assert capsys.readouterr().err == ""
