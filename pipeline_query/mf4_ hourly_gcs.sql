-- ============================================================
-- mf4_hourly_gcs.sql
-- mengambil nilai GCS per jam untuk setiap ICU stay
-- satu baris = satu ICU stay pada satu window waktu (1 jam)
-- ============================================================

-- Nilai yang digunakan adalah GCS terakhir yang tersedia di dalam setiap window

-- ARRAY_AGG(... ORDER BY charttime DESC LIMIT 1) mengambil pengukuran terakhir.

-- IGNORE NULLS melewati nilai NULL.
-- Jika tidak ada pengukuran pada window tersebut,
-- hasilnya menjadi NULL.

-- Menggunakan GCS total saja.
-- Komponen eye, verbal, dan motor tidak digunakan karena skor total sudah mewakili ketiga komponen tersebut.

--GCS adalah pengukuran selama ICU stay, sehingga join menggunakan stay_id

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_gcs`
CLUSTER BY stay_id, hr
AS

SELECT
  b.stay_id,
  b.hr,

  -- jika tidak ada pengukuran pada window ini, nilai akan tetap NULL.
  ARRAY_AGG(
    g.gcs
    IGNORE NULLS
    ORDER BY g.charttime DESC
    LIMIT 1
  )[SAFE_OFFSET(0)] AS gcs

FROM
  `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b

LEFT JOIN
  `physionet-data.mimiciv_3_1_derived.gcs` g
  ON  g.stay_id = b.stay_id
  AND g.charttime >  b.starttime
  AND g.charttime <= b.endtime

GROUP BY
  b.stay_id,
  b.hr;
