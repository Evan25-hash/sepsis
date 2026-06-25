-- ============================================================
-- M3: HOURLY LABS — v7 (FiO2 multi-source fallback)
-- Dataset: MIMIC-IV v3.1
--
-- Agregasi: LAST NON-NULL VALUE per kolom per jam
--   Bashiri et al. (2022, JAMIA) menggunakan strategi last value
--   untuk agregasi time-series ICU pada tugas prediksi infeksi.
--   Untuk source table multi-column (chemistry, complete_blood_count,
--   blood_differential, coagulation, enzyme, bg, inflammation,
--   cardiac_marker), agregasi dilakukan per-kolom dengan ARRAY_AGG
--   IGNORE NULLS untuk mempertahankan measurement individual yang
--   valid. Strategi per-row last-value drop measurement valid
--   ketika row last charttime punya NULL di kolom tersebut
--   sementara row earlier punya nilai.
--
-- Window: (starttime, endtime] — LEFT OPEN, RIGHT CLOSED
--   Identik dengan MIMIC-Code sofa.sql (Johnson et al., 2023)
--
-- Catatan elektrolit overlap chemistry vs bg:
--   bicarbonate, calcium, chloride, glucose, sodium, potassium
--   tersedia di kedua tabel. COALESCE chemistry > bg karena
--   central lab lebih standar dibanding ABG specimen.
--
-- Justifikasi kolom:
--   rdw, mcv      : SHAP top-3 septic shock ML (Hou 2021, Liu 2024)
--   monocytes     : NMLR/MLR signal (Guo 2023, Shi 2024 MIMIC-IV)
--   eosinophils   : eosinopenia marker sepsis (Abidi 2008)
--   basophils     : moderate evidence (Ying 2023 MIMIC-IV)
--   metamyelocytes: immature granulocyte marker stress/infeksi
--   nrbc          : nucleated RBC, marker stres sumsum tulang
--   ld_ldh        : 3 MIMIC-IV studies (Zeng 2025, Lu 2024, Wang 2024)
--   aado2         : Wang 2023 MIMIC-IV n=18,933
--   crp           : inflammatory marker
--   troponin_t    : cardiac injury marker
--   ntprobnp      : cardiac stress marker
--
-- ────────────────────────────────────────────────────────────
-- v7 PERUBAHAN: FiO2 MULTI-SOURCE FALLBACK
-- ────────────────────────────────────────────────────────────
-- Akar masalah v6: fio2 di-aggregate HANYA dari bg.* (LABEVENTS
--   itemid 50816 + bg.fio2_chartevents yang lookback dari BGA).
--   Pasien yang ventilated tapi tidak punya BGA akan kehilangan
--   fio2 di mf3 meskipun fio2 tercatat di ventilator_setting.
--
-- Audit diagnostic (220 stays via Layer 2 only) konfirmasi:
--   - mf0 A8 OR-filter sudah benar (Missing ALL sources = 0)
--   - Gap v6 = mf3 v6 tidak include ventilator_setting standalone
--
-- v7 menambahkan vent CTE (ventilator_setting.fio2) sebagai
--   sumber INDEPENDENT, lalu COALESCE dalam dua layer:
--
--   Layer 1: bg.fio2 + bg.fio2_chartevents
--            (paling spesifik — diukur saat/dekat BGA sampling,
--             4,822/5,042 stays = 95.6%)
--   Layer 2: ventilator_setting.fio2
--            (CHARTEVENTS 223835 standalone — untuk 220 stays
--             ventilated tanpa BGA)
--
-- Cohort filter mf0 A8 (TEW3S, Kim et al. 2024) sudah menjamin
--   setiap stay punya ≥1 fio2 measurement di salah satu sumber.
--   Audit menunjukkan 0 stays missing fio2 di ALL sources, sehingga
--   COALESCE Layer 1 + Layer 2 akan menjamin stay_cov 100% post v7.
--
-- Hourly gaps (jam tanpa measurement) di-handle di Cell 4B pipeline
--   Python via ffill/bfill — propagate measured value lebih akurat
--   secara klinis dibanding static default.
--
-- Coverage dan redundansi dianalisis di Python (mRMR pipeline)
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.hourly_labs`
CLUSTER BY stay_id, hr
AS

WITH

-- ── Chemistry ──
chem AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(ch.albumin,       1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS albumin,
    ARRAY_AGG(ROUND(ch.globulin,      1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS globulin,
    ARRAY_AGG(ROUND(ch.total_protein, 1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS total_protein,
    ARRAY_AGG(ROUND(ch.aniongap,      1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS aniongap,
    ARRAY_AGG(ROUND(ch.bun,           1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bun,
    ARRAY_AGG(ROUND(ch.creatinine,    2) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS creatinine,
    ARRAY_AGG(ROUND(ch.bicarbonate,   1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bicarbonate_chem,
    ARRAY_AGG(ROUND(ch.calcium,       1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS calcium_chem,
    ARRAY_AGG(ROUND(ch.chloride,      1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS chloride_chem,
    ARRAY_AGG(ROUND(ch.glucose,       1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS glucose_chem,
    ARRAY_AGG(ROUND(ch.sodium,        1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS sodium_chem,
    ARRAY_AGG(ROUND(ch.potassium,     1) IGNORE NULLS ORDER BY ch.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS potassium_chem
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.chemistry` ch
    ON  ch.hadm_id   =  b.hadm_id
    AND ch.charttime >  b.starttime
    AND ch.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Complete Blood Count ──
