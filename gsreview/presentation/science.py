"""Independent scientific output; never recolor simulated or historical states."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timezone
from pathlib import Path

from gsreview.analytics.causal_features import TARGET
from gsreview.domain.rules import ValidationError
from gsreview.application.workflow import data_version, at_cutoff, matching_scores, matching_forecast
from gsreview.presentation.navigation import navigate


def render_anomalies(c, token, scenario_id, frame):
    st.subheader("Detección estadística · Isolation Forest congelado")
    st.caption("Score de atipicidad, no probabilidad de falla ni nivel de riesgo. "
               "Los estados y scores del generador sintético siguen siendo simulados por reglas. "
               "Modelo entrenado en West Wall; transferencia a otras fuentes no validada geotécnicamente.")
    if TARGET not in frame:
        st.info("Inferencia bloqueada: añade reported_3d_movement_mm (milímetros reportados). "
                "Las tasas no sustituyen esa magnitud; no se integran ni se inventan desplazamientos.")
        return
    signature = data_version(frame)
    dates = sorted(pd.to_datetime(frame.timestamp, utc=True).unique())
    saved = pd.to_datetime(st.session_state.get("scenario_analysis_cutoff"), utc=True)
    cutoff = st.select_slider("Fecha de corte del análisis", dates, value=saved if saved in dates else dates[-1], key="science_analysis_cutoff_"+scenario_id)
    st.session_state.scenario_analysis_cutoff = pd.to_datetime(cutoff, utc=True).isoformat()
    prefix = at_cutoff(frame, cutoff)
    if st.button("Ejecutar Isolation Forest verificado", key="science_run_" + scenario_id):
        st.session_state.pop("scenario_science_result", None)
        try:
            with st.spinner("Verificando artefactos, equivalencia histórica y características causales…"):
                scores, validation = c.science.anomalies(token, scenario_id, prefix)
        except ValidationError as exc:
            st.error(str(exc))
        else:
            st.session_state.scenario_science_result = {
                "scenario": scenario_id, "signature": signature,
                "scores": scores, "validation": validation,
                "cutoff": pd.to_datetime(cutoff, utc=True).isoformat(),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
    stored = st.session_state.get("scenario_science_result", {})
    if (stored.get("scenario") == scenario_id and stored.get("signature") == signature
            and stored.get("cutoff") == pd.to_datetime(cutoff, utc=True).isoformat()):
        st.caption("Inferencia real del modelo congelado sobre este escenario. "
                   "No modifica episodios ni dictámenes humanos.")
        st.dataframe(stored["scores"], hide_index=True)
        with st.expander("Trazabilidad y reproducción histórica"):
            st.json(stored["validation"])
    render_forecasts(c, token, scenario_id, frame, signature, cutoff)
    st.button("Continuar a revisión humana", key="science_continue_"+scenario_id,
              on_click=navigate, args=("Bandeja de revisión",))


def render_forecasts(c, token, scenario_id, frame, signature, cutoff=None):
    st.subheader("Pronóstico escalar experimental")
    st.caption("Cuantiles 0.10/0.50/0.90 en mm; no predicción de colapso. "
               "Los intervalos empíricos de referencia no garantizan cobertura del 80 %. "
               "Sin proyección de posiciones 3D ni modificación de los prismas.")
    ids = sorted(frame.prism_id.unique())
    selected = st.session_state.get("scenario_selected_prism")
    prism = st.selectbox("Prisma para pronóstico", ids, index=ids.index(selected) if selected in ids else 0,
                        key="science_prism_" + scenario_id)
    st.session_state.scenario_selected_prism = prism
    cutoff = cutoff if cutoff is not None else pd.to_datetime(frame.timestamp, utc=True).max()
    hours = st.selectbox("Horizonte de pronóstico (horas)", [24, 72, 168],
                        key="science_horizon_" + scenario_id)
    use_chronos = st.checkbox("Comparar con Chronos-2", key="science_chronos_" + scenario_id)
    if use_chronos:
        from gsreview.application.chronos import LocalChronos
        ready, message = LocalChronos(c.app_root if hasattr(c, "app_root") else Path(__file__).resolve().parents[2]).availability()
        st.info(message)
    else:
        ready = True
    request = (scenario_id, signature, prism, hours, use_chronos, pd.to_datetime(cutoff, utc=True).isoformat())
    if st.button("Evaluar y pronosticar", key="science_forecast_" + scenario_id):
        st.session_state.pop("scenario_forecast_result", None)
        try:
            with st.spinner("Evaluando ventanas cronológicas y pronóstico escalar…"):
                if not ready:
                    raise ValidationError("Chronos-2 no disponible. Puedes ejecutar únicamente las referencias temporales.")
                future, metrics, report = c.science.forecasts(token, scenario_id, at_cutoff(frame, cutoff), prism, hours, use_chronos)
        except ValidationError as exc:
            st.error(str(exc))
        else:
            st.session_state.scenario_forecast_result = {
                "request": request, "future": future, "metrics": metrics, "report": report,
                "cutoff": pd.to_datetime(cutoff, utc=True).isoformat(),
            }
    stored = st.session_state.get("scenario_forecast_result", {})
    if stored.get("request") == request:
        st.caption(f"Prisma {prism} · corte {stored['cutoff']} · horizonte {hours} h · "
                   f"ejecución {stored['report'].get('executed_at', 'No registrada')} · "
                   f"modelos {stored['report'].get('model_versions', {})}")
        temporal_chart(frame, prism, cutoff, stored["future"])
        st.dataframe(stored["future"], hide_index=True)
        if stored["metrics"].empty:
            st.warning("Historia insuficiente para folds de evaluación a este horizonte; sin métricas de validación.")
        else:
            st.caption("MAE/RMSE en mm y cobertura [q10,q90] por fold. Sin métricas inventadas para datos ausentes.")
            st.dataframe(stored["metrics"], hide_index=True)
        with st.expander("Procedencia y ejecución del pronóstico"):
            st.json(stored["report"])
    else:
        temporal_chart(frame, prism, cutoff)


def temporal_chart(frame, prism, cutoff, future=None):
    observed = at_cutoff(frame.loc[frame.prism_id.eq(prism)], cutoff).sort_values("timestamp")
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=observed.timestamp, y=observed[TARGET], mode="lines+markers",
                               name="Mediciones sintéticas" if "causal_state" in frame else "Mediciones observadas",
                               connectgaps=False, line={"color": "#247BA0"}))
    if future is not None:
        for model, rows in future.groupby("model", sort=False):
            rows = rows.sort_values("timestamp")
            figure.add_trace(go.Scatter(x=rows.timestamp, y=rows.q10, mode="lines", line={"width": 0},
                                       name=model+" q10", showlegend=False, connectgaps=False))
            figure.add_trace(go.Scatter(x=rows.timestamp, y=rows.q90, mode="lines", line={"width": 0},
                                       fill="tonexty", name=model+" intervalo q10–q90", connectgaps=False))
            figure.add_trace(go.Scatter(x=rows.timestamp, y=rows.q50, mode="lines", line={"dash": "dash"},
                                       name=model+" mediana proyectada"))
    figure.update_layout(title="Desplazamiento escalar · "+str(prism), xaxis_title="Fecha", yaxis_title="mm", height=390)
    st.plotly_chart(figure, width="stretch")


def render_prism_detail(c, token, scenario_id, frame, prism, cutoff):
    if prism not in set(frame.prism_id):
        return
    subset = at_cutoff(frame.loc[frame.prism_id.eq(prism)], cutoff).sort_values("timestamp")
    if subset.empty:
        st.info("Sin mediciones al corte seleccionado.")
        return
    st.session_state.scenario_selected_prism = prism
    st.session_state.scenario_analysis_cutoff = pd.to_datetime(cutoff, utc=True).isoformat()
    row = subset.iloc[-1]
    st.subheader("Ficha del prisma · "+str(prism))
    position = row
    if scenario_id == "john_henry" and "model_eligible" in subset:
        valid_positions = subset.loc[subset.model_eligible.fillna(False)]
        position = valid_positions.iloc[-1] if not valid_positions.empty else subset.iloc[0]
    fields = [key for key in ("sector_topografico", "pendiente_base_deg", "timestamp", TARGET) if key in subset]
    st.write({key: str(row[key]) for key in fields})
    st.write("Última posición válida (o inicial si no hay observación válida):",
             {key: str(position[key]) for key in ("easting", "northing", "rl", "timestamp") if key in subset})
    st.caption("Calidad de la última medición: " +
               ("magnitud escalar ausente" if TARGET not in subset or pd.isna(row[TARGET]) else
                "magnitud escalar disponible; evaluabilidad del modelo se comprueba por separado"))
    if {"easting", "northing", "rl"}.issubset(subset) and scenario_id == "john_henry":
        valid = subset.loc[subset.model_eligible.fillna(False)] if "model_eligible" in subset else subset
        last = valid.iloc[-1] if not valid.empty else subset.iloc[0]
        vector = (last[["easting", "northing", "rl"]].astype(float)-subset.iloc[0][["easting", "northing", "rl"]].astype(float))*1000
        st.write("Componentes vectoriales simuladas desde el inicio (mm):", dict(zip(["ΔEste", "ΔNorte", "ΔCota"], vector)))
        st.caption("Se usa la última posición válida. Sin dato nuevo no se inventa movimiento.")
    scores = matching_scores(st.session_state, scenario_id, frame)
    if scores:
        at = at_cutoff(scores["scores"].loc[scores["scores"].prism_id.eq(prism)], cutoff).sort_values("timestamp")
        if not at.empty and pd.to_datetime(at.timestamp.iloc[-1], utc=True) == pd.to_datetime(row.timestamp, utc=True):
            result = at.iloc[-1]
            st.write("Isolation Forest:", "No evaluable" if not result.model_eligible else
                     "Marca estadística" if bool(result.isolation_forest_marked_q99) else "Sin marca estadística")
            st.write("Calidad:", result.model_ineligibility_reason or "Características disponibles", "· score:", str(result.isolation_forest_score))
        else:
            st.info("Isolation Forest pendiente para la medición de este corte.")
    else:
        st.info("Isolation Forest aún no ejecutado para esta versión de datos.")
    if TARGET in frame:
        forecast = matching_forecast(st.session_state, scenario_id, frame, prism, cutoff)
        temporal_chart(frame, prism, cutoff, forecast["future"] if forecast else None)
        if forecast:
            st.caption("Pronóstico disponible · "+str(forecast["report"].get("model_versions", {})))
    st.button("Continuar al análisis", key="detail_analyze_"+scenario_id, on_click=navigate, args=("Prismas",))
