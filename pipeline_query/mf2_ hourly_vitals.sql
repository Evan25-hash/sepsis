-- ============================================================
-- mf2_hourly_vitals.sql
--mengambil tanda vital per jam untuk setiap ICU stay
-- nilai yang digunakan adalah pengukuran terakhir yang tersedia
-- di dalam setiap window 1 jam
-- ============================================================

--jika dalam satu jam ada beberapa pengukuran, gunakan nilai terakhir (charttime paling akhir)

-- ARRAY_AGG(... ORDER BY charttime DESC LIMIT 1) mengambil nilai paling akhir

-- IGNORE NULLS memastikan nilai NULL dilewati
-- jadi jika pengukuran terakhir NULL tetapi sebelumnya ada nilai, nilai sebelumnya tetap digunakan
--
-- SAFE_OFFSET(0) mengambil elemen pertama hasil ARRAY_AGG().
-- jika tidak ada data sama sekali pada window tersebut, hasilnya menjadi NULL (tidak error)

-- *note:
-- pada tabel derived.vitalsign, SBP, DBP, dan MAP sudah merupakan hasil agregasi dari seluruh pengukuran pada charttime yang sama.
-- nilai tsb dpt berasal dari arterial line maupun cuff, sehingga tabel ini tidak membedakan tekanan darah invasif dan non-invasif

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_vitals`

CLUSTER BY stay_id, hr
AS

SELECT
  b.stay_id,
  b.hr,

  ARRAY_AGG(v.heart_rate  IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS heart_rate,
  ARRAY_AGG(v.sbp         IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS sbp,
  ARRAY_AGG(v.dbp         IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS dbp,
  ARRAY_AGG(v.mbp         IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS map,
  ARRAY_AGG(v.resp_rate   IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS resp_rate,
  ARRAY_AGG(v.temperature IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS temperature,
  ARRAY_AGG(v.spo2        IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS spo2,
  ARRAY_AGG(v.glucose     IGNORE NULLS ORDER BY v.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS glucose_poc
FROM
  `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b

LEFT JOIN
  `physionet-data.mimiciv_3_1_derived.vitalsign` v ON  
  v.stay_id = b.stay_id        AND 
  v.charttime >  b.starttime   AND 
  v.charttime <= b.endtime
GROUP BY
  b.stay_id,
  b.hr;
