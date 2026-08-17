from streamlit.testing.v1 import AppTest


def test_daily_digest_renders_without_exception():
    at = AppTest.from_file("../ui/app.py").run(timeout=15)
    assert not at.exception
