-- ============================================================
-- mf0_ cohort.sql (Seleksi Kohort)
-- ============================================================
CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.cohort` AS

WITH

-- eksklusi dulu sebelum join besar
  
-- E1: buang pasien yang punya diagnosis shock NON-septic
-- masalahnya: kardiogenik/hipovolemik/anafilaktik punya pola
-- MAP rendah + vasopressor + laktat tinggi yang mirip banget
-- sama septic shock → noise di label

-- yang penting: septic shock (R65.21 / ICD-9 78552) tidak ada di list ini, jadi pasien syok septik aman, tidak ikut kebuang

-- ICD-10: R570 cardiogenic, R571 hypovolemic,
--         R578 other (neurogenik dll), R579 unspecified
--         T782* dan T886* = anaphylactic (regex biar catch semua subtype)
-- ICD-9:  78550/78551/78559 = unspecified/cardiogenic/other
--         9950/9951/9952 = anaphylactic (NOS/food/drug)
dx_other_shock AS (
  SELECT 
    DISTINCT hadm_id
  FROM 
    `physionet-data.mimiciv_3_1_hosp.diagnoses_icd`
  WHERE
    (icd_version = 10 AND icd_code IN ('R570', 'R571', 'R578', 'R579'))  OR
    (icd_version = 9  AND icd_code IN ('78550', '78551', '78559'))       OR 
    (icd_version = 10 AND REGEXP_CONTAINS(icd_code, r'^T782'))           OR 
    (icd_version = 10 AND REGEXP_CONTAINS(icd_code, r'^T886'))           OR 
    (icd_version = 9  AND icd_code IN ('9950', '9951', '9952'))
),

-- E2: buang pasien DNR/DNI/CMO
-- kalau pasien punya treatment limitation, vasopressor
-- mungkin tidak diberikan bukan karena tidak perlu,
-- tapi karena keputusan klinis, label syok septik nantinya jadi tidak valid

-- itemid 223758 = "Code Status" di chartevents
code_status_excl AS (
  SELECT 
    DISTINCT stay_id
  FROM 
    `physionet-data.mimiciv_3_1_icu.chartevents`
  WHERE 
    itemid = 223758               AND 
    value IN (
      'DNR (do not resuscitate)',
      'DNI (do not intubate)',
      'DNR / DNI',
      'Comfort measures only'
    )
),

-- join utama: ambil semua pasien sepsis dewasa, ICU pertama, MICU/SICU

-- t_sepsis_hr: jam onset sepsis relatif ke ICU admission
-- pakai GREATEST(suspected_infection_time, sofa_time) karena
-- Sepsis-3 butuh KEDUA kriteria terpenuhi bersamaan
-- COALESCE untuk handle edge case salah satu NULL

-- effective_outtime = LEAST(icu_outtime, deathtime)
-- dipakai sebagai batas akhir window di availability filter bawah
base AS (
  SELECT
    ic.subject_id,
    ic.hadm_id,
    ic.stay_id,
    ic.gender,
    ic.admission_age,
    ic.icu_intime,
    ic.icu_outtime,
    icu.first_careunit,

    DATETIME_DIFF(
      GREATEST(
        COALESCE(s3.suspected_infection_time, s3.sofa_time),
        COALESCE(s3.sofa_time, s3.suspected_infection_time)
      ),
      ic.icu_intime, HOUR
    ) AS t_sepsis_hr,

    LEAST(ic.icu_outtime, COALESCE(ad.deathtime, ic.icu_outtime))
      AS effective_outtime

  FROM
    `physionet-data.mimiciv_3_1_derived.icustay_detail` ic
  INNER JOIN 
    `physionet-data.mimiciv_3_1_icu.icustays` icu 
    ON  ic.stay_id = icu.stay_id

  -- INNER JOIN ke sepsis3 + filter sepsis3=TRUE
  -- tanpa ini, pasien yang cuma memenuhi salah satu kriteria
  -- (SOFA >= 2 tapi belum ada suspek infeksi, atau sebaliknya)
  -- bisa ikut masuk
  INNER JOIN 
    `physionet-data.mimiciv_3_1_derived.sepsis3` s3 
    ON  ic.stay_id = s3.stay_id AND 
        s3.sepsis3 = TRUE

  LEFT JOIN `physionet-data.mimiciv_3_1_hosp.admissions` ad
    ON ic.hadm_id = ad.hadm_id

  WHERE
    ic.admission_age >= 18                                      AND
    ic.first_icu_stay = TRUE                                    AND
    icu.first_careunit IN (
      'Medical Intensive Care Unit (MICU)',
      'Surgical Intensive Care Unit (SICU)',
      'Medical/Surgical Intensive Care Unit (MICU/SICU)'
    )                                                           AND
    ic.hadm_id NOT IN (SELECT hadm_id FROM dx_other_shock)      AND 
    ic.stay_id NOT IN (SELECT stay_id FROM code_status_excl)
),

-- availability filter: pastikan setiap pasien punya minimal 1 pengukuran untuk tiap komponen SOFA selama stay-nya

-- window sama seperti M1-M8: charttime > icu_intime (left open)
-- dan charttime <= effective_outtime (right closed)
cohort_final AS (
  SELECT 
    b.*
  FROM 
    base b
  
  WHERE
    -- A1-A2: SBP + DBP, keduanya wajib ada (SOFA cardiovascular)
    EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.vitalsign` v
      WHERE v.stay_id = b.stay_id AND v.sbp IS NOT NULL
        AND v.charttime > b.icu_intime AND v.charttime <= b.effective_outtime
    )
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.vitalsign` v
      WHERE v.stay_id = b.stay_id AND v.dbp IS NOT NULL
        AND v.charttime > b.icu_intime AND v.charttime <= b.effective_outtime
    )

    -- A3: GCS (SOFA CNS)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.gcs` g
      WHERE g.stay_id = b.stay_id AND g.gcs IS NOT NULL
        AND g.charttime > b.icu_intime AND g.charttime <= b.effective_outtime
    )
    -- A4-A6: lab SOFA — creatinine (renal), bilirubin (hepatic), platelet (coagulation)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.chemistry` ch
      WHERE ch.hadm_id = b.hadm_id AND ch.creatinine IS NOT NULL
        AND ch.charttime > b.icu_intime AND ch.charttime <= b.effective_outtime
    )
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.enzyme` en
      WHERE en.hadm_id = b.hadm_id AND en.bilirubin_total IS NOT NULL
        AND en.charttime > b.icu_intime AND en.charttime <= b.effective_outtime
    )
    
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.complete_blood_count` cbc
      WHERE cbc.hadm_id = b.hadm_id AND cbc.platelet IS NOT NULL
        AND cbc.charttime > b.icu_intime AND cbc.charttime <= b.effective_outtime
    )
    -- A7-A8: PaO2 + FiO2 (SOFA respiratory)
    -- FiO2 pakai OR karena bisa dari bg atau ventilator_setting
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.bg` bg
      WHERE bg.hadm_id = b.hadm_id AND bg.po2 IS NOT NULL
        AND bg.charttime > b.icu_intime AND bg.charttime <= b.effective_outtime
    )
    AND (
      EXISTS (
        SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.bg` bg
        WHERE bg.hadm_id = b.hadm_id
          AND (bg.fio2 IS NOT NULL OR bg.fio2_chartevents IS NOT NULL)
          AND bg.charttime > b.icu_intime AND bg.charttime <= b.effective_outtime
      )
      OR EXISTS (
        SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.ventilator_setting` vs
        WHERE vs.stay_id = b.stay_id AND vs.fio2 IS NOT NULL
          AND vs.charttime > b.icu_intime AND vs.charttime <= b.effective_outtime
      )
    )
    -- A9: laktat wajib ada, ini kriteria shock Singer 2016
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.bg` bg
      WHERE bg.hadm_id = b.hadm_id AND bg.lactate IS NOT NULL
        AND bg.charttime > b.icu_intime AND bg.charttime <= b.effective_outtime
    )
)

SELECT
  *
FROM
  cohort_final
ORDER BY
  stay_id;
