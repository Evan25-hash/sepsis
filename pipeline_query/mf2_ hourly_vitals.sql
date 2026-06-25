-- ============================================================
-- M2: HOURLY VITALS
-- Dataset: MIMIC-IV v3.1
--
-- Agregasi: LAST NON-NULL VALUE per kolom per jam
--   Bashiri et al. (2022, JAMIA) menggunakan strategi last value
--   untuk agregasi time-series ICU pada tugas prediksi infeksi.
--   Untuk source table multi-column (derived.vitalsign), agregasi
--   dilakukan per-kolom dengan ARRAY_AGG IGNORE NULLS untuk
--   mempertahankan measurement individual yang valid. Strategi
--   per-row last-value drop measurement valid ketika row last
--   charttime punya NULL di kolom tersebut sementara row earlier
--   punya nilai.
--
-- Window: (starttime, endtime] — LEFT OPEN, RIGHT CLOSED
--   Identik dengan MIMIC-Code sofa.sql (Johnson et al., 2023)
--
-- Catatan tentang sbp/dbp/map di derived.vitalsign:
--   Kolom sbp/dbp/mbp adalah AVG semua itemid yang masuk dalam
--   satu charttime, mencakup invasive (arterial line: 220050/
--   220051/220052, 225309/225310/225312) dan non-invasive (cuff:
--   220179/220180/220181) sekaligus. Tidak ada kolom
--   invasive-only — pada pasien tanpa arterial line, sbp == sbp_ni.
--
-- Kolom output:
--   heart_rate, sbp, dbp, map    — vital signs utama
--   resp_rate, temperature, spo2 — vital signs lain
--   glucose_poc                  — glucose point-of-care
-- ============================================================

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
FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
LEFT JOIN `physionet-data.mimiciv_3_1_derived.vitalsign` v
  ON  v.stay_id   =  b.stay_id
  AND v.charttime >  b.starttime
  AND v.charttime <= b.endtime
GROUP BY b.stay_id, b.hr;
