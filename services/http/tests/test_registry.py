import pytest
import os
import json
from unittest import mock
from pathlib import Path
from openbb_app.core import registry

@pytest.fixture(autouse=True)
def clear_templates():
    registry.TEMPLATES.clear()
    yield
    registry.TEMPLATES.clear()

def test_add_template_success(tmp_path, monkeypatch):
    # Arrange (src-layout: parent.parent of core/registry.py = src/openbb_app)
    templates_dir = tmp_path / "src" / "openbb_app" / "templates"
    templates_dir.mkdir(parents=True)
    template_name = "test_template"
    template_content = {"foo": "bar"}
    template_file = templates_dir / f"{template_name}.json"
    template_file.write_text(json.dumps(template_content))

    fake_core = tmp_path / "src" / "openbb_app" / "core"
    fake_core.mkdir(parents=True)
    fake_file = fake_core / "fake_registry.py"
    fake_file.write_text("# dummy")
    monkeypatch.setattr(registry, "__file__", str(fake_file))

    # Act
    result = registry.add_template(template_name)

    # Assert
    assert result is True
    assert template_name in registry.TEMPLATES
    assert registry.TEMPLATES[template_name] == template_content

def test_add_template_file_not_found(monkeypatch):
    # Patch __file__ to a temp directory
    fake_dir = Path(os.getcwd())
    monkeypatch.setattr(registry, "__file__", str(fake_dir / "fake_registry.py"))

    result = registry.add_template("nonexistent_template")
    assert result is False
    assert "nonexistent_template" not in registry.TEMPLATES

def test_add_template_invalid_json(tmp_path, monkeypatch):
    templates_dir = tmp_path / "src" / "openbb_app" / "templates"
    templates_dir.mkdir(parents=True)
    template_name = "bad_template"
    template_file = templates_dir / f"{template_name}.json"
    template_file.write_text("{invalid json}")

    fake_core = tmp_path / "src" / "openbb_app" / "core"
    fake_core.mkdir(parents=True)
    fake_file = fake_core / "fake_registry.py"
    fake_file.write_text("# dummy")
    monkeypatch.setattr(registry, "__file__", str(fake_file))

    result = registry.add_template(template_name)
    assert result is False
    assert template_name not in registry.TEMPLATES
def test_add_template_other_exception(tmp_path, monkeypatch):
    templates_dir = tmp_path / "src" / "openbb_app" / "templates"
    templates_dir.mkdir(parents=True)
    template_name = "test_template"
    template_file = templates_dir / f"{template_name}.json"
    template_file.write_text('{"foo": "bar"}')

    fake_core = tmp_path / "src" / "openbb_app" / "core"
    fake_core.mkdir(parents=True)
    fake_file = fake_core / "fake_registry.py"
    fake_file.write_text("# dummy")
    monkeypatch.setattr(registry, "__file__", str(fake_file))

    # Simulate exception when opening the file
    with mock.patch("builtins.open", side_effect=OSError("fail")):
        result = registry.add_template(template_name)
        assert result is False
        assert template_name not in registry.TEMPLATES