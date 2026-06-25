# Prediksi Dini Syok Septik pada Pasien Sepsis di ICU Menggunakan Model *Deep Learning* *Time-Series*

Repositori ini berisi seluruh artefak teknis dari penelitian prediksi dini syok septik berbasis *deep learning* pada dataset MIMIC-IV v3.1. Pipeline dibagi menjadi tiga bagian utama: konstruksi data via BigQuery SQL, pelatihan dan evaluasi model Python, serta prototipe aplikasi CDSS berbasis Streamlit.

---

## Struktur Repositori

```
sepsis/
├── pipeline_query/       # Query SQL BigQuery (M0–M8)
├── pipeline_model/       # Notebook pelatihan dan evaluasi model
└── cdss_apps/            # Prototipe aplikasi CDSS (Streamlit)
```

---

## 1. Pipeline Data (`pipeline_query/`)

Konstruksi dataset dilakukan secara bertahap menggunakan Google BigQuery pada dataset MIMIC-IV v3.1 (`physionet-data.mimiciv_*`). Output akhir disimpan di project BigQuery `skripsi-sepsis-488003.sepsis_v3`.

### Urutan Eksekusi

Modul harus dijalankan secara berurutan. M2–M7 dapat dijalankan paralel setelah M1 selesai.

```
M0 → M1 → M2–M7 (paralel) → M8
```

| Modul | File | Deskripsi |
|---|---|---|
| M0 | `mf0__cohort.sql` | Seleksi kohort: pasien ICU dewasa dengan Sepsis-3, kunjungan pertama, unit MICU/SICU |
| M1 | `mf1__hourly_backbone.sql` | Grid jam per ICU stay (satu baris per `stay_id × hr`) |
| M2 | `mf2__hourly_vitals.sql` | Tanda vital per jam (SBP, DBP, MAP, dll.) |
| M3 | `mf3__hourly_labs.sql` | Hasil laboratorium per jam (laktat, kreatinin, INR, dll.) |
| M4 | `mf4__hourly_gcs.sql` | Glasgow Coma Scale per jam |
| M5 | `mf5__hourly_urine.sql` | Volume keluaran urin per jam |
| M6 | `mf6__static_features.sql` | Fitur statis per stay (usia, jenis kelamin, berat badan) |
| M7 | `mf7__hourly_vasopressor.sql` | Status vasopressor aktif per jam |
| M8 | `mf8__sepsis_hourly_dataset.sql` | Penggabungan seluruh modul menjadi dataset final |

### Kriteria Kohort

**Inklusi:** usia ≥ 18 tahun, kunjungan ICU pertama, Sepsis-3 terkonfirmasi (SOFA ≥ 2 + suspek infeksi), unit perawatan MICU atau SICU.

**Eksklusi:** syok non-septik (ICD-10: R570, R571, R578, R579; anafilaktik: T782\*, T886\*), status DNR/DNI/CMO, stay dengan nilai permanen *missing* setelah imputasi, dan onset syok < 4 jam dari masuk ICU.

**Kohort final:** 4.626 ICU stay (1.046 syok, 3.580 non-syok) — prevalensi syok 22,6%, total 906.989 baris jam.

### Definisi Label Syok

Label `has_shock` bernilai 1 jika pasien mengalami kondisi berikut secara simultan minimal satu jam selama stay:

```
vasopressor_active == 1  AND  lactate > 2.0 mmol/L  AND  hr >= t_sepsis_onset
```

Label bersifat statis per pasien (*patient-level binary label*). Tidak ada *forward-fill* pada laktat untuk konstruksi label — nilai NaN pada jam tanpa pengukuran dievaluasi sebagai False, menghindari *label leakage*.

---

## 2. Pipeline Model (`pipeline_model/`)

Pelatihan dan evaluasi dilakukan di Google Colab dengan GPU T4. Notebook utama: `skripsi_v4.ipynb`.

### Alur Notebook

| Cell | Tahap | Keterangan |
|---|---|---|
| 1A | Load data | Baca dataset M8 dari BigQuery |
| 2B–2C | Konstruksi label | Buat `has_shock`, `t_shock_onset` |
| 2D | Eksklusi onset dini | Hapus stays dengan onset < 4 jam |
| 3A–3D | Seleksi fitur | Kruskal-Wallis η², *distance correlation*, mRMR *greedy* + BH-FDR → 21 fitur |
| 4B | Imputasi | *Forward-fill* / *backward-fill* per stay; urin menggunakan ffill/bfill |
| 5A | Split & normalisasi | Subject-level stratified 70/15/15; StandardScaler fit pada train saja |
| 5B | Bangun sekuen | *Framing B* (PSP): growing window per pasien, K_SHOCK=20, K_NONSHOCK=15 |
| 6A–6C | Pelatihan | GRU, TCN, Transformer Encoder — hyperparameter identik |
| 7 | Evaluasi test set | Threshold via TS-CUS pada validation set |
| 8 | Analisis *lead-time* | Evaluasi per bucket horizon prediksi |
| 9 | Interpretabilitas | Shapley Value Sampling (Captum) pada 10% data test |

