-- ============================================================
-- M4: HOURLY GCS
-- Dataset: MIMIC-IV v3.1
--
-- Agregasi: LAST NON-NULL VALUE per kolom per jam
--   Bashiri et al. (2022, JAMIA) menggunakan strategi last value
--   untuk agregasi time-series ICU pada tugas prediksi infeksi.
--   Untuk source table multi-column (derived.gcs), agregasi
--   dilakukan per-kolom dengan ARRAY_AGG IGNORE NULLS untuk
--   mempertahankan measurement individual yang valid.
--
-- Keputusan desain:
--   1. GCS TOTAL saja (bukan 3 komponen terpisah)
--      Tiga komponen GCS (eye, verbal, motor) bersifat
--      aditif terhadap total dan saling berkorelasi tinggi;
--      memakai skor total menghindari multikolinearitas dan
--      konsisten dengan penggunaan GCS total sebagai komponen
--      SOFA (CNS) -- Singer et al., 2016.
--
--   2. gcs_unable tidak diambil
--      Bukan raw measurement, melainkan derived context flag
--      Konsisten dengan prinsip pure raw features
--
--   3. Window: (starttime, endtime] — LEFT OPEN RIGHT CLOSED
--      Identik dengan MIMIC-Code sofa.sql (Johnson et al., 2023)
--
--   4. Join via stay_id (bukan hadm_id)
--      GCS adalah ICU-specific measurement
--
-- Sumber: physionet-data.mimiciv_3_1_derived.gcs
--   Range valid: 3 (worst) – 15 (best/normal)
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_gcs`
CLUSTER BY stay_id, hr
AS

SELECT
  b.stay_id,
  b.hr,
  -- NULL jika tidak ada pengukuran dalam window;
  -- imputasi missing values ditangani di Python (Cell 4B,
  -- mengikuti strategi imputasi yang telah disetujui dosen).
  ARRAY_AGG(g.gcs IGNORE NULLS ORDER BY g.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS gcs
FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
LEFT JOIN `physionet-data.mimiciv_3_1_derived.gcs` g
  ON  g.stay_id   =  b.stay_id
  AND g.charttime >  b.starttime
  AND g.charttime <= b.endtime
GROUP BY b.stay_id, b.hr;
