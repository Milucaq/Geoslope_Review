"""UI imports, filters and rejection paths use controlled in-memory CSVs."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gsreview.application.csv_import import validate_csv
from gsreview.presentation import external_spatial_workspace as workspace


HEADER = (
    "source_record_id,prism_id,timestamp,easting,northing,"
    "rl,movement_rate_mm_per_day,elapsed_hours\n"
)
CSV = (HEADER +
       "R1,P1,2026-01-01T00:00:00Z,100,200,10,1,24\n" +
       "R2,P1,2026-01-02T00:00:00Z,101,201,11,2,24\n" +
       "R3,P2,2026-01-01T00:00:00Z,110,210,20,3,24\n").encode()


def external_app():
    from gsreview.presentation.external_spatial_workspace import render_external_workspace

    render_external_workspace()


@pytest.fixture
def external_ui(monkeypatch):
    upload = {"file": None}
    charts = []
    # Streamlit AppTest has no upload driver; replace only that browser boundary.
    monkeypatch.setattr(workspace.st, "file_uploader", lambda *a, **k: upload["file"])
    monkeypatch.setattr(workspace.st, "plotly_chart", lambda fig, **k: charts.append(fig))
    return upload, charts


def test_uploaded_csv_filters_last_positions_and_survives_navigation(external_ui):
    upload, charts = external_ui
    upload["file"] = SimpleNamespace(name="controlled.csv", type="text/csv", getvalue=lambda: CSV)
    at = AppTest.from_function(external_app).run()
    assert not at.exception and not at.error
    assert [m.value for m in at.metric] == ["3", "2"]
    trace = charts[-1].data[0]
    assert trace.type == "scatter3d"
    assert dict(zip(trace.text, trace.x)) == {"P1": 101, "P2": 110}
    stored = at.session_state["scenario_external_frame"].copy(deep=True)
    at.selectbox(key="hu110_prism").select("P2").run()
    assert list(charts[-1].data[0].text) == ["P2"]
    assert len(at.dataframe[0].value) == 1
    at.segmented_control(key="hu110_dimension").set_value("2D").run()
    assert charts[-1].data[0].type == "scatter"
    assert charts[-1].layout.xaxis.scaleanchor == "y"
    # File upload widget can disappear across pages; the session copy remains.
    upload["file"] = None
    at.run()
    assert not at.exception and not at.error
    pd.testing.assert_frame_equal(at.session_state["scenario_external_frame"], stored)
    assert list(charts[-1].data[0].text) == ["P2"]


def test_no_upload_has_no_points_or_historical_fallback(external_ui):
    _, charts = external_ui
    at = AppTest.from_function(external_app).run()
    assert not at.exception and not at.error and not at.metric
    assert any("Columnas requeridas" in c.value for c in at.caption)
    assert not charts


@pytest.mark.parametrize("failure", ["binary", "filename", "mime", "schema", "size"])
def test_bad_replacement_discards_cached_data_and_never_draws(external_ui, monkeypatch, failure):
    upload, charts = external_ui
    at = AppTest.from_function(external_app)
    at.session_state["scenario_external_frame"] = validate_csv(CSV)
    content, name, mime = CSV, "controlled.csv", "text/csv"
    if failure == "binary":
        content = b"MZexecutable"
    elif failure == "filename":
        name = "../unsafe.csv"
    elif failure == "mime":
        mime = "text/html"
    elif failure == "schema":
        content = b"prism_id\nP1\n"
    else:
        monkeypatch.setattr(workspace, "MAX_FILE_SIZE", 10)
    upload["file"] = SimpleNamespace(name=name, type=mime, getvalue=lambda: content)
    at.run()
    assert not at.exception
    assert any("CSV rechazado" in e.value for e in at.error)
    assert "scenario_external_frame" not in at.session_state
    assert not charts and not at.dataframe


def test_invalid_coordinates_are_omitted_and_all_invalid_rejected(external_ui):
    _, charts = external_ui
    data = validate_csv(CSV)
    data.loc[data.prism_id.eq("P2"), "easting"] = np.nan
    original = data.copy(deep=True)
    at = AppTest.from_function(external_app)
    at.session_state["scenario_external_frame"] = data
    at.run()
    assert not at.exception and not at.error
    assert any("Se omitieron 1" in w.value for w in at.warning)
    assert list(charts[-1].data[0].text) == ["P1"]
    pd.testing.assert_frame_equal(data, original)
    data.loc[:, "easting"] = np.nan
    at.session_state["scenario_external_frame"] = data
    charts.clear()
    at.run()
    assert any("coordenadas válidas" in e.value for e in at.error)
    assert not charts
