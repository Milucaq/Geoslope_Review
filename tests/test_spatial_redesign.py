import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from gsreview.presentation.spatial_controller import filter_points, accept_selection
from gsreview.application.spatial import SpatialService
from gsreview.domain.rules import AccessDenied


def test_filters_preserve_coordinates_and_candidates(app):
    points = app.reader.spatial("2014-02-20 23:59:59")
    assert len(points) == 49
    filtered = filter_points(points, only_candidates=True)
    assert filtered.candidate_hybrid.fillna(False).all()
    pd.testing.assert_frame_equal(filtered, points.loc[filtered.index])
    assert filter_points(points, "30-1994").prism_id.tolist() == ["30-1994"]
    assert filter_points(points, "missing").empty
    assert (
        filter_points(points, state="Marca estadística")
        .causal_state.isin(["marca_aislada", "episodio_en_observacion"])
        .all()
    )

def test_filter_points_supports_single_and_multiple_prism_selection(app):
    points = app.reader.spatial("2014-02-20 23:59:59")

    single = filter_points(
        points,
        selected_prisms=["30-1994"],
    )
    assert single.prism_id.unique().tolist() == ["30-1994"]

    selected = ["22-1917", "30-1994", "31-1991"]
    multiple = filter_points(
        points,
        selected_prisms=selected,
    )

    assert set(multiple.prism_id.unique()) == set(selected)
    pd.testing.assert_frame_equal(
        multiple,
        points.loc[points.prism_id.isin(selected)],
    )


def test_filter_points_empty_selection_preserves_all_points(app):
    points = app.reader.spatial("2014-02-20 23:59:59")

    filtered = filter_points(
        points,
        selected_prisms=[],
    )

    pd.testing.assert_frame_equal(filtered, points)


def test_prism_selection_combines_with_existing_filters(app):
    points = app.reader.spatial("2014-02-20 23:59:59")

    candidate_ids = (
        points.loc[points.candidate_hybrid.fillna(False), "prism_id"]
        .drop_duplicates()
        .tolist()
    )

    selected = candidate_ids[:2]

    filtered = filter_points(
        points,
        only_candidates=True,
        selected_prisms=selected,
    )

    assert filtered.candidate_hybrid.fillna(False).all()
    assert set(filtered.prism_id.unique()).issubset(set(selected))

def test_workspace_prism_multiselect_filters_and_restores_view(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))

    points = app.reader.spatial("2014-02-20 23:59:59")
    selected = sorted(points.prism_id.unique().tolist())[:2]

    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=40)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()

    assert not at.exception and not at.error

    prism_filter = at.multiselect(key="sx_prisms")
    assert prism_filter.value == []

    prism_filter.set_value(selected).run()

    assert not at.exception and not at.error
    assert set(at.multiselect(key="sx_prisms").value) == set(selected)

    real_prism_ids = set(points.prism_id.unique())

    visible_options = {
        value
        for value in at.selectbox(key="sx_selected").options
        if value in real_prism_ids
    }
    assert visible_options == set(selected)

    at.button(key="sx_clear_prisms").click().run()

    restored_options = {
        value
        for value in at.selectbox(key="sx_selected").options
        if value in real_prism_ids
    }
    assert restored_options == real_prism_ids
    
def test_click_event_rejects_invented_id_duplicates_and_invalid_camera():
    assert accept_selection(
        {"prism_id": "22-1917", "nonce": 1, "camera": None}, ["22-1917"], None
    ) == ("22-1917", None, 1)
    assert accept_selection({"prism_id": "invented", "nonce": 2}, ["22-1917"], 1) is None
    assert accept_selection({"prism_id": "22-1917", "nonce": 1}, ["22-1917"], 1) is None
    assert (
        accept_selection(
            {"prism_id": "22-1917", "nonce": 2, "camera": {"eye": {"x": float("inf")}}},
            ["22-1917"],
            1,
        )
        is None
    )


