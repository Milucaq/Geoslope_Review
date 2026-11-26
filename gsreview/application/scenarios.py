"""Session-local scenario identity. No database or frozen artifact writes."""

from dataclasses import dataclass

from gsreview.domain.rules import ValidationError


@dataclass(frozen=True)
class Scenario:
    id: str
    label: str
    kind: str
    provenance: str
    spatial_reference: str
    validation: str


SCENARIOS = {
    "historical": Scenario(
        "historical", "Histórico congelado", "historical_readonly",
        "Artefactos históricos verificados; resultados precomputados",
        "Referencia espacial histórica no validada para John Henry", "frozen_verified",
    ),
    "external": Scenario(
        "external", "CSV externo temporal", "external",
        "CSV aportado por el usuario; persistente al guardar el escenario",
        "CRS y datum no declarados; sin vinculación a topografía", "pending_csv",
    ),
    "john_henry": Scenario(
        "john_henry", "John Henry · experimental", "synthetic",
        "OpenTopography 2023; prismas y mediciones simulados por reglas",
        "EPSG:6339 / NAVD88", "experimental_not_scientifically_validated",
    ),
}


def select_scenario(state, scenario_id):
    """Clear selections across datasets, while retaining each scenario's own data."""
    if scenario_id not in SCENARIOS:
        raise ValidationError("Escenario desconocido.")
    if state.get("active_scenario", "historical") != scenario_id:
        for key in ("scenario_saved_id", "scenario_saved_revision", "scenario_name"):
            state.pop(key, None)
        for key in list(state):
            if key.startswith(("sx_", "inbox_", "detail_", "review_", "science_", "report_")):
                del state[key]
        state.pop("spatial_access_logged", None)
        state.pop("export_ready", None)
        state.pop("scenario_science_result", None)
        state.pop("scenario_forecast_result", None)
        for key in list(state):
            if key.startswith("scenario_review_") or key in {"scenario_selected_prism", "scenario_analysis_cutoff", "scenario_visualized", "scenario_report_version"}:
                del state[key]
    state["active_scenario"] = scenario_id
    return SCENARIOS[scenario_id]


def bind_session(state, owner):
    """A replacement authenticated session must never inherit uploaded measurements."""
    if state.get("scenario_owner") != owner:
        for key in list(state):
            if key.startswith(("scenario_", "hu110_", "hu106_", "jh_", "sx_",
                               "inbox_", "detail_", "review_", "synthetic_", "science_", "report_")):
                del state[key]
        state.pop("active_scenario", None)
        state.pop("export_ready", None)
        state["scenario_owner"] = owner
    return select_scenario(state, state.get("active_scenario", "historical"))


def supports_page(scenario_id, page):
    if scenario_id not in SCENARIOS:
        raise ValidationError("Escenario desconocido.")
    return True  # Each operational page now has an isolated scenario implementation.


def activate_external(state, frame, source=None):
    """Widget callback: runs before the selector is instantiated on the next rerun."""
    state["scenario_external_frame"] = frame.copy(deep=True)
    state["scenario_external_source"] = source or {}
    select_scenario(state, "external")
    state["scenario_selector"] = "external"
