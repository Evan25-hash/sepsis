# Prediksi Dini Progresi Syok Septik pada Pasien Sepsis di ICU Menggunakan *Deep Learning* Berbasis Deret Waktu

Repositori ini berisi seluruh artefak teknis penelitian prediksi dini syok septik menggunakan model *deep learning* berbasis deret waktu pada dataset MIMIC-IV v3.1. Pipeline terdiri dari tiga bagian utama: konstruksi data via BigQuery SQL, pelatihan dan evaluasi model, serta prototipe CDSS berbasis Streamlit.

## Struktur Repositori

```
sepsis/
├── pipeline_query/        — query SQL BigQuery (M0–M8)
├── pipeline_model/        — notebook pelatihan dan evaluasi model
├── cdss_apps/             — prototipe aplikasi CDSS
└── documentation/         — flowchart, screenshots, dan video demo
```

## Prasyarat

- Python 3.10+
- Akses MIMIC-IV v3.1 via Google BigQuery (credentialed access dari [PhysioNet](https://physionet.org/content/mimiciv/))
- Google Cloud project dengan izin `bigquery.dataViewer` pada `physionet-data`

## Pipeline Data

Query SQL dijalankan secara berurutan di Google BigQuery. Lihat [`pipeline_query/README.md`](pipeline_query/README.md) untuk detail.

## Pipeline Model

Pelatihan dan evaluasi model dijalankan di Google Colab (GPU T4). Lihat [`pipeline_model/README.md`](pipeline_model/README.md) untuk detail.

**Hasil evaluasi (test set):**

| Model | AUROC | AUPRC | PLR | FAR | TS-CUS |
|---|---|---|---|---|---|
| **TCN** | 0.8675 | 0.6941 | **0.8797** | 0.2793 | **0.7763** |
| GRU | 0.8762 | 0.7022 | 0.8101 | 0.2086 | 0.7721 |
| Transformer | 0.8824 | 0.7138 | 0.8165 | 0.2439 | 0.7675 |

Model terbaik: **TCN** (TS-CUS tertinggi, threshold 0.60).

## Aplikasi CDSS

Prototipe *Clinical Decision Support System* berbasis Streamlit. Lihat [`cdss_apps/README.md`](cdss_apps/README.md) untuk detail dan cara menjalankan.

## Akses Data

Dataset MIMIC-IV memerlukan sertifikasi CITI Program dan *credentialed access* melalui [PhysioNet](https://physionet.org/content/mimiciv/). Repositori ini tidak menyertakan data apapun.
