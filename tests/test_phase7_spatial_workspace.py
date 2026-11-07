import numpy as np
from streamlit.testing.v1 import AppTest
from gsreview.presentation.charts import spatial
from gsreview.presentation.spatial_workspace import _visible_state_summary


def test_spatial_chart_uses_only_original_coordinates_and_highlights_selection(app):
    points = app.reader.spatial("2014-02-20 23:59:59")
    selected = points.prism_id.iloc[0]
    original = {(float(r.easting), float(r.northing), float(r.rl)) for r in points.itertuples()}
    for focus in (False, True):
        fig = spatial(points, "3D", selected=selected, focus=focus)
        assert all(trace.type == "scatter3d" for trace in fig.data)
        assert {
            (float(x), float(y), float(z)) for t in fig.data for x, y, z in zip(t.x, t.y, t.z)
        } == original
        target = points.loc[points.prism_id.eq(selected)].iloc[0]
        assert tuple(fig.data[-1].x) == (target.easting,)
        assert tuple(fig.data[-1].y) == (target.northing,)
        assert tuple(fig.data[-1].z) == (target.rl,)


def test_centered_2d_window_and_3d_camera_target_actual_prism(app):
    points = app.reader.spatial("2014-02-20 23:59:59")
    chosen = points.iloc[-1]
    fig = spatial(points, "2D", selected=chosen.prism_id, focus=True)
    assert np.isclose(sum(fig.layout.xaxis.range) / 2, chosen.easting)
    assert np.isclose(sum(fig.layout.yaxis.range) / 2, chosen.northing)
    full = spatial(points, "2D", selected=chosen.prism_id, focus=False)
    assert full.layout.xaxis.range is None and full.layout.yaxis.range is None
    focused = spatial(points, "3D", selected=chosen.prism_id, focus=True)
    assert focused.layout.scene.camera.center.to_plotly_json()
    for axis, value in (
        ("xaxis", chosen.easting),
        ("yaxis", chosen.northing),
        ("zaxis", chosen.rl),
    ):
        assert np.isclose(sum(getattr(focused.layout.scene, axis).range) / 2, value)
    assert not any(t.type in ("surface", "mesh3d", "scattermapbox") for t in focused.data)


def test_empty_spatial_scene_has_no_invented_points(app):
    points = app.reader.spatial("1900-01-01")
    for dimension in ("2D", "3D"):
        assert len(spatial(points, dimension, selected="missing", focus=True).data) == 0


def test_workspace_center_reset_and_empty_filters(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=15)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()
    assert not at.exception and not at.error
    assert at.selectbox(key="sx_selected").value is None
    at.selectbox(key="sx_selected").set_value("22-1917").run()
    [b for b in at.button if b.label == "Centrar"][0].click().run()
    assert at.session_state["sx_focus"] and not at.exception and not at.error
    [b for b in at.button if b.label == "Vista completa"][0].click().run()
    assert not at.session_state["sx_focus"] and not at.exception
    [i for i in at.text_input if i.label == "Buscar prisma"][0].set_value("SIN-PRISMA").run()
    assert not at.exception and not at.error
    assert any(
        "No hay puntos disponibles para visualizar con los criterios actuales." in x.value
        for x in at.info
    )

    reset_buttons = [b for b in at.button if b.label == "Restablecer filtros"]
    assert reset_buttons

    reset_buttons[0].click().run()

    assert not at.exception and not at.error
    assert at.session_state["sx_search"] == ""
    assert at.session_state["sx_state"] == "Todos"
    assert at.session_state["sx_candidates"] is False

def test_spatial_identifier_control_changes_marker_labels(app):
    points = app.reader.spatial("2014-02-20 23:59:59")

    with_labels = spatial(points, "3D", labels=True)
    without_labels = spatial(points, "3D", labels=False)

    assert all(trace.mode == "markers+text" for trace in with_labels.data)
    assert all(trace.mode == "markers" for trace in without_labels.data)

def test_spatial_legend_reports_visible_state_counts(app):
    points = app.reader.spatial("2014-02-20 23:59:59")
    fig = spatial(points, "3D")

    legend_names = {
        trace.name
        for trace in fig.data
        if trace.showlegend is not False
    }

    counts = points.causal_state.value_counts()

    candidate_count = int(counts.get("candidato_revision", 0))
    mark_count = int(
        counts.get("marca_aislada", 0)
        + counts.get("episodio_en_observacion", 0)
    )
    non_evaluable_count = int(counts.get("no_evaluable", 0))
    normal_count = int(counts.get("sin_marca", 0))

    if candidate_count:
        assert f"Candidato para revisión ({candidate_count})" in legend_names

    if mark_count:
        assert f"Marca estadística ({mark_count})" in legend_names

    if non_evaluable_count:
        assert f"No evaluable ({non_evaluable_count})" in legend_names

    if normal_count:
        assert f"Sin marca ({normal_count})" in legend_names


def test_visible_state_summary_matches_spatial_data(app):
    points = app.reader.spatial("2014-02-20 23:59:59")
    summary = _visible_state_summary(points)

    assert sum(summary.values()) == len(points)
    assert summary["Candidato para revisión"] == int(
        points.causal_state.eq("candidato_revision").sum()
    )
    assert summary["Marca estadística"] == int(
        points.causal_state.isin(
            ["marca_aislada", "episodio_en_observacion"]
        ).sum()
    )