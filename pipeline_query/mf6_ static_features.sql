-- ============================================================
-- mf6_static_features.sql
-- Mengambil fitur statis untuk setiap ICU stay
-- (1 baris per stay)
-- ============================================================

--fitur
-- age    : usia saat admission
-- gender : 1 = Male, 0 = Female
-- weight : berat badan hari pertama ICU (kg)
-- height : tinggi badan hari pertama ICU (cm)
-- bmi    : dihitung dari weight dan height

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.static_features`
CLUSTER BY stay_id
AS

SELECT
  c.stay_id,

  c.admission_age AS age,

  -- Binary encoding gender.
  CASE
    WHEN c.gender = 'M' THEN 1
    ELSE 0
  END AS gender,

  ROUND(fw.weight, 1) AS weight,
  ROUND(fh.height, 1) AS height,

  -- hitung BMI (Body Mass Index) jika weight dan height tersedia
  CASE
    WHEN fw.weight IS NOT NULL
     AND fh.height IS NOT NULL
     AND fh.height > 0
    THEN ROUND(
      fw.weight / POWER(fh.height / 100.0, 2),
      1
    )
    ELSE NULL
  END AS bmi

FROM `skripsi-sepsis-488003.sepsis_v3.cohort` c

LEFT JOIN `physionet-data.mimiciv_3_1_derived.first_day_weight` fw
  ON c.stay_id = fw.stay_id

LEFT JOIN `physionet-data.mimiciv_3_1_derived.first_day_height` fh
  ON c.stay_id = fh.stay_id;
