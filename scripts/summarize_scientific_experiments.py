"""Summarize existing synthetic experiments, without recomputing model inference."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gsreview.analytics.experiment_summary import summarize_experiments


def main():
    directory = ROOT / "reports/science"
    summary, comparison = summarize_experiments(directory / "synthetic_backtest.csv")
    summary.to_csv(directory / "experiment_summary.csv", index=False)
    comparison.to_csv(directory / "experiment_comparisons.csv", index=False)
    lines = ["# Resumen de experimentos registrados", "",
        "Caso sintético SYN-W01, semilla 42, 45 días, cadencia 6 h; tres folds no solapados por horizonte. "
        "No son resultados del prisma activo ni validación geotécnica de campo.", "",
        "MAE ponderado por objetivos observados. RMSE conjunto = sqrt(suma(RMSE_fold² × n_fold)/suma(n_fold)). "
        "Cobertura ponderada por pares objetivo/intervalo conocidos; objetivo nominal 0.80.", "",
        "| Modelo | Horizonte (h) | MAE (mm) | RMSE (mm) | Cobertura | Objetivos |", "|---|---:|---:|---:|---:|---:|"]
    for row in summary.itertuples():
        lines.append(f"| {row.model} | {row.horizon_hours} | {row.mae_mm:.6f} | {row.rmse_mm:.6f} | {row.coverage:.6f} | {row.observed_targets} |")
    lines += ["", "## Comparación limitada a este experimento", ""]
    for row in comparison.itertuples():
        mae = "menor" if row.chronos_lower_mae else "no menor"
        rmse = "menor" if row.chronos_lower_rmse else "no menor"
        coverage = "más próxima" if row.chronos_closer_to_80pct else "no más próxima"
        lines.append(f"- {row.horizon_hours} h, frente a {row.reference}: Chronos-2 presenta MAE {mae}, RMSE {rmse} y cobertura {coverage} a 0.80.")
    outcome = ("Chronos-2 reduce ambos errores frente a ambas referencias en todos los horizontes de este caso."
               if comparison.chronos_lower_mae.all() and comparison.chronos_lower_rmse.all() else
               "Chronos-2 no reduce ambos errores frente a todas las referencias/horizontes; consultar cada comparación.")
    coverage = "; ".join(f"{r.horizon_hours} h: {r.coverage:.6f}" for r in summary.loc[summary.model.eq("chronos2")].itertuples())
    lines += ["", outcome+" Esto no demuestra superioridad general ni en campo. "
              "Cobertura real de Chronos-2: "+coverage+"; comparar con nominal 0.80, no asumir calibración.", "",
              "Fuente: synthetic_backtest.csv; no se ajustaron ni inventaron métricas."]
    (directory / "experiment_summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
