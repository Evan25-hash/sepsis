# Pipeline Model (`pipeline_model/`)

Pelatihan dan evaluasi model dijalankan di Google Colab (GPU T4). Notebook utama: `skripsi_v4.ipynb`.

## Instalasi

```bash
pip install torch pandas numpy scikit-learn captum plotly openpyxl
```

## Alur Notebook

| Cell | Tahap | Keterangan |
|---|---|---|
| 1A | Load data | Baca dataset M8 dari BigQuery (`skripsi-sepsis-488003.sepsis_v3`) |
| 2B–2C | Konstruksi label | `has_shock` (biner per pasien), `t_shock_onset` (jam pertama syok) |
| 2D | Eksklusi onset dini | Hapus stays dengan onset < 4 jam |
| 3A–3D | Seleksi fitur | Kruskal-Wallis η², *distance correlation*, mRMR *greedy* + BH-FDR → 21 fitur |
| 4B | Imputasi | interpolasi linear/ffill/bfill per stay |
| 5A | Split & normalisasi | Subject-level stratified 70/15/15; StandardScaler fit pada train |
| 5B | Bangun sekuen | *Framing B* (PSP): growing window, K_SHOCK=20, K_NONSHOCK=15, λ=0.05 |
| 6A | Pelatihan GRU | Hidden=32, layers=2, dropout=0.4 |
| 6B | Pelatihan TCN | 3 blok, dilation 1/2/4, kernel=3, receptive field=15 timestep |
| 6C | Pelatihan Transformer | d_model=32, heads=2, layers=1, causal mask |
| 7 | Evaluasi test set | Threshold via maksimasi TS-CUS pada validation set |
| 8 | Analisis *lead-time* | Evaluasi per bucket horizon prediksi (≤6h, 6–12h, 12–24h, 24–48h, >48h) |
| 9 | Interpretabilitas | Shapley Value Sampling (Captum) pada 10% data test |

## Metrik Evaluasi

```
TS-CUS = 0.40 × PLR + 0.30 × AUPRC + 0.30 × (1 − FAR)
```

Bobot ditetapkan sebelum eksperimen. PLR dan FAR dihitung pada level pasien.

## Hasil Evaluasi (Test Set)

| Model | AUROC | AUPRC | PLR | FAR | TS-CUS | Threshold |
|---|---|---|---|---|---|---|
| **TCN** | 0.8675 | 0.6941 | **0.8797** | 0.2793 | **0.7763** | 0.60 |
| GRU | 0.8762 | 0.7022 | 0.8101 | 0.2086 | 0.7721 | 0.75 |
| Transformer | 0.8824 | 0.7138 | 0.8165 | 0.2439 | 0.7675 | 0.70 |

Model terbaik: **TCN**. *Checkpoint* tersimpan di `cdss_apps/assets/checkpoints/best_tcn.pt`.
