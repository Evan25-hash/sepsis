-- ============================================================
-- M1: HOURLY BACKBONE
-- Dataset: MIMIC-IV v3.1
--
-- Keputusan desain:
--   1. ANCHOR: t0 = icu_intime (MIMIC-Extract, Wang et al. 2020)
--   2. HOUR INDEXING: hr=0 untuk jam pertama (MIMIC-Extract)
--   3. LAST-HOUR ROUNDING: FLOOR(LOS_minutes/60)
--      → partial last hour dipertahankan, zero-length dibuang
--   4. WINDOW BOUNDS: (starttime, endtime] LEFT OPEN RIGHT CLOSED
--      identik dengan MIMIC-Code sofa.sql (Johnson et al. 2023)
--   5. ENDTIME CAPPING: LEAST(intime+(hr+1)h, effective_outtime)
--   6. _label_t_sepsis_hr: firewall leakage — BUKAN fitur model
--   7. STORAGE: CLUSTER BY (stay_id, hr)
--   8. FILTER: durasi window > 0 untuk exclude zero-length rows
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_backbone`
CLUSTER BY stay_id, hr
AS

WITH

-- Guard: pastikan semua stays punya durasi positif.
-- GENERATE_ARRAY(0, negative) = empty array → silent row loss
-- via UNNEST. Sejak kriteria minimum LOS dihapus dari M0,
-- cohort dapat memuat stay berdurasi sangat pendek, sehingga
-- guard ini berperan nyata untuk membuang stay berdurasi nol.
cohort_guarded AS (
  SELECT
    stay_id,
    subject_id,
    hadm_id,
    icu_intime,
    effective_outtime,
    t_sepsis_hr AS _label_t_sepsis_hr  -- BUKAN fitur model
  FROM `skripsi-sepsis-488003.sepsis_v3.cohort`
  WHERE DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) > 0
),

grid AS (
  SELECT
    *,
    -- FLOOR(LOS_minutes/60) = index jam terakhir yang
    -- starttime-nya masih di dalam window observasi
    -- Contoh: LOS=136.3h → hrs=[0..136], last hour partial (~18 menit)
    --         LOS=136.0h → hrs=[0..136], last hour zero-length (difilter)
    GENERATE_ARRAY(
      0,
      CAST(
        FLOOR(
          DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) / 60.0
        ) AS INT64
      )
    ) AS hrs
  FROM cohort_guarded
),

expanded AS (
  SELECT
    g.subject_id,
    g.hadm_id,
    g.stay_id,
    hr,
    g.icu_intime,
    g.effective_outtime,
    g._label_t_sepsis_hr,
    DATETIME_ADD(g.icu_intime, INTERVAL hr HOUR) AS starttime,
    -- Cap endtime agar tidak melampaui discharge/death
    LEAST(
      DATETIME_ADD(g.icu_intime, INTERVAL hr + 1 HOUR),
      g.effective_outtime
    )                                             AS endtime
  FROM grid g
  CROSS JOIN UNNEST(g.hrs) AS hr
)

SELECT
  subject_id,
  hadm_id,
  stay_id,
  hr,
  icu_intime,
  effective_outtime,
  _label_t_sepsis_hr,
  starttime,
  endtime

FROM expanded
WHERE starttime < effective_outtime
  AND DATETIME_DIFF(endtime, starttime, MINUTE) > 0;
