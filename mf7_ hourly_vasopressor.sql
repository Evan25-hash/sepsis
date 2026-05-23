-- ============================================================
-- M7: HOURLY VASOPRESSOR
-- Dataset: MIMIC-IV v3.1
--
-- PENTING: Tabel ini HANYA untuk label construction di Python
-- (Cell 2). Kolom vasopressor_active TIDAK masuk ke feature
-- matrix model -- memasukkan vasopressor sebagai fitur saat
-- vasopressor mendefinisikan label adalah circular reasoning
-- (Davis et al., 2024, JAMIA).
--
-- vasopressor_active: 1 jika ada infusion vasopressor aktif
--   dalam window jam, 0 jika tidak ada.
--   Penelitian ini hanya membutuhkan keberadaan vasopressor
--   (bukan besar dosisnya) untuk konstruksi label syok septik,
--   sehingga output disimpan sebagai flag biner. Sumber dosis
--   yang dipakai untuk menentukan keberadaan adalah
--   derived.norepinephrine_equivalent_dose (NED), yang
--   mengagregasi seluruh vasopressor menjadi satu dosis
--   ekuivalen norepinephrine.
--
-- Window join: infusion aktif jika overlap dengan window jam
--   Overlap: ned.starttime < b.endtime AND ned.endtime > b.starttime
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_vasopressor`
CLUSTER BY stay_id, hr
AS

SELECT
  b.stay_id,
  b.hr,
  -- 1 jika ada infusion vasopressor (NED > 0) yang overlap
  -- dengan window jam ini; 0 jika tidak ada infusion.
  -- MAX dipakai agar bila ada >1 baris infusion dalam window,
  -- keberadaan vasopressor tetap terdeteksi.
  CASE
    WHEN MAX(ned.norepinephrine_equivalent_dose) > 0 THEN 1
    ELSE 0
  END AS vasopressor_active
FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
LEFT JOIN `physionet-data.mimiciv_3_1_derived.norepinephrine_equivalent_dose` ned
  ON  ned.stay_id   =  b.stay_id
  AND ned.starttime <  b.endtime
  AND ned.endtime   >  b.starttime
GROUP BY b.stay_id, b.hr;