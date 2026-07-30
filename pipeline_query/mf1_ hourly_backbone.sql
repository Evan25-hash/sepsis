-- ============================================================
-- mf1_hourly_backbone.sql
--membuat backbone data per jam untuk setiap rawatan/stay ICU
--satu baris = satu interval waktu (1 jam)
-- ============================================================
CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_backbone`
CLUSTER BY stay_id, hr
AS

WITH

--pastikan hanya ICU stay dengan durasi > 0 menit yang diproses
--jika tidak, GENERATE_ARRAY() akan menghasilkan array kosong sehingga stay tersebut hilang saat UNNEST
cohort_guarded AS (
  SELECT
    stay_id,
    subject_id,
    hadm_id,
    icu_intime,
    effective_outtime,
    t_sepsis_hr AS _label_t_sepsis_hr  --disimpan sebagai label, bukan fitur model
  FROM
    `skripsi-sepsis-488003.sepsis_v3.cohort`
  WHERE
  --DATETIME_DIFF() menghitung selisih waktu antara:
  --   1. effective_outtime = waktu keluar ICU (atau waktu kematian jika lebih dulu)
  --   2. icu_intime = waktu masuk ICU
    DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) > 0
),

--GENERATE_ARRAY() membuat daftar nomor jam dari 0 sampai jam terakhir.
--contoh:
--   LOS = 3,5 jam -> [0,1,2,3]
--   LOS = 5,0 jam -> [0,1,2,3,4,5]

--setiap angka nantinya menjadi satu window waktu.
grid AS (
  SELECT
    *,
    GENERATE_ARRAY(
      0,
      CAST(
        FLOOR(
          DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) / 60.0
        ) AS INT64
      )
    ) AS hrs
  FROM
    cohort_guarded
),

-- UNNEST() mengubah array hrs menjadi beberapa baris.
--
--before:
--   stay_id = 1001
--   hrs = [0,1,2]

--sesudah:
--   stay_id | hr
--   1001    | 0
--   1001    | 1
--   1001    | 2

-- CROSS JOIN memasangkan setiap nilai hr dengan stay yang sama.
-- starttime = awal window
-- endtime = akhir window
-- LEAST() memastikan endtime tidak melewati discharge/death.
expanded AS (
  SELECT
    g.subject_id,
    g.hadm_id,
    g.stay_id,
    hr,
    g.icu_intime,
    g.effective_outtime,
    g._label_t_sepsis_hr,

    DATETIME_ADD(
      g.icu_intime,
      INTERVAL hr HOUR
    ) AS starttime,

    LEAST(
      DATETIME_ADD(
        g.icu_intime,
        INTERVAL hr + 1 HOUR
      ),
      g.effective_outtime
    ) AS endtime

  FROM
    grid g
  CROSS JOIN UNNEST(g.hrs) AS hr
)

--hanya simpan window yang valid.
-- starttime harus sebelum ICU stay berakhir
-- dan durasi window harus lebih dari 0 menit.
SELECT
  subject_id,
  hadm_id,
  stay_id,
  hr,
  icu_intime,
  effective_outtime,
  _label_t_sepsis_hr,
  starttime,
  endtime
FROM
  expanded
WHERE
  starttime < effective_outtime AND
  DATETIME_DIFF(
    endtime,
    starttime,
    MINUTE
  ) > 0;
