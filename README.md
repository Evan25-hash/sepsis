# Prediksi Dini Progresi Syok Septik pada Pasien Sepsis di ICU Menggunakan *Deep Learning* Berbasis Deret Waktu

Repositori ini berisi kode dan artefak teknis untuk penelitian prediksi dini syok septik menggunakan model *deep learning* berbasis deret waktu pada dataset MIMIC-IV v3.1. Pipeline terdiri dari tiga bagian: konstruksi data via BigQuery SQL, pelatihan dan evaluasi model, serta prototipe CDSS berbasis Streamlit.

```
sepsis/
├── pipeline_query/    — query SQL BigQuery (M0–M8)
├── pipeline_model/    — notebook pelatihan dan evaluasi model
└── cdss_apps/         — prototipe aplikasi CDSS
```

---

## Prasyarat

- Python 3.10+
- Akses MIMIC-IV v3.1 via Google BigQuery (memerlukan credentialed access dari PhysioNet)
- Google Cloud project dengan izin `bigquery.dataViewer` pada `physionet-data`

---

## 1. Pipeline Data (`pipeline_query/`)

Query dijalankan secara berurutan di Google BigQuery. M2–M7 dapat dijalankan paralel setelah M1 selesai.

```
M0 → M1 → M2, M3, M4, M5, M6, M7 (paralel) → M8
```

| Modul | File | Output |
|---|---|---|
| M0 | `mf0__cohort.sql` | Kohort ICU sepsis (Sepsis-3, dewasa, kunjungan pertama, MICU/SICU) |
| M1 | `mf1__hourly_backbone.sql` | Grid jam per stay (`stay_id × hr`) |
| M2 | `mf2__hourly_vitals.sql` | Tanda vital per jam |
| M3 | `mf3__hourly_labs.sql` | Hasil lab per jam |
| M4 | `mf4__hourly_gcs.sql` | GCS per jam |
| M5 | `mf5__hourly_urine.sql` | Volume urin per jam |
| M6 | `mf6__static_features.sql` | Fitur statis per stay |
| M7 | `mf7__hourly_vasopressor.sql` | Status vasopressor per jam |
| M8 | `mf8__sepsis_hourly_dataset.sql` | Dataset final (hasil `LEFT JOIN` M1–M7) |

Output M8 disimpan di `skripsi-sepsis-488003.sepsis_v3`. Kohort final: 4.626 ICU stay, 906.989 baris jam, prevalensi syok 22,6%.

---

## 2. Pipeline Model (`pipeline_model/`)

Dijalankan di Google Colab (GPU T4). Notebook utama: `skripsi_v4.ipynb`.

**Instalasi:**

```bash
pip install torch pandas numpy scikit-learn captum plotly openpyxl
```

**Ringkasan alur notebook:**

- Konstruksi label syok per pasien (*patient-level binary*, tanpa kontaminasi pasca-onset)
- Seleksi 21 fitur via mRMR *greedy* + BH-FDR dari 77 kandidat
- Split 70/15/15 berbasis subjek, normalisasi StandardScaler (fit pada train)
- Pelatihan GRU, TCN, dan Transformer Encoder dengan hyperparameter identik
- Evaluasi dengan metrik TS-CUS = 0.40 × PLR + 0.30 × AUPRC + 0.30 × (1 − FAR)
- Interpretabilitas via Shapley Value Sampling (Captum) pada 10% data test

**Hasil evaluasi (test set):**

| Model | AUROC | AUPRC | PLR | FAR | TS-CUS |
|---|---|---|---|---|---|
| **TCN** | 0.8675 | 0.6941 | **0.8797** | 0.2793 | **0.7763** |
| GRU | 0.8762 | 0.7022 | 0.8101 | 0.2086 | 0.7721 |
| Transformer | 0.8824 | 0.7138 | 0.8165 | 0.2439 | 0.7675 |

Model terbaik berdasarkan TS-CUS: **TCN** (threshold 0.60, ditetapkan via optimasi pada validation set).

---

## 3. Aplikasi CDSS (`cdss_apps/`)

Prototipe *Clinical Decision Support System* untuk pemantauan risiko syok septik per jam. Input berupa file Excel; mendukung hingga 20 pasien per sesi.

**Menjalankan aplikasi:**

```bash
cd cdss_apps
pip install -r requirements.txt
streamlit run app.py
```

**Struktur folder:**

```
cdss_apps/
├── app.py
├── inference.py
├── imputation.py
├── validation.py
├── tcn_arch.py
├── requirements.txt
└── assets/
    ├── checkpoints/
    │   ├── best_tcn.pt
    │   ├── scaler_21feats.pkl
    │   └── feature_cols_final.json
    ├── demos/
    └── templates/
```

Template Excel untuk input data tersedia di sidebar aplikasi atau di `assets/templates/`.

---

## Akses Data

Dataset MIMIC-IV memerlukan sertifikasi CITI Program dan *credentialed access* melalui [PhysioNet](https://physionet.org/content/mimiciv/). Kode di repositori ini tidak menyertakan data apapun.
