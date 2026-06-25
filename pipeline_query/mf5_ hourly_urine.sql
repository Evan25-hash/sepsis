-- ============================================================
-- M5: HOURLY URINE
-- Dataset: MIMIC-IV v3.1
--
-- Agregasi: SUM per jam
--   Urine output = total produksi dalam window
--   Berbeda dengan vitals/labs yang pakai last value
--   karena urine adalah cumulative flow, bukan point measurement
--
-- Keputusan desain:
--   1. urine_output (ml) — raw absolute value
--      Konsisten dengan prinsip pure raw features.
--      Tidak dinormalisasi per berat badan karena normalisasi
--      (urine_rate ml/kg/hr) adalah derived feature, bukan raw
--      measurement — konsisten dengan pendekatan M2-M4.
--   2. SUM bukan last value — satu-satunya modul yang pakai SUM.
--      Klinis: urine output = total produksi per jam.
--   3. PENANGANAN IRIGASI GU.
--      Sumber derived.urine_output memberi tanda negatif pada
--      GU Irrigant Volume In (itemid 227488). Maksudnya: irigasi
--      yang dimasukkan ke saluran kemih mengurangi urine output
--      bersih, karena cairan irigasi bukan urin sejati.
--      M5 menjumlahkan seluruh pencatatan dalam satu jam APA
--      ADANYA (nilai negatif diperhitungkan), lalu membatasi
--      total jam ke minimum 0 via GREATEST(SUM(...), 0).
--      Urutan penting: clip SETELAH SUM, bukan sebelum, agar
--      pengurangan irigasi dalam satu jam tetap dihitung. Clip
--      ke 0 dilakukan karena urine output per jam tidak dapat
--      bernilai negatif secara fisik.
--      KETERBATASAN yang diakui:
--        a. Jam yang hanya memuat irigasi dengan net negatif
--           tercatat sebagai 0, tidak terbedakan dari oliguria
--           sejati.
--        b. Bila pencatatan irigasi masuk dan keluar jatuh pada
--           jam berbeda, agregasi per jam tidak dapat
--           menyelaraskannya. Artefak lintas-jam ini tidak
--           dikoreksi.
--      Item irigasi GU hanya relevan pada subset pasien dengan
--      kondisi urologi spesifik; besar pengaruhnya pada cohort
--      diukur terpisah melalui query diagnostik
--      (diagnostik_urine_negatif.sql) dan dilaporkan sebagai
--      keterbatasan minor.
--
-- Sumber: physionet-data.mimiciv_3_1_derived.urine_output
--   Join via stay_id (ICU-specific measurement)
--   Window: (starttime, endtime] — konsisten M2/M3/M4
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_urine`
CLUSTER BY stay_id, hr
AS

WITH urine_agg AS (
  SELECT
    b.stay_id,
    b.hr,
    COUNT(uo.urineoutput)             AS urine_count,
    -- SUM seluruh pencatatan apa adanya (negatif diperhitungkan),
    -- lalu batasi total jam ke minimum 0.
    GREATEST(SUM(uo.urineoutput), 0)  AS urine_sum
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.urine_output` uo
    ON  uo.stay_id   =  b.stay_id
    AND uo.charttime >  b.starttime
    AND uo.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
)

SELECT
  stay_id,
  hr,
  CASE
    WHEN urine_count = 0 THEN NULL  -- tidak ada entry = NULL
    ELSE urine_sum                   -- ada entry = total (termasuk 0 genuine)
  END AS urine_output
FROM urine_agg;
