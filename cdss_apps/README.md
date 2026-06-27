# Aplikasi CDSS (`cdss_apps/`)

Prototipe *Clinical Decision Support System* untuk pemantauan risiko syok septik per jam pada pasien sepsis di ICU. Dibangun dengan Streamlit, menggunakan model TCN terlatih dengan inferensi berbasis *growing window*.

## Menjalankan Aplikasi

```bash
cd cdss_apps
pip install -r requirements.txt
streamlit run app.py
```

## Struktur File

| File | Deskripsi |
|---|---|
| `app.py` | Entry point Streamlit — UI, routing antar halaman |
| `inference.py` | Inferensi TCN, konstruksi sekuen, kategorisasi risiko |
| `imputation.py` | Imputasi ffill/bfill per stay |
| `validation.py` | Validasi rentang nilai fitur, FEATURE_DISPLAY |
| `tcn_arch.py` | Definisi arsitektur TCN (PyTorch) |
| `generate_template.py` | Generator template Excel untuk input data |
| `requirements.txt` | Dependensi Python |

## Dependensi

| Paket | Versi |
|---|---|
| streamlit | ≥ 1.32.0 |
| torch | ≥ 2.0.0 |
| scikit-learn | 1.6.1 |
| pandas | ≥ 2.0.0 |
| plotly | ≥ 5.18.0 |
| openpyxl | ≥ 3.1.0 |

## Format Input

Data diunggah dalam format `.xlsx` dengan kolom wajib: `stay_id`, `hr`, dan 21 kolom fitur. Template tersedia di sidebar aplikasi atau di `assets/templates/`. Batas maksimum: **20 pasien per file**.

## Kategorisasi Risiko

| Kategori | Rentang Probabilitas |
|---|---|
| Rendah | < 30% |
| Sedang | 30–60% |
| Tinggi | > 60% |

Threshold 60% ditetapkan via optimasi TS-CUS pada validation set (TCN).

## Screenshots

| Halaman | Preview |
|---|---|
| Halaman utama | ![](../documentation/screenshots/01_halaman_utama.png) |
| Unggah data | ![](../documentation/screenshots/02_unggah_data.png) |
| Validasi | ![](../documentation/screenshots/03_validasi.png) |
| Dashboard pasien tunggal | ![](../documentation/screenshots/04_dashboard_single.png) |
| Kondisi pasien | ![](../documentation/screenshots/05_kondisi_pasien.png) |
| Faktor utama (Shapley) | ![](../documentation/screenshots/06_faktor_utama.png) |
| Dashboard multi-pasien | ![](../documentation/screenshots/07_dashboard_multi.png) |
| Triase | ![](../documentation/screenshots/08_triase.png) |

## Video Demo

[![Demo CDSS](../documentation/screenshots/01_halaman_utama.png)](../documentation/video/demo_cdss.mp4)

## Flowchart

![CDSS Flowchart](../documentation/flowchart/cdss_flowchart.png)
