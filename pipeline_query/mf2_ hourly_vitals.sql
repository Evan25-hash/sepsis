-- ============================================================
-- mf2_ hourly_vitals.sql (Tanda Vital per Jam)
-- ============================================================

-- agregasi: last non-null value per kolom per jam
-- pakai ARRAY_AGG IGNORE NULLS ORDER BY charttime DESC
-- bukan last-row approach, karena row terakhir dalam jam
-- bisa saja NULL di kolom tertentu padahal row sebelumnya ada nilainya
-- → per-kolom lebih aman

-- soal sbp/dbp/map di derived.vitalsign:
-- kolom ini sudah AVG dari semua itemid yang masuk charttime yang sama,
-- mencakup invasive (arterial line) dan non-invasive (cuff) sekaligus
-- tidak ada pemisahan invasive-only di sini
-- kalau pasien tidak punya arterial line, sbp == sbp_ni (tidak ada bedanya)

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
  `physionet-data.mimiciv_3_1_derived.vitalsign` v 
  ON  v.stay_id   =  b.stay_id
  AND v.charttime >  b.starttime
  AND v.charttime <= b.endtime
GROUP BY
  b.stay_id, b.hr;
