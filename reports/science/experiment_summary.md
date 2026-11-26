# Resumen de experimentos registrados

Caso sintético SYN-W01, semilla 42, 45 días, cadencia 6 h; tres folds no solapados por horizonte. No son resultados del prisma activo ni validación geotécnica de campo.

MAE ponderado por objetivos observados. RMSE conjunto = sqrt(suma(RMSE_fold² × n_fold)/suma(n_fold)). Cobertura ponderada por pares objetivo/intervalo conocidos; objetivo nominal 0.80.

| Modelo | Horizonte (h) | MAE (mm) | RMSE (mm) | Cobertura | Objetivos |
|---|---:|---:|---:|---:|---:|
| chronos2 | 24 | 1.578538 | 1.899163 | 1.000000 | 12 |
| chronos2 | 72 | 4.787263 | 5.659489 | 1.000000 | 36 |
| chronos2 | 168 | 20.261664 | 25.613131 | 0.666667 | 84 |
| linear | 24 | 171.076897 | 171.303433 | 0.000000 | 12 |
| linear | 72 | 162.516540 | 164.780090 | 0.000000 | 36 |
| linear | 168 | 143.943642 | 156.264341 | 0.000000 | 84 |
| persistence | 24 | 21.473633 | 23.547841 | 0.000000 | 12 |
| persistence | 72 | 50.957786 | 58.089387 | 0.000000 | 36 |
| persistence | 168 | 87.720940 | 104.978187 | 0.000000 | 84 |

## Comparación limitada a este experimento

- 24 h, frente a persistence: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.
- 24 h, frente a linear: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.
- 72 h, frente a persistence: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.
- 72 h, frente a linear: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.
- 168 h, frente a persistence: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.
- 168 h, frente a linear: Chronos-2 presenta MAE menor, RMSE menor y cobertura más próxima a 0.80.

Chronos-2 reduce ambos errores frente a ambas referencias en todos los horizontes de este caso. Esto no demuestra superioridad general ni en campo. Cobertura real de Chronos-2: 24 h: 1.000000; 72 h: 1.000000; 168 h: 0.666667; comparar con nominal 0.80, no asumir calibración.

Fuente: synthetic_backtest.csv; no se ajustaron ni inventaron métricas.
