-- ============================================================
-- M6: STATIC FEATURES
-- Dataset: MIMIC-IV v3.1
--
-- 1 baris per stay — fitur yang tidak berubah sepanjang stay
--
-- Kolom yang diambil:
--   age    : usia saat admission (tahun)
--   gender : 1=Male, 0=Female (binary encoding)
--   weight : berat badan hari pertama ICU (kg)
--   height : tinggi badan hari pertama ICU (cm)
--   bmi    : Body Mass Index = weight / (height/100)^2
--            NULL jika salah satu komponen tidak tersedia
--
-- Catatan weight/height:
--   Diambil dari first_day karena itulah pengukuran dengan
--   coverage paling memadai di MIMIC-IV. height memiliki
--   coverage lebih rendah dibanding weight dan berpotensi
--   tereksklusi pada tahap seleksi fitur di Python (Cell 3B).
--   Nilai dapat bersifat post-resuscitation dan tidak menangkap
--   perubahan fluid status -- diakui sebagai keterbatasan
--   di BAB 4.
--
-- Kolom yang tidak diambil:
--   first_careunit       : homogen MICU/SICU setelah filter M0
--   hospital_expire_flag : outcome variable -- label leakage
--   t_sepsis_hr          : sudah ada di backbone (_label_t_sepsis_hr)
--
-- Sumber: derived.first_day_weight, derived.first_day_height
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.static_features`
CLUSTER BY stay_id
AS

SELECT
  c.stay_id,
  c.admission_age                             AS age,
  CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END AS gender,
  ROUND(fw.weight, 1) AS weight,
  ROUND(fh.height, 1) AS height,
  CASE
    WHEN fw.weight IS NOT NULL
     AND fh.height IS NOT NULL
     AND fh.height > 0
    THEN ROUND(fw.weight / POWER(fh.height / 100.0, 2), 1)
    ELSE NULL
  END AS bmi

FROM `skripsi-sepsis-488003.sepsis_v3.cohort` c

LEFT JOIN `physionet-data.mimiciv_3_1_derived.first_day_weight` fw
  ON c.stay_id = fw.stay_id

LEFT JOIN `physionet-data.mimiciv_3_1_derived.first_day_height` fh
  ON c.stay_id = fh.stay_id;