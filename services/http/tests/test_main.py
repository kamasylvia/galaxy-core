from openbb_app.main import get_apps

def test_get_apps(tmp_path):
    # Call the function and verify response
    data = get_apps()
    assert isinstance(data, list)
    assert len(data) > 0
