"""Render every view (and an account detail with all tabs) with Streamlit's AppTest."""
import pathlib
import pytest
from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parents[1] / "src" / "gtm_os" / "app.py")


def run(view, account_id=None):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["view"] = view
    if account_id:
        at.session_state["account_id"] = account_id
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


@pytest.mark.parametrize("view", ["Overview", "Accounts", "Models & Projects", "Research"])
def test_views_render(view):
    at = run(view)
    assert at.title or at.markdown


def test_account_detail_renders():
    at = run("Accounts", "ACC-019")
    text = " ".join(m.value for m in at.markdown)
    assert "Alibaba Cloud / Bailian" in text


def test_landscape_account_detail_renders():
    at = run("Accounts", "LF-0001")
