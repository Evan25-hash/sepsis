# Pipeline Data (`pipeline_query/`)

Konstruksi dataset dilakukan secara bertahap menggunakan Google BigQuery pada MIMIC-IV v3.1 (`physionet-data.mimiciv_*`). Output akhir disimpan di `skripsi-sepsis-488003.sepsis_v3`.

## Urutan Eksekusi

M2–M7 dapat dijalankan paralel setelah M1 selesai.

```
M0 -> M1 -> M2, M3, M4, M5, M6, M7 (paralel) -> M8
```

## Modul

| File | Deskripsi | Output |
|---|---|---|
| `mf0__cohort.sql` | Seleksi kohort ICU sepsis | Daftar `stay_id` yang memenuhi kriteria |
| `mf1__hourly_backbone.sql` | Grid jam per stay | Satu baris per `stay_id × hr` |
| `mf2__hourly_vitals.sql` | Tanda vital per jam | SBP, DBP, MAP, dll. |
| `mf3__hourly_labs.sql` | Hasil laboratorium per jam | Laktat, kreatinin, INR, dll. |
| `mf4__hourly_gcs.sql` | Glasgow Coma Scale per jam | Skor GCS per jam |
| `mf5__hourly_urine.sql` | Volume keluaran urin per jam | mL/jam |
| `mf6__static_features.sql` | Fitur statis per stay | Usia, jenis kelamin, berat badan |
| `mf7__hourly_vasopressor.sql` | Status vasopressor per jam | Flag aktif/tidak aktif |
| `mf8__sepsis_hourly_dataset.sql` | Penggabungan final | Dataset lengkap siap pakai |