### Fitur Terpilih (21 fitur)

`lactate`, `dbp`, `map`, `sbp`, `creatinine`, `fio2`, `aniongap`, `pt`, `inr`, `baseexcess`, `ph`, `ptt`, `wbc`, `bicarbonate`, `urine_output`, `sodium`, `rdw`, `totalco2`, `platelet`, `bilirubin`, `ast`

### Metrik Evaluasi

Metrik utama: **TS-CUS** (komposit, ditetapkan sebelum eksperimen):

```
TS-CUS = 0.40 × PLR + 0.30 × AUPRC + 0.30 × (1 − FAR)
```

PLR (*Proportion of Late Recognition*) dan FAR (*False Alarm Rate*) dihitung pada level pasien mengikuti evaluasi berbasis alarm (Hyland et al., 2020, *Nature Medicine*).

### Hasil Evaluasi (Test Set)

| Model | AUROC | AUPRC | PLR | FAR | TS-CUS | Threshold |
|---|---|---|---|---|---|---|
| **TCN** | 0.8675 | 0.6941 | **0.8797** | 0.2793 | **0.7763** | 0.60 |
| GRU | 0.8762 | 0.7022 | 0.8101 | 0.2086 | 0.7721 | 0.75 |
| Transformer | 0.8824 | 0.7138 | 0.8165 | 0.2439 | 0.7675 | 0.70 |

Model terbaik: **TCN** (TS-CUS tertinggi). *Checkpoint* tersimpan di `cdss_apps/assets/checkpoints/best_tcn.pt`.

### *Setup* Notebook

```bash
pip install torch pandas numpy scikit-learn captum plotly openpyxl
```

Akses BigQuery memerlukan service account dengan izin `bigquery.dataViewer` pada project `physionet-data` dan `skripsi-sepsis-488003`.

---

## 3. Aplikasi CDSS (`cdss_apps/`)

Prototipe *Clinical Decision Support System* berbasis Streamlit untuk pemantauan risiko syok septik secara per-jam. Mendukung satu pasien maupun beberapa pasien sekaligus melalui unggah file Excel.

### Cara Menjalankan

```bash
cd cdss_apps
pip install -r requirements.txt
streamlit run app.py
```

### Dependensi Utama

| Paket | Versi |
|---|---|
| streamlit | ≥ 1.32.0 |
| torch | ≥ 2.0.0 |
| scikit-learn | 1.6.1 |
| pandas | ≥ 2.0.0 |
| plotly | ≥ 5.18.0 |
| openpyxl | ≥ 3.1.0 |

### Struktur Folder

```
cdss_apps/
├── app.py                     # Entry point Streamlit
├── inference.py               # Inferensi TCN + kategorisasi risiko
├── imputation.py              # Imputasi ffill/bfill per stay
├── validation.py              # Validasi rentang nilai fitur
├── tcn_arch.py                # Definisi arsitektur TCN (PyTorch)
├── generate_template.py       # Generator template Excel
├── requirements.txt
└── assets/
    ├── checkpoints/
    │   ├── best_tcn.pt        # Model TCN terlatih
    │   ├── scaler_21feats.pkl # StandardScaler (fit pada train)
    │   └── feature_cols_final.json
    ├── demos/                 # Data demo bawaan
    └── templates/             # Template Excel untuk unggah data
```

### Format Input

Data pasien diunggah dalam format `.xlsx` dengan kolom wajib: `stay_id`, `hr`, dan 21 kolom fitur. Template dapat diunduh langsung dari sidebar aplikasi. Batas maksimum: **20 pasien per file**.

### Fitur Aplikasi

- Prediksi risiko syok septik per jam dengan *growing window* (mengikuti framing PSP)
- Visualisasi trajektori probabilitas per pasien
- Interpretabilitas berbasis Shapley Value Sampling (Captum) — ditampilkan sebagai persentase kontribusi relatif
- Mode multi-pasien dengan tampilan triase
- Imputasi otomatis nilai kosong (ffill/bfill) sesuai metode pelatihan

---

## Referensi Dataset

Johnson AEW, et al. (2023). MIMIC-IV, a freely accessible electronic health record dataset. *Scientific Data*, 10(1):1. doi:10.1038/s41597-022-01899-x

Akses MIMIC-IV memerlukan sertifikasi CITI Program dan persetujuan PhysioNet credentialed access.
