-- ============================================================
-- mf5_hourly_urine.sql
-- Menghitung urine output per jam untuk setiap ICU stay
-- ============================================================

-- Urine output dijumlahkan (SUM) karena merupakan total volume
-- dalam satu jam.

-- Window waktu: (starttime, endtime]

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_urine`
CLUSTER BY stay_id, hr
AS

WITH urine_agg AS (
  SELECT
    b.stay_id,
    b.hr,

    -- Untuk membedakan tidak ada data dengan urine output = 0.
    COUNT(uo.urineoutput) AS urine_count,

    -- Total urine output dalam satu jam.
    GREATEST(SUM(uo.urineoutput), 0) AS urine_sum

  FROM
    `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN 
    `physionet-data.mimiciv_3_1_derived.urine_output` uo
    ON  uo.stay_id   = b.stay_id
    AND uo.charttime > b.starttime
    AND uo.charttime <= b.endtime
  GROUP BY
    b.stay_id,
    b.hr
)

SELECT
  stay_id,
  hr,
  CASE
    WHEN urine_count = 0 THEN NULL
    ELSE urine_sum
  END AS urine_output
FROM urine_agg;
