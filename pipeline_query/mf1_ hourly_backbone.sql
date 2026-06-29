-- ============================================================
-- mf1_ hourly_backbone.sql (Grid Jam per Stay)
-- ============================================================
CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_backbone`
CLUSTER BY stay_id, hr
AS

WITH

-- guard dulu sebelum GENERATE_ARRAY
-- kalau durasi stay <= 0 menit, GENERATE_ARRAY(0, negative)
-- hasilnya empty array → row hilang diam-diam waktu UNNEST
-- sejak minimum LOS dihapus dari M0, ini bisa kejadian
cohort_guarded AS (
  SELECT
    stay_id,
    subject_id,
    hadm_id,
    icu_intime,
    effective_outtime,
    t_sepsis_hr AS _label_t_sepsis_hr  -- jangan pakai ini sebagai fitur model
  FROM
    `skripsi-sepsis-488003.sepsis_v3.cohort`
  WHERE 
    DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) > 0
),

-- generate index jam per stay, mulai dari hr=0
-- hr=0 = jam pertama sejak ICU admission (t0 = icu_intime)
-- FLOOR(LOS_minutes/60) = index jam terakhir yang starttime-nya
-- masih dalam window → partial last hour ikut masuk, zero-length dibuang nanti

-- contoh: LOS=136.3h → hrs=[0..136], last hour sekitar 18 menit
--         LOS=136.0h → hrs=[0..136], last hour 0 menit → kena filter bawah
grid AS (
  SELECT
    *,
    GENERATE_ARRAY(
      0,
      CAST(
        FLOOR(
          DATETIME_DIFF(effective_outtime, icu_intime, MINUTE) / 60.0
        ) AS INT64
      )
    ) AS hrs
  FROM 
    cohort_guarded
),

-- expand ke satu baris per stay_id × hr
-- endtime di-cap ke effective_outtime supaya tidak overshoot discharge/death
expanded AS (
  SELECT
    g.subject_id,
    g.hadm_id,
    g.stay_id,
    hr,
    g.icu_intime,
    g.effective_outtime,
    g._label_t_sepsis_hr,
    DATETIME_ADD(g.icu_intime, INTERVAL hr HOUR)      AS starttime,
    
    LEAST(
      DATETIME_ADD(g.icu_intime, INTERVAL hr + 1 HOUR),
      g.effective_outtime
    )                                                  AS endtime
  FROM 
    grid g
  CROSS JOIN UNNEST(g.hrs) AS hr
)

-- filter ganda: starttime harus sebelum discharge,
-- dan window harus punya durasi > 0 menit
-- (ini yang buang zero-length last hour dari contoh LOS=136.0h di atas)
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
FROM 
  expanded
WHERE 
  starttime < effective_outtime AND 
  DATETIME_DIFF(
    endtime, 
    starttime, MINUTE) > 0;
