# Aplikasi CDSS (`cdss_apps/`)

Prototipe *Clinical Decision Support System* untuk pemantauan risiko syok septik per jam pada pasien sepsis di ICU. Dibangun menggunakan Streamlit dengan model **Temporal Convolutional Network (TCN)** dan inferensi berbasis *growing window*.

## Menjalankan Aplikasi

```bash
cd cdss_apps
pip install -r requirements.txt
streamlit run app.py
```

## Struktur File

| File | Deskripsi |
|---|---|
| `app.py` | Entry point Streamlit — UI dan routing antar halaman |
| `inference.py` | Inferensi model TCN, konstruksi sekuen, dan kategorisasi risiko |
| `imputation.py` | Imputasi data menggunakan interpolasi linear, *forward fill*, dan *backward fill* |
| `validation.py` | Validasi nilai fitur, definisi rentang nilai, dan `FEATURE_DISPLAY` |
| `tcn_arch.py` | Implementasi arsitektur TCN menggunakan PyTorch |
| `generate_template.py` | Generator template Excel untuk input data |
| `requirements.txt` | Daftar dependensi Python |

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

Data diunggah dalam format `.xlsx` dengan kolom wajib:

- `stay_id`
- `hr`
- 21 fitur klinis hasil seleksi

Template Excel dapat diunduh melalui sidebar aplikasi atau dari folder `assets/templates/`.

**Batas maksimum:** **20 pasien** per file.

## Validasi Nilai Klinis

Sebelum dilakukan imputasi dan inferensi, seluruh fitur numerik divalidasi menggunakan dua jenis batas nilai:

- **Rentang valid (*physiologically plausible range*)**, digunakan untuk mendeteksi nilai yang kemungkinan merupakan kesalahan pencatatan (*data quality control*) tanpa menghilangkan nilai ekstrem yang masih mungkin dijumpai pada pasien ICU.
- **Rentang normal (*clinical reference range*)**, digunakan sebagai informasi referensi klinis yang ditampilkan kepada pengguna dan bukan sebagai dasar diagnosis.

Rentang normal disusun berdasarkan referensi laboratorium klinis dan referensi *critical care*, sedangkan rentang valid ditetapkan secara konservatif agar hanya mengecualikan nilai yang secara fisiologis tidak masuk akal atau kemungkinan merupakan kesalahan input.

## Kategorisasi Risiko

| Kategori | Rentang Probabilitas |
|---|---|
| Rendah | < 30% |
| Sedang | 30–60% |
| Tinggi | > 60% |

Threshold **60%** diperoleh melalui optimasi **TS-CUS** pada *validation set* model TCN.

## Referensi

1. Bai, S., Kolter, J. Z., & Koltun, V. (2018). *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling*. NeurIPS Workshop. https://arxiv.org/abs/1803.01271

2. Pagana, K. D., Pagana, T. J., & Pagana, T. N. (2021). *Mosby's Diagnostic & Laboratory Test Reference* (15th ed.). Elsevier.

3. National Center for Biotechnology Information. (2024). *Appendix A. Normal Laboratory Values*. In *Clinical Methods*. U.S. National Library of Medicine. https://www.ncbi.nlm.nih.gov/books/NBK613071/

4. Bickley, L. S. (2021). *Bates' Guide to Physical Examination and History Taking* (13th ed.). Wolters Kluwer.

5. Marino, P. L. (2024). *The ICU Book* (5th ed.). Wolters Kluwer.
