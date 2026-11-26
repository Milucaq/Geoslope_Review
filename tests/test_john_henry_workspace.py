"""Exercise the real terrain/simulation pipeline with a 5x5 local test asset.

Only the browser component transport is replaced: CI does not execute WebGL.
"""

import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gsreview.analytics.john_henry import build_mesh
from gsreview.analytics.synthetic import SyntheticConfig, generate_synthetic_monitoring_data
from gsreview.domain.rules import AccessDenied
from gsreview.presentation import john_henry_workspace as workspace


def terrain_app(c):
    from gsreview.presentation.john_henry_workspace import render_john_henry_workspace

    render_john_henry_workspace(c, "synthetic-test-session")


@pytest.fixture
def small_terrain(tmp_path, monkeypatch):
    root = tmp_path / "assets/terrain/john_henry"
    root.mkdir(parents=True)
    # A connected 45-degree plane: 25 vertices meet the production minimum of 20.
    z = np.tile(np.arange(5, dtype=float), (5, 1))
    mesh = build_mesh(z, np.ones_like(z, dtype=bool), (1, 0, 100, 0, -1, 205), stride=1)
    np.savez(root / "mesh.npz", **mesh)
    (root / "texture.jpg").write_bytes(b"controlled texture transport fixture")
    meta = {
        "vertices": 25, "triangles": 32, "mesh_spacing_m": [1, 1],
        "asset_hashes": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("mesh.npz", "texture.jpg")
        },
        "provenance": "Synthetic plane for tests; not a John Henry measurement",
    }
    (root / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    bundle = tmp_path / "assets/three_component/bundle"
    bundle.mkdir(parents=True)
    (bundle / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(workspace, "ROOT", tmp_path)
    workspace._load.clear()
    workspace._sectors.clear()
    yield root, mesh, meta
    workspace._load.clear()
    workspace._sectors.clear()


@pytest.fixture
def simulation_ui(monkeypatch):
    def generate(token, **kwargs):
        assert token == "synthetic-test-session"
        return generate_synthetic_monitoring_data(SyntheticConfig(**kwargs))

    c = SimpleNamespace(
        auth=SimpleNamespace(authorize=Mock(return_value={"id": "test"})),
        reader=SimpleNamespace(assert_current=Mock()),
        synthetic=SimpleNamespace(generate=Mock(side_effect=generate)),
    )
    calls = []
    event = {"prism_id": "SYN-W01"}

    def component(**kwargs):
        calls.append(kwargs)
        return event.copy()

    declaration = Mock(return_value=component)
    monkeypatch.setattr(workspace.components, "declare_component", declaration)
    return c, calls, event, declaration


def test_asset_loader_checks_hashes_and_serializes_unexaggerated_geometry(small_terrain):
    root, mesh, meta = small_terrain
    actual, payload, positions, origin, triangles, slopes = workspace._load(str(root), (1,))
    assert actual == meta
    assert payload["vertices"] == 25 and payload["triangles"] == 32
    np.testing.assert_array_equal(positions, mesh["positions"])
    np.testing.assert_array_equal(origin, mesh["origin"])
    np.testing.assert_array_equal(triangles, mesh["indices"])
    np.testing.assert_allclose(slopes, 45)
    decoded = np.frombuffer(base64.b64decode(payload["positions"]), dtype="<f4").reshape(-1, 3)
    np.testing.assert_array_equal(decoded, positions)
    assert np.all(workspace._sectors(slopes, triangles, 35) == 1)
    assert not workspace._sectors(slopes, triangles, 50).any()


def test_generate_select_and_amplify_do_not_change_measurements(small_terrain, simulation_ui):
    _, mesh, _ = small_terrain
    c, calls, event, declaration = simulation_ui
    at = AppTest.from_function(terrain_app, args=(c,)).run()
    assert not at.exception and not at.error
    assert calls[-1]["markers"] == []
    at.selectbox(key="jh_slope_sector").select(1).run()
    next(x for x in at.number_input if x.label == "Prismas simulados").set_value(4)
    next(x for x in at.number_input if x.label == "Días simulados").set_value(3)
    next(x for x in at.button if x.label == "Generar escenario sobre terreno real").click().run()
    assert not at.exception and not at.error
    c.synthetic.generate.assert_called_once()
    records = at.session_state["jh_records"].copy(deep=True)
    assert records.prism_id.nunique() == 4
    assert set(records.sector_topografico) == {1}
    assert records.pendiente_base_deg.between(44.99, 45.01).all()
    assert len(calls[-1]["markers"]) == 4
    assert len(at.get("download_button")) == 1
    assert any(x.label == "Desplazamiento vectorial simulado desde el inicio (mm)" for x in at.metric)
    before = calls[-1]["markers"]
    at.selectbox(key="jh_vector_scale_v2").select(100).run()
    after = calls[-1]["markers"]
    for a, b in zip(before, after):
        np.testing.assert_array_equal(a["position"], b["position"])
        assert a["coordinate_displacement_mm"] == b["coordinate_displacement_mm"]
        np.testing.assert_allclose(
            np.array(b["vector_endpoint"]) - b["base"],
            100 * (np.array(a["position"]) - a["base"]), atol=1e-7,
        )
    at.selectbox(key="jh_vertical_exaggeration").select(1).run()
    at.radio(key="jh_slope_layer_v2").set_value("Ortofotografía").run()
    assert calls[-1]["vertical"] == 1 and not calls[-1]["slope_layer"]
    pd.testing.assert_frame_equal(at.session_state["jh_records"], records)
    at.select_slider(key="jh_cutoff").set_value(records.timestamp.min().to_pydatetime()).run()
    assert all(x["coordinate_displacement_mm"] == 0 for x in calls[-1]["markers"])
    assert all(x["movement"] is None for x in calls[-1]["markers"])
    # A forged browser ID is never used as a historical or simulated selection.
    event["prism_id"] = "<script>historical-id</script>"
    at.run()
    assert not any(x.label == "Desplazamiento vectorial simulado desde el inicio (mm)" for x in at.metric)
    c.auth.authorize.assert_called_with("synthetic-test-session", "read")
    c.reader.assert_current.assert_called()
    assert declaration.call_args.kwargs["path"].endswith("bundle")
    np.testing.assert_array_equal(mesh["positions"].shape, (25, 3))


def test_changed_threshold_hides_stale_simulation_and_rejects_insufficient_vertices(
    small_terrain, simulation_ui,
):
    c, calls, _, _ = simulation_ui
    at = AppTest.from_function(terrain_app, args=(c,)).run()
    next(x for x in at.button if x.label == "Generar escenario sobre terreno real").click().run()
    assert calls[-1]["markers"]
    at.selectbox(key="jh_slope_threshold").select(50).run()
    assert not at.exception and not at.error
    assert calls[-1]["markers"] == []
    assert not at.get("download_button")
    next(x for x in at.button if x.label == "Generar escenario sobre terreno real").click().run()
    assert any("suficientes vértices" in w.value for w in at.warning)
    assert c.synthetic.generate.call_count == 1


@pytest.mark.parametrize("asset", ["mesh.npz", "texture.jpg"])
def test_tampered_asset_fails_closed(small_terrain, simulation_ui, asset):
    root, _, _ = small_terrain
    (root / asset).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="incompatibles"):
        workspace._load(str(root), (2,))
    c, calls, _, _ = simulation_ui
    at = AppTest.from_function(terrain_app, args=(c,)).run()
    assert not at.exception
    assert any("verificar los activos" in e.value for e in at.error)
    assert not calls
    c.synthetic.generate.assert_not_called()


def test_missing_bundle_and_authorization_stop_before_simulation(small_terrain, simulation_ui):
    c, calls, _, _ = simulation_ui
    (workspace.ROOT / "assets/three_component/bundle/index.html").unlink()
    at = AppTest.from_function(terrain_app, args=(c,)).run()
    assert any("Faltan activos" in w.value for w in at.warning)
    assert not calls
    c.auth.authorize.side_effect = AccessDenied("test denied")
    with pytest.raises(AccessDenied, match="test denied"):
        workspace.render_john_henry_workspace(c, "synthetic-test-session")
    c.synthetic.generate.assert_not_called()


def test_navigation_retains_sector_instrumentation_prism_and_cutoff(
    app, monkeypatch, small_terrain, simulation_ui,
):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    _, calls, _, _ = simulation_ui
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=30)
    at.session_state["token"] = app.test_admin
    at.run()
    at.button(key="flow_new_jh").click().run()
    at.button(key="flow_terrain_prepare").click().run()
    at.selectbox(key="jh_slope_sector").select(1).run()
    next(x for x in at.number_input if x.label == "Prismas simulados").set_value(4)
    next(x for x in at.number_input if x.label == "Días simulados").set_value(45)
    next(x for x in at.button if x.label == "Generar escenario sobre terreno real").click().run()
    assert not at.exception and not at.error
    records = at.session_state["jh_records"].copy(deep=True)
    at.button(key="detail_analyze_john_henry").click().run()
    assert any(t.value == "Análisis del escenario" for t in at.title)
    cutoff = pd.Timestamp(records.timestamp.sort_values().iloc[len(records)//2], tz="UTC")
    at.select_slider(key="science_analysis_cutoff_john_henry").set_value(cutoff).run()
    at.button(key="rail_Vista espacial").click().run()
    assert not at.exception and not at.error
    assert at.selectbox(key="jh_slope_sector").value == 1
    assert at.session_state["scenario_jh_valid"]
    assert calls[-1]["markers"]
    assert all(pd.to_datetime(m["timestamp"], utc=True) <= cutoff for m in calls[-1]["markers"])
    pd.testing.assert_frame_equal(at.session_state["jh_records"], records)
