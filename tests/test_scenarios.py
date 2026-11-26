"""Scenario boundaries use only in-memory state and synthetic test measurements."""

import pytest
from streamlit.testing.v1 import AppTest

from gsreview.application.scenarios import (
    SCENARIOS, bind_session, select_scenario, supports_page,
)
from gsreview.domain.rules import ValidationError


def test_switch_clears_cross_scenario_selections_but_retains_owned_data():
    state = {"active_scenario": "historical", "inbox_prism": "P1",
             "detail_prism": "P1", "sx_prisms": ["P1"],
             "scenario_external_frame": "external-only", "token": "test"}
    active = select_scenario(state, "external")
    assert active.kind == "external"
    assert not {"inbox_prism", "detail_prism", "sx_prisms"}.intersection(state)
    assert state["scenario_external_frame"] == "external-only"
    assert state["token"] == "test"
    select_scenario(state, "historical")
    assert state["scenario_external_frame"] == "external-only"


def test_session_replacement_discards_private_scenario_state():
    state = {}
    bind_session(state, "test-session-a")
    select_scenario(state, "external")
    state.update(scenario_external_frame="private", hu110_csv="private",
                 synthetic_scenario="private", jh_seed=2)
    bind_session(state, "test-session-a")
    assert state["active_scenario"] == "external"
    assert bind_session(state, "test-session-b").id == "historical"
    assert not {"scenario_external_frame", "hu110_csv", "synthetic_scenario", "jh_seed"}.intersection(state)


def test_unknown_selection_is_rejected_atomically():
    state = {"active_scenario": "historical", "detail_prism": "P1"}
    before = state.copy()
    with pytest.raises(ValidationError):
        select_scenario(state, "untrusted")
    assert state == before


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_historical_reviews_and_exports_cannot_be_mixed(scenario):
    for page in ("Bandeja de revisión", "Prismas", "Reportes"):
        assert supports_page(scenario, page)  # Phase C supplies isolated implementations for all three.
    assert SCENARIOS[scenario].kind == {"historical": "historical_readonly", "external": "external", "john_henry": "synthetic"}[scenario]
    assert supports_page(scenario, "Vista espacial")


def test_navigation_never_displays_historical_dashboard_for_external(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=20)
    at.session_state["token"] = app.test_admin
    at.run()
    at.selectbox(key="scenario_selector").select("external").run()
    assert not at.exception and not at.error
    assert any(t.value == "Panorama del escenario" for t in at.title)
    assert not any(t.value == "Panorama de revisión" for t in at.title)
    at.button(key="rail_Reportes").click().run()
    assert any(t.value == "Reporte del escenario" for t in at.title)
    assert not any(t.value == "Reportes y trazabilidad" for t in at.title)
    assert not at.get("download_button")
    at.selectbox(key="scenario_selector").select("historical").run()
    assert any(t.value == "Reportes y trazabilidad" for t in at.title)
