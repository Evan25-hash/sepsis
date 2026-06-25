# ICU Septic Shock Monitor — Prototipe CDSS (v3)

Sistem Pendukung Keputusan untuk Pemantauan Risiko Septic Shock pada pasien ICU.
Skripsi S1 Computer Science · Bina Nusantara University.

> **Peringatan:** Prototipe penelitian. Bukan alat diagnostik klinis. Keputusan medis tetap pada tenaga medis.

## Fitur Utama (v3)

- **Multi-pasien dalam 1 file Excel** — efisien untuk klinisi yang memantau beberapa pasien sekaligus
- **Workflow 4-langkah Polytron-style:** Unggah → Validasi → Tinjau Data → Hasil Prediksi
- **Validasi per-baris dengan pesan error spesifik** sebelum prediksi dijalankan
- **Tinjauan imputasi transparan** — user tahu nilai mana yang diisi otomatis
- **Triage overview screen** untuk multi-pasien — lihat ringkasan semua sekaligus
- **Light theme dengan typography Plus Jakarta Sans** — clean, modern, klinis-friendly
- **Bahasa Indonesia konsisten**, tanpa jargon teknis di UI utama
- **Visualisasi window lead-time** — area abu-abu menandakan akurasi prediksi terbatas
- **Tombol Mulai Ulang** kapan saja untuk reset session

## Cara Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Browser auto-open `http://localhost:8501`.

## Format File Excel

| Kolom | Wajib | Keterangan |
|---|---|---|
| stay_id | Ya | ID pasien (angka atau teks) |
| hr | Ya | Jam ke berapa di ICU (mulai 0, berurutan) |
| lactate | Ya* | Laktat (mmol/L) |
| baseexcess | Ya* | Base Excess (mEq/L) |
| inr | Ya* | INR |
| aniongap | Ya* | Anion Gap (mEq/L) |
| sbp | Ya* | Tekanan Sistolik (mmHg) |
| pt | Ya* | Prothrombin Time (detik) |
| totalco2 | Ya* | Total CO₂ (mEq/L) |
| urine_output | Ya* | Produksi Urin (mL/jam) |
| fio2 | Ya* | FiO₂ (%) |
| bicarbonate | Ya* | Bikarbonat (mEq/L) |
| platelet | Ya* | Trombosit (rb/µL) |
| map | Ya* | Tekanan Rata-rata (mmHg) |
| creatinine | Ya* | Kreatinin (mg/dL) |

*Kolom harus ada, nilainya boleh kosong di sebagian baris (sistem akan mengisi otomatis).
Tapi setiap kolom harus punya minimal 1 nilai pengukuran.

**Batasan:** Maksimum 20 pasien per file.

## Workflow

```
1. UNGGAH DATA
   └── Pilih file Excel atau pilih contoh data

2. VALIDASI
   ├── Sistem cek setiap baris
   ├── Tampilkan baris bermasalah dengan pesan error spesifik
   └── Tombol Lanjutkan aktif jika semua valid

3. TINJAU DATA
   ├── Ringkasan nilai kosong per pasien
   ├── Pratinjau nilai kosong per kolom
   └── Penjelasan cara sistem mengisi nilai kosong

4. HASIL PREDIKSI
   ├── Multi-pasien: triage card overview
   ├── Single pasien: langsung ke dashboard detail
   └── Dashboard: tren risiko + kondisi pasien + faktor utama
```

## Tentang Sistem

Model AI dilatih pada data lebih dari 4,700 pasien ICU dari basis data MIMIC-IV.
Performa terbaik untuk prediksi dalam 6 jam ke depan; akurasi menurun untuk
prediksi window yang lebih jauh.

## Citation

Evan Kurniady. *Prediksi Septic Shock pada Pasien Sepsis ICU Menggunakan Deep Learning Time Series.*
Bina Nusantara University · 2025.
