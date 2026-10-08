from streamlit.testing.v1 import AppTest
from pathlib import Path

def test_navigation_and_demo(tmp_path,monkeypatch):
    monkeypatch.setenv('ASSURANCE_DB',str(tmp_path/'ui.sqlite3'))
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30).run()
    assert not app.exception
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert len(app.metric) == 4
    for page in ['Import & reconcile','Investigations','Evidence & documents','Rules & settings']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
