"""Test component contracts using real payloads and a fake browser transport."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from gsreview.domain.rules import ValidationError
from gsreview.presentation import three_component as component
from streamlit.testing.v1 import AppTest


@pytest.fixture
def transport(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(component, "_BUNDLE", bundle)
    browser = Mock(return_value={"prism_id": "B", "nonce": "test"})
    declare = Mock(return_value=browser)
    monkeypatch.setattr(component.components, "declare_component", declare)
    return bundle, declare, browser


def grid():
    return {
        "easting": np.array([[100, 110], [100, 110]]),
        "northing": np.array([[210, 210], [200, 200]]),
        "elevation": np.array([[10, 20], [30, 40]]),
    }


def prisms():
    return pd.DataFrame({
        "prism_id": ["A", "B", "C", "D"],
        "easting": [100., 110., 100., 110.], "northing": [200., 200., 210., 210.],
        "rl": [10., 20., 30., 40.], "causal_state": ["sin_marca"] * 4,
        "timestamp": ["2026-01-01"] * 4,
    })


def test_terrain_transport_preserves_units_and_revision(transport):
    bundle, declare, browser = transport
    arrays = grid()
    assert component.render_three_terrain(arrays, 3, "revision-test") is True
    declare.assert_called_once_with("geoslope_three_terrain", path=str(bundle))
    args = browser.call_args.kwargs
    assert args["revision"] == "revision-test" and args["default"] is None
    payload = args["payload"]
    p = np.array(payload["positions"]).reshape(2, 2, 3)
    np.testing.assert_allclose(p[..., 1] / 3 + payload["origin"][2], arrays["elevation"])


@pytest.mark.parametrize("surface", [True, False])
def test_instrumental_transport_retains_full_mesh_and_filters_only_markers(transport, surface):
    _, declare, browser = transport
    source = prisms()
    before = source.copy(deep=True)
    result = component.render_three_instrumental(
        source, source.iloc[[1]], "B", True, True, surface, "cutoff-test",
    )
    assert result == {"prism_id": "B", "nonce": "test"}
    assert declare.call_args.args == ("geoslope_three_instrumental",)
    args = browser.call_args.kwargs
    assert args["mode"] == "instrumental" and args["revision"] == "cutoff-test"
    payload = args["payload"]
    assert payload["reference_count"] == 4
    assert [p["id"] for p in payload["markers"]] == ["B"]
    assert payload["selected"] == "B" and payload["focus"] and payload["labels"]
    assert bool(payload["indices"]) is surface
    pd.testing.assert_frame_equal(source, before)


def test_missing_bundle_warns_without_declaring_component(transport, monkeypatch):
    bundle, declare, _ = transport
    (bundle / "index.html").unlink()
    warning = Mock()
    monkeypatch.setattr(component.st, "warning", warning)
    assert component.render_three_terrain(grid(), 1, "r") is False
    assert component.render_three_instrumental(prisms(), prisms(), None, False, False, True, "r") is None
    assert warning.call_count == 2
    declare.assert_not_called()


def test_invalid_coordinates_never_reach_browser(transport):
    _, _, browser = transport
    source = prisms()
    source.loc[0, "easting"] = np.inf
    with pytest.raises(ValidationError, match="Coordenadas"):
        component.render_three_instrumental(source, source, None, False, False, True, "r")
    browser.assert_not_called()


def test_authenticated_three_workspace_filters_events_and_preserves_reference_mesh(
    app, transport, monkeypatch,
):
    _, _, browser = transport
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=25)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()
    at.radio(key="sx_prism_engine").set_value("Three.js").run()
    assert not at.exception and not at.error
    payload = browser.call_args.kwargs["payload"]
    reference_count = payload["reference_count"]
    chosen = payload["markers"][0]["id"]
    at.multiselect(key="sx_prisms").set_value([chosen]).run()
    payload = browser.call_args.kwargs["payload"]
    assert payload["reference_count"] == reference_count
    assert [m["id"] for m in payload["markers"]] == [chosen]
    # An ID outside the visible set cannot select a historical prism.
    assert at.session_state["sx_selected"] is None
    browser.return_value = {"prism_id": chosen, "nonce": "valid-event"}
    at.run()
    assert not at.exception and not at.error
    assert at.session_state["sx_selected"] == chosen
    at.toggle(key="sx_instrumental_tin").set_value(False).run()
    assert not browser.call_args.kwargs["payload"]["indices"]
    at.toggle(key="sx_labels").set_value(True).run()
    assert browser.call_args.kwargs["payload"]["labels"] is True
    assert app.reader.verify() == 17
