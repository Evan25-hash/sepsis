-- ============================================================
-- M8: FINAL DATASET ASSEMBLY
-- Dataset: MIMIC-IV v3.1
--
-- Gabungan M1–M7 — TANPA label (dikerjakan Python Cell 2)
-- Python akan tambahkan: has_shock, t_shock_onset, sample_weight
--
-- Kolom output:
--   Identifiers   : stay_id, subject_id, hadm_id, hr
--   Temporal      : starttime, endtime, icu_intime,
--                   effective_outtime
--   Label metadata: _label_t_sepsis_hr (BUKAN fitur model)
--   Vitals    (8) : heart_rate, sbp, dbp, map,
--                   resp_rate, temperature, spo2, glucose_poc
--   Chemistry (12): albumin, globulin, total_protein,
--                   aniongap, bun, creatinine, bicarbonate,
--                   calcium, chloride, glucose, sodium, potassium
--   CBC      (10) : hematocrit, hemoglobin, platelet, wbc,
--                   rdw, rdwsd, mcv, mch, mchc, rbc
--   Diff     (10) : neutrophils, lymphocytes, monocytes,
--                   eosinophils, basophils, bands,
--                   immature_granulocytes, atypical_lymphocytes,
--                   metamyelocytes, nrbc
--   Coagulation(6): inr, pt, ptt, d_dimer, fibrinogen, thrombin
--   Enzymes  (11) : ast, alt, bilirubin, bilirubin_direct,
--                   bilirubin_indirect, ld_ldh, alp, ggt,
--                   amylase, ck_cpk, ck_mb
--   ABG      (10) : lactate, ph, pco2, po2, so2, baseexcess,
--                   pf_ratio, fio2, totalco2, aado2
--   Inflam    (1) : crp
--   Cardiac   (2) : troponin_t, ntprobnp
--   GCS       (1) : gcs
--   Urine     (1) : urine_output
--   Static    (5) : age, gender, weight, height, bmi
--   Vasopressor   : vasopressor_active
--                   (HANYA untuk Python labeling —
--                    TIDAK masuk feature matrix model)
--
-- Fitur final ditentukan setelah coverage filter di Python
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.sepsis_hourly_dataset`
CLUSTER BY stay_id, hr
AS

SELECT
  -- ── Identifiers ──
  b.stay_id,
  b.subject_id,
  b.hadm_id,
  b.hr,

  -- ── Temporal metadata ──
  b.starttime,
  b.endtime,
  b.icu_intime,
  b.effective_outtime,

  -- ── Label metadata (BUKAN fitur model) ──
  b._label_t_sepsis_hr,

  -- ── Vital signs ──
  -- sbp/dbp/map dari derived.vitalsign = AVG semua sumber
  -- (invasive + non-invasive); lihat catatan di M2
  vt.heart_rate,
  vt.sbp,
  vt.dbp,
  vt.map,
  vt.resp_rate,
  vt.temperature,
  vt.spo2,
  vt.glucose_poc,

  -- ── Chemistry ──
  lb.albumin,
  lb.globulin,
  lb.total_protein,
  lb.aniongap,
  lb.bun,
  lb.creatinine,
  lb.bicarbonate,
  lb.calcium,
  lb.chloride,
  -- Glucose: COALESCE chemistry > bg > poc (lihat M3 + M8)
  COALESCE(lb.glucose, vt.glucose_poc) AS glucose,
  lb.sodium,
  lb.potassium,

  -- ── CBC ──
  lb.hematocrit,
  lb.hemoglobin,
  lb.platelet,
  lb.wbc,
  lb.rdw,
  lb.rdwsd,
  lb.mcv,
  lb.mch,
  lb.mchc,
  lb.rbc,

  -- ── Blood Differential ──
  lb.neutrophils,
  lb.lymphocytes,
  lb.monocytes,
  lb.eosinophils,
  lb.basophils,
  lb.bands,
  lb.immature_granulocytes,
  lb.atypical_lymphocytes,
  lb.metamyelocytes,
  lb.nrbc,

  -- ── Coagulation ──
  lb.inr,
  lb.pt,
  lb.ptt,
  lb.d_dimer,
  lb.fibrinogen,
  lb.thrombin,

  -- ── Enzymes ──
  lb.ast,
  lb.alt,
  lb.bilirubin,
  lb.bilirubin_direct,
  lb.bilirubin_indirect,
  lb.ld_ldh,
  lb.alp,
  lb.ggt,
  lb.amylase,
  lb.ck_cpk,
  lb.ck_mb,

  -- ── ABG ──
  lb.lactate,
  lb.ph,
  lb.pco2,
  lb.po2,
  lb.so2,
  lb.baseexcess,
  lb.pf_ratio,
  lb.fio2,
  lb.totalco2,
  lb.aado2,

  -- ── Inflammation ──
  lb.crp,

  -- ── Cardiac Marker ──
  lb.troponin_t,
  lb.ntprobnp,

  -- ── GCS ──
  gc.gcs,

  -- ── Urine ──
  ur.urine_output,

  -- ── Static features ──
  sf.age,
  sf.gender,
  sf.weight,
  sf.height,
  sf.bmi,

  -- ── Vasopressor (HANYA untuk Python labeling) ──
  -- TIDAK masuk feature matrix — circular reasoning
  -- (Davis et al., 2024, JAMIA)
  vp.vasopressor_active

FROM `skripsi-sepsis-488003.sepsis_v3.hourly_backbone` b
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.hourly_vitals`      vt
  ON b.stay_id = vt.stay_id AND b.hr = vt.hr
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.hourly_labs`        lb
  ON b.stay_id = lb.stay_id AND b.hr = lb.hr
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.hourly_gcs`         gc
  ON b.stay_id = gc.stay_id AND b.hr = gc.hr
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.hourly_urine`       ur
  ON b.stay_id = ur.stay_id AND b.hr = ur.hr
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.static_features`    sf
  ON b.stay_id = sf.stay_id
LEFT JOIN `skripsi-sepsis-488003.sepsis_v3.hourly_vasopressor` vp
  ON b.stay_id = vp.stay_id AND b.hr = vp.hr;