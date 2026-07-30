-- ============================================================
-- mf7_hourly_vasopressor.sql
-- Menentukan status penggunaan vasopressor per jam
-- ============================================================

-- vasopressor_active:
-- 1 = ada vasopressor aktif pada window ini
-- 0 = tidak ada vasopressor aktif

-- Menggunakan derived.norepinephrine_equivalent_dose (NED), yaitu tabel yang mengonversi berbagai jenis vasopressor ke dosis ekuivalen norepinephrine.

-- Infus dianggap aktif jika overlap dengan window waktu.

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_vasopressor`
CLUSTER BY stay_id, hr
AS

SELECT
  b.stay_id,
  b.hr,

  -- Jika terdapat minimal satu infus vasopressor
  -- pada window ini, beri nilai 1.
  CASE
    WHEN MAX(ned.norepinephrine_equivalent_dose) > 0 THEN 1
    ELSE 0
  END AS vasopressor_active

FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b

LEFT JOIN `physionet-data.mimiciv_3_1_derived.norepinephrine_equivalent_dose` ned
  ON  ned.stay_id   = b.stay_id
  AND ned.starttime <  b.endtime
  AND ned.endtime   >  b.starttime

GROUP BY
  b.stay_id,
  b.hr;