cbc AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(cb.hematocrit, 1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS hematocrit,
    ARRAY_AGG(ROUND(cb.hemoglobin, 1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS hemoglobin,
    ARRAY_AGG(ROUND(cb.platelet,   0) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS platelet,
    ARRAY_AGG(ROUND(cb.wbc,        1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS wbc,
    ARRAY_AGG(ROUND(cb.rdw,        1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS rdw,
    ARRAY_AGG(ROUND(cb.rdwsd,      1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS rdwsd,
    ARRAY_AGG(ROUND(cb.mcv,        1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS mcv,
    ARRAY_AGG(ROUND(cb.mch,        1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS mch,
    ARRAY_AGG(ROUND(cb.mchc,       1) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS mchc,
    ARRAY_AGG(ROUND(cb.rbc,        2) IGNORE NULLS ORDER BY cb.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS rbc
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.complete_blood_count` cb
    ON  cb.hadm_id   =  b.hadm_id
    AND cb.charttime >  b.starttime
    AND cb.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Blood Differential ──
diff AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(bd.neutrophils_abs,       1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS neutrophils,
    ARRAY_AGG(ROUND(bd.lymphocytes_abs,       1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS lymphocytes,
    ARRAY_AGG(ROUND(bd.monocytes_abs,         1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS monocytes,
    ARRAY_AGG(ROUND(bd.eosinophils_abs,       1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS eosinophils,
    ARRAY_AGG(ROUND(bd.basophils_abs,         1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS basophils,
    ARRAY_AGG(ROUND(bd.bands,                 1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bands,
    ARRAY_AGG(ROUND(bd.immature_granulocytes, 1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS immature_granulocytes,
    ARRAY_AGG(ROUND(bd.atypical_lymphocytes,  1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS atypical_lymphocytes,
    ARRAY_AGG(ROUND(bd.metamyelocytes,        1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS metamyelocytes,
    ARRAY_AGG(ROUND(bd.nrbc,                  1) IGNORE NULLS ORDER BY bd.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS nrbc
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.blood_differential` bd
    ON  bd.hadm_id   =  b.hadm_id
    AND bd.charttime >  b.starttime
    AND bd.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Coagulation ──
coag AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(cg.inr,        1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS inr,
    ARRAY_AGG(ROUND(cg.pt,         1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS pt,
    ARRAY_AGG(ROUND(cg.ptt,        1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ptt,
    ARRAY_AGG(ROUND(cg.d_dimer,    1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS d_dimer,
    ARRAY_AGG(ROUND(cg.fibrinogen, 1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS fibrinogen,
    ARRAY_AGG(ROUND(cg.thrombin,   1) IGNORE NULLS ORDER BY cg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS thrombin
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.coagulation` cg
    ON  cg.hadm_id   =  b.hadm_id
    AND cg.charttime >  b.starttime
    AND cg.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Enzymes ──
enz AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(en.ast,                1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ast,
    ARRAY_AGG(ROUND(en.alt,                1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS alt,
    ARRAY_AGG(ROUND(en.bilirubin_total,    1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bilirubin,
    ARRAY_AGG(ROUND(en.bilirubin_direct,   1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bilirubin_direct,
    ARRAY_AGG(ROUND(en.bilirubin_indirect, 1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bilirubin_indirect,
    ARRAY_AGG(ROUND(en.ld_ldh,             1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ld_ldh,
    ARRAY_AGG(ROUND(en.alp,                1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS alp,
    ARRAY_AGG(ROUND(en.ggt,                1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ggt,
    ARRAY_AGG(ROUND(en.amylase,            1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS amylase,
    ARRAY_AGG(ROUND(en.ck_cpk,             1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ck_cpk,
    ARRAY_AGG(ROUND(en.ck_mb,              1) IGNORE NULLS ORDER BY en.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ck_mb_enzyme
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.enzyme` en
    ON  en.hadm_id   =  b.hadm_id
    AND en.charttime >  b.starttime
    AND en.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── ABG / Blood Gas (sumber Layer 1 fio2) ──
abg AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(bg.lactate,                             1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS lactate,
    ARRAY_AGG(ROUND(bg.ph,                                  2) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ph,
    ARRAY_AGG(ROUND(bg.pco2,                                1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS pco2,
    ARRAY_AGG(ROUND(bg.po2,                                 1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS po2,
    ARRAY_AGG(ROUND(bg.so2,                                 1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS so2,
    ARRAY_AGG(ROUND(bg.baseexcess,                          1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS baseexcess,
    ARRAY_AGG(ROUND(bg.pao2fio2ratio,                       1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS pf_ratio,
    -- fio2 Layer 1: dari bg (BGA charttime). COALESCE(bg.fio2,
    -- bg.fio2_chartevents) mengikuti pola MIT-LCP sofa.sql.
    ARRAY_AGG(ROUND(COALESCE(bg.fio2, bg.fio2_chartevents), 1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS fio2_bg,
    ARRAY_AGG(ROUND(bg.totalco2,                            1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS totalco2,
    ARRAY_AGG(ROUND(bg.aado2,                               1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS aado2,
    -- Elektrolit overlap dengan chemistry (untuk COALESCE di bawah)
    ARRAY_AGG(ROUND(bg.bicarbonate, 1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS bicarbonate_bg,
    ARRAY_AGG(ROUND(bg.calcium,     1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS calcium_bg,
    ARRAY_AGG(ROUND(bg.chloride,    1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS chloride_bg,
    ARRAY_AGG(ROUND(bg.glucose,     1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS glucose_bg,
    ARRAY_AGG(ROUND(bg.sodium,      1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS sodium_bg,
    ARRAY_AGG(ROUND(bg.potassium,   1) IGNORE NULLS ORDER BY bg.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS potassium_bg
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.bg` bg
    ON  bg.hadm_id   =  b.hadm_id
    AND bg.charttime >  b.starttime
    AND bg.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Ventilator Setting (sumber Layer 2 fio2) ──
-- Independent dari bg table — capture ventilated patients tanpa BGA
-- itemid 223835 di chartevents, sudah di-clean MIT-LCP (range 20-100)
vent AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(vs.fio2, 1) IGNORE NULLS ORDER BY vs.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS fio2_vent
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.ventilator_setting` vs
    ON  vs.stay_id   =  b.stay_id
    AND vs.charttime >  b.starttime
    AND vs.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Inflammation ──
inflam AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(inf.crp, 1) IGNORE NULLS ORDER BY inf.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS crp
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.inflammation` inf
    ON  inf.hadm_id   =  b.hadm_id
    AND inf.charttime >  b.starttime
    AND inf.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
),

-- ── Cardiac Marker ──
cardiac AS (
  SELECT
    b.stay_id, b.hr,
    ARRAY_AGG(ROUND(cm.troponin_t, 3) IGNORE NULLS ORDER BY cm.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS troponin_t,
    ARRAY_AGG(ROUND(cm.ntprobnp,   1) IGNORE NULLS ORDER BY cm.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ntprobnp,
    ARRAY_AGG(ROUND(cm.ck_mb,      1) IGNORE NULLS ORDER BY cm.charttime DESC LIMIT 1)[SAFE_OFFSET(0)] AS ck_mb_cardiac
  FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
  LEFT JOIN `physionet-data.mimiciv_3_1_derived.cardiac_marker` cm
    ON  cm.hadm_id   =  b.hadm_id
    AND cm.charttime >  b.starttime
    AND cm.charttime <= b.endtime
  GROUP BY b.stay_id, b.hr
)

-- ── Final Assembly ──
SELECT
  b.stay_id,
  b.hr,

  -- Chemistry
  ch.albumin,
  ch.globulin,
  ch.total_protein,
  ch.aniongap,
  ch.bun,
  ch.creatinine,
  COALESCE(ch.bicarbonate_chem, ab.bicarbonate_bg) AS bicarbonate,
  COALESCE(ch.calcium_chem,     ab.calcium_bg)     AS calcium,
  COALESCE(ch.chloride_chem,    ab.chloride_bg)    AS chloride,
  COALESCE(ch.glucose_chem,     ab.glucose_bg)     AS glucose,
  COALESCE(ch.sodium_chem,      ab.sodium_bg)      AS sodium,
  COALESCE(ch.potassium_chem,   ab.potassium_bg)   AS potassium,

  -- CBC
  cb.hematocrit,
  cb.hemoglobin,
  cb.platelet,
  cb.wbc,
  cb.rdw,
  cb.rdwsd,
  cb.mcv,
  cb.mch,
  cb.mchc,
  cb.rbc,

  -- Differential (absolute counts)
  df.neutrophils,
  df.lymphocytes,
  df.monocytes,
  df.eosinophils,
  df.basophils,
  df.bands,
  df.immature_granulocytes,
  df.atypical_lymphocytes,
  df.metamyelocytes,
  df.nrbc,

  -- Coagulation
  cg.inr,
  cg.pt,
  cg.ptt,
  cg.d_dimer,
  cg.fibrinogen,
  cg.thrombin,

  -- Enzymes
  en.ast,
  en.alt,
  en.bilirubin,
  en.bilirubin_direct,
  en.bilirubin_indirect,
  en.ld_ldh,
  en.alp,
  en.ggt,
  en.amylase,
  en.ck_cpk,
  -- ck_mb: COALESCE cardiac_marker (lebih spesifik) > enzyme
  COALESCE(car.ck_mb_cardiac, en.ck_mb_enzyme) AS ck_mb,

  -- ABG
  ab.lactate,
  ab.ph,
  ab.pco2,
  ab.po2,
  ab.so2,
  ab.baseexcess,
  ab.pf_ratio,

  -- ── fio2 multi-source COALESCE (v7) ──
  -- Layer 1 (paling spesifik): ab.fio2_bg     (saat/dekat BGA)
  -- Layer 2:                   vt.fio2_vent   (ventilator standalone)
  --
  -- mf0 A8 menjamin setiap stay punya ≥1 fio2 di salah satu Layer
  -- (audit: 0 stays missing ALL sources). Hourly NaN di-handle Cell 4B.
  COALESCE(ab.fio2_bg, vt.fio2_vent) AS fio2,

  ab.totalco2,
  ab.aado2,

  -- Inflammation
  inf.crp,

  -- Cardiac Marker
  car.troponin_t,
  car.ntprobnp

FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
LEFT JOIN chem    ch  ON b.stay_id = ch.stay_id  AND b.hr = ch.hr
LEFT JOIN cbc     cb  ON b.stay_id = cb.stay_id  AND b.hr = cb.hr
LEFT JOIN diff    df  ON b.stay_id = df.stay_id  AND b.hr = df.hr
LEFT JOIN coag    cg  ON b.stay_id = cg.stay_id  AND b.hr = cg.hr
LEFT JOIN enz     en  ON b.stay_id = en.stay_id  AND b.hr = en.hr
LEFT JOIN abg     ab  ON b.stay_id = ab.stay_id  AND b.hr = ab.hr
LEFT JOIN vent    vt  ON b.stay_id = vt.stay_id  AND b.hr = vt.hr
LEFT JOIN inflam  inf ON b.stay_id = inf.stay_id AND b.hr = inf.hr
LEFT JOIN cardiac car ON b.stay_id = car.stay_id AND b.hr = car.hr;