def test_spatial_service_requires_auth_and_logs_once_per_explicit_access(app):
    service = SpatialService(app)
    with pytest.raises(AccessDenied):
        service.points("invalid", pd.Timestamp("2014-02-20"))
    count = len(app.store.list("audit_log"))
    service.log_access(app.test_admin, "spatial_view_opened")
    assert len(app.store.list("audit_log")) == count + 1
    rows = service.series(app.test_admin, "30-1994", pd.Timestamp("2014-01-01"))
    assert rows.timestamp.le(pd.Timestamp("2014-01-01")).all()


def test_no_arbitrary_selection_and_linked_histories(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=20)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()
    assert not at.error and not at.exception
    assert at.selectbox(key="sx_selected").value is None
    at.selectbox(key="sx_selected").set_value("30-1994").run()
    assert any(x.value == "Prisma 30-1994" for x in at.subheader)
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Candidatos"] == "15"
    at.button(key="sx_history").click().run()
    assert (
        at.session_state["nav"] == "Prismas" and at.selectbox(key="detail_prism").value == "30-1994"
    )

def test_selected_prism_shows_measurement_detail_and_preserves_data(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))

    chosen = "30-1994"
    cutoff = pd.Timestamp(app.reader.rows.timestamp.max())

    service = SpatialService(app)
    rows = service.series(app.test_admin, chosen, cutoff)

    assert not rows.empty

    latest = rows.iloc[-1]
    before = app.reader.rows.copy(deep=True)

    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=40)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()

    at.selectbox(key="sx_selected").set_value(chosen).run()

    assert not at.exception and not at.error
    assert any(x.value == f"Prisma {chosen}" for x in at.subheader)

    markdown_values = [element.value for element in at.markdown]

    assert f"**Fecha:** {latest.timestamp}" in markdown_values

    movement = latest.reported_3d_movement_mm
    expected_movement = (
        "Sin dato" if pd.isna(movement) else f"{movement:.2f} mm"
    )

    assert f"**Desplazamiento:** {expected_movement}" in markdown_values

    assert app.reader.rows.equals(before)

def test_review_action_opens_same_prism_episode(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=20)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()
    at.selectbox(key="sx_selected").set_value("30-1994").run()
    at.button(key="sx_review").click().run()
    assert not at.exception and not at.error
    assert at.session_state["nav"] == "Bandeja de revisión"
    ep = app.reader.episodes.set_index("episode_id").loc[
        at.selectbox(key="inbox_open_episode").value
    ]
    assert ep.prism_id == "30-1994"


def test_compact_rail_opens_real_page(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=20)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Vista espacial"
    at.run()
    at.button(key="rail_Prismas").click().run()
    assert not at.error and not at.exception
    assert at.session_state["nav"] == "Prismas"
    assert any(x.value == "Detalle del prisma" for x in at.title)
    at.button(key="rail_Inicio").click().run()
    [button for button in at.button if button.label == "Revisar candidatos pendientes"][
        0
    ].click().run()
    assert not at.error and at.session_state["current_page"] == "Bandeja de revisión"


def test_engineer_compact_navigation_has_no_administrative_actions(app, monkeypatch):
    import pyotp

    app.auth.create_user(
        app.test_admin, "sampleengineer", "Ingeniero sintético", app.test_temporary, "ingeniero"
    )
    challenge, _ = app.auth.password_step("sampleengineer", app.test_temporary)
    _, secret = app.auth.enrollment(challenge)
    token, _ = app.auth.second_step(
        challenge, pyotp.TOTP(secret).at(app.test_clock[0]), enroll=True
    )
    app.auth.change_password(token, app.test_temporary, app.test_permanent)
    app.test_clock[0] += 31
    challenge, _ = app.auth.password_step("sampleengineer", app.test_permanent)
    token, _ = app.auth.second_step(challenge, pyotp.TOTP(secret).at(app.test_clock[0]))
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=20)
    at.session_state["token"] = token
    at.session_state["nav"] = "Vista espacial"
    at.run()
    assert not at.error and not at.exception
    keys = {button.key for button in at.button}
    assert "rail_Prismas" in keys
    assert not keys.intersection({"rail_Usuarios", "rail_Auditoría", "rail_Copias de seguridad"})
