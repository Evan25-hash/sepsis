-- ============================================================
-- M0: COHORT SELECTION
-- Dataset: MIMIC-IV v3.1
-- Project: skripsi-sepsis-488003.sepsis_v3
--
-- Kriteria inklusi:
--   I1. Dewasa >= 18 tahun (Singer et al., 2016)
--   I2. First ICU stay only
--       Rasional: mencegah dependensi antar-stay dari pasien
--       yang sama (data leakage antar train/test split bila
--       satu pasien punya >1 stay). Mengikuti praktik
--       subject-level separation (Harutyunyan et al., 2019).
--   I3. Confirmed Sepsis-3 via derived.sepsis3
--       (Johnson et al., 2023 - MIMIC-Code)
--   I4. MICU + SICU only
--       Rasional: fokus pada unit medical/surgical; cardiac
--       dan neuro ICU dieksklusi karena profil shock dan
--       populasi pasiennya berbeda secara sistematis.
--
-- Kriteria eksklusi:
--   E1. Non-septic shock ICD
--       (kardiogenik, hipovolemik, anafilaktik, other shock)
--       Catatan: septic shock (ICD-10 R65.21 / ICD-9 78552)
--       TIDAK termasuk daftar ini — septic shock punya kode
--       terpisah dan tidak akan terbuang oleh filter E1.
--   E2. Semua documented treatment limitation:
--       DNR, DNI, DNR/DNI, Comfort Measures Only
--       Rasional: ketiadaan atau pembatasan intervensi
--       mencerminkan keputusan klinis, bukan fisiologi --
--       label has_shock berbasis vasopressor tidak valid
--
-- Availability filters (Kim et al., 2024 - TEW3S):
--   A1. SBP tersedia         (SOFA cardiovascular)
--   A2. DBP tersedia         (SOFA cardiovascular)
--   A3. GCS tersedia         (SOFA CNS)
--   A4. Creatinine tersedia  (SOFA renal)
--   A5. Bilirubin total      (SOFA hepatic)
--   A6. Platelet tersedia    (SOFA coagulation)
--   A7. PaO2 tersedia        (SOFA respiratory)
--   A8. FiO2 tersedia        (SOFA respiratory)
--   A9. Lactate tersedia     (shock criterion -- Singer 2016)
--
-- Ditangani di Python (bukan di M0):
--   P1. Instantaneous shock criterion (Cell 2C)
--       Mengikuti Singer et al. (2016) -- Sepsis-3 tidak
--       mendefinisikan sustained duration requirement.
--   P2. Label syok septik dengan raw intersection criterion
--       (Cell 2C): is_shock_hour bernilai TRUE bila ketiga
--       kondisi terpenuhi pada jam yang sama --
--       (a) vasopressor aktif (ned_dose > 0),
--       (b) lactate > 2.0 mmol/L (nilai mentah hasil
--           pengukuran, tanpa propagasi/LOCF),
--       (c) jam observasi > onset sepsis.
--       Penggunaan lactate mentah (bukan LOCF) mencegah
--       circular leakage pada konstruksi label.
--       (Kim et al., 2024)
--   P3. Shock-at-admission exclusion: drop shock dengan
--       onset < 4 jam (Cell 2F). Memisahkan incident shock
--       dari prevalent shock (Wardi et al., 2021).
--
-- Catatan revisi:
--   Kriteria minimum ICU LOS dihapus. Penelitian ini
--   memprediksi syok septik secara prospektif tanpa
--   mensyaratkan durasi rawat minimum; pasien dengan
--   trajektori pendek tetap disertakan.
-- ============================================================

CREATE OR REPLACE TABLE `skripsi-sepsis-488003.sepsis_v3.cohort` AS

WITH

-- ────────────────────────────────────────────────────────────
-- EKSKLUSI E1: Non-septic shock ICD diagnoses
--
-- Rasional: Kardiogenik, hipovolemik, dan anafilaktik shock
--   menghasilkan pola fisiologis MAP rendah + vasopressor +
--   lactate tinggi yang identik dengan septic shock, namun
--   mekanismenya berbeda -- sumber label noise yang signifikan.
--
-- Septic shock TIDAK termasuk daftar eksklusi ini. Pada
--   ICD-10, septic shock dikode R65.21 (kategori terpisah
--   dari R57 "shock not elsewhere classified"); pada ICD-9
--   dikode 78552. Kedua kode tersebut tidak ada di bawah,
--   sehingga pasien septic shock tidak terbuang oleh E1.
--
-- ICD-10:
--   R570 → cardiogenic shock
--   R571 → hypovolemic shock
--   R578 → other shock (mis. neurogenik, obstruktif)
--   R579 → unspecified shock
--   T782X → anaphylactic shock (semua subtype via REGEXP)
--   T886X → anaphylactic shock due to adverse drug effect
--
-- ICD-9:
--   78550 → unspecified shock
--   78551 → cardiogenic shock
--   78559 → other shock
--   9950  → anaphylactic shock NOS
--   9951  → anaphylactic shock due to food
--   9952  → anaphylactic shock due to drug
-- ────────────────────────────────────────────────────────────
dx_other_shock AS (
  SELECT DISTINCT hadm_id
  FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd`
  WHERE
    (icd_version = 10 AND icd_code IN ('R570', 'R571', 'R578', 'R579'))
    OR (icd_version = 9  AND icd_code IN ('78550', '78551', '78559'))
    OR (icd_version = 10 AND REGEXP_CONTAINS(icd_code, r'^T782'))
    OR (icd_version = 10 AND REGEXP_CONTAINS(icd_code, r'^T886'))
    OR (icd_version = 9  AND icd_code IN ('9950', '9951', '9952'))
),

-- ────────────────────────────────────────────────────────────
-- EKSKLUSI E2: Documented treatment limitation
--
-- Lima nilai di chartevents itemid 223758 (Code Status):
--   'Full code'                → tidak dieksklusi
--   'DNR (do not resuscitate)' → eksklusi
--   'DNI (do not intubate)'    → eksklusi
--   'DNR / DNI'                → eksklusi
--   'Comfort measures only'    → eksklusi
--
-- Rasional: Pasien dengan treatment limitation cenderung
--   tidak menerima vasopressor atas keputusan klinis,
--   sehingga label has_shock berbasis vasopressor tidak valid.
--   DNI dieksklusi meski tidak membatasi vasopressor secara
--   langsung, karena pembatasan intubasi menciptakan
--   confounding pada trajektori penanganan shock.
--
-- Value string diverifikasi dari MIMIC-IV v3.1 (case-sensitive).
-- ────────────────────────────────────────────────────────────
code_status_excl AS (
  SELECT DISTINCT stay_id
  FROM `physionet-data.mimiciv_3_1_icu.chartevents`
  WHERE itemid = 223758
    AND value IN (
      'DNR (do not resuscitate)',
      'DNI (do not intubate)',
      'DNR / DNI',
      'Comfort measures only'
    )
),

-- ────────────────────────────────────────────────────────────
-- BASE COHORT: Kriteria inklusi utama (I1-I4 + E1-E2)
--
-- Interpretasi Sepsis-3 onset (t_sepsis_hr):
--   GREATEST(suspected_infection_time, sofa_time) -- jam paling
--   awal di mana KEDUA kriteria Sepsis-3 simultaneously
--   terpenuhi: organ dysfunction (SOFA >= 2) AND suspected
--   infection. Mengikuti annotation MIT-LCP sepsis3.sql:
--   "earliest time at which a patient had SOFA >= 2 AND
--    suspicion of infection" (Johnson et al., 2023).
--
-- COALESCE defensif: jika salah satu timestamp NULL (rare
--   edge case), gunakan yang non-NULL untuk menghindari
--   NULL propagation di GREATEST.
--
-- Nilai negatif: community-acquired sepsis -- onset sebelum
--   ICU admission. Cell 2D handles via filter hr > t_sepsis_hr
--   yang selalu TRUE untuk kasus ini.
--
-- effective_outtime: LEAST(icu_outtime, deathtime) -- batas
--   akhir observasi, dipakai di availability filter A1-A9.
-- ────────────────────────────────────────────────────────────
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

  FROM `physionet-data.mimiciv_3_1_derived.icustay_detail` ic
  INNER JOIN `physionet-data.mimiciv_3_1_icu.icustays` icu
    ON ic.stay_id = icu.stay_id

  -- INNER JOIN: hanya pasien confirmed Sepsis-3
  -- Filter eksplisit s3.sepsis3 = TRUE memastikan kedua kriteria
  --   (SOFA >= 2 AND suspected_infection = 1) telah terpenuhi.
  --   Tanpa filter ini, baris dengan suspected_infection = 0
  --   (antibiotic atau culture criteria tidak fully met) akan
  --   ikut masuk cohort.
  INNER JOIN `physionet-data.mimiciv_3_1_derived.sepsis3` s3
    ON ic.stay_id = s3.stay_id
    AND s3.sepsis3 = TRUE

  LEFT JOIN `physionet-data.mimiciv_3_1_hosp.admissions` ad
    ON ic.hadm_id = ad.hadm_id

  WHERE
    ic.admission_age >= 18
    AND ic.first_icu_stay = TRUE
    AND icu.first_careunit IN (
      'Medical Intensive Care Unit (MICU)',
      'Surgical Intensive Care Unit (SICU)',
      'Medical/Surgical Intensive Care Unit (MICU/SICU)'
    )
    AND ic.hadm_id NOT IN (SELECT hadm_id FROM dx_other_shock)
    AND ic.stay_id NOT IN (SELECT stay_id FROM code_status_excl)
),

-- ────────────────────────────────────────────────────────────
-- AVAILABILITY FILTERS: Ketersediaan komponen SOFA (A1-A9)
--
-- Setiap pasien harus memiliki minimal 1 pengukuran per
-- komponen selama ICU stay (Kim et al., 2024 - TEW3S).
--
-- Window: LEFT OPEN RIGHT CLOSED -- charttime > icu_intime
-- Konsisten dengan konvensi M1-M8 (MIMIC-Code sofa.sql).
--
-- Catatan: filter ini memperkenalkan selection bias
-- (pasien lebih sakit cenderung diukur lebih lengkap);
-- diakui sebagai keterbatasan di BAB 4.
-- ────────────────────────────────────────────────────────────
cohort_final AS (
  SELECT b.*
  FROM base b
  WHERE
    -- A1: SBP (SOFA cardiovascular)
    EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.vitalsign` v
      WHERE v.stay_id = b.stay_id AND v.sbp IS NOT NULL
        AND v.charttime > b.icu_intime AND v.charttime <= b.effective_outtime
    )
    -- A2: DBP (SOFA cardiovascular)
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
    -- A4: Creatinine (SOFA renal)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.chemistry` ch
      WHERE ch.hadm_id = b.hadm_id AND ch.creatinine IS NOT NULL
        AND ch.charttime > b.icu_intime AND ch.charttime <= b.effective_outtime
    )
    -- A5: Bilirubin total (SOFA hepatic)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.enzyme` en
      WHERE en.hadm_id = b.hadm_id AND en.bilirubin_total IS NOT NULL
        AND en.charttime > b.icu_intime AND en.charttime <= b.effective_outtime
    )
    -- A6: Platelet (SOFA coagulation)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.complete_blood_count` cbc
      WHERE cbc.hadm_id = b.hadm_id AND cbc.platelet IS NOT NULL
        AND cbc.charttime > b.icu_intime AND cbc.charttime <= b.effective_outtime
    )
    -- A7: PaO2 (SOFA respiratory)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.bg` bg
      WHERE bg.hadm_id = b.hadm_id AND bg.po2 IS NOT NULL
        AND bg.charttime > b.icu_intime AND bg.charttime <= b.effective_outtime
    )
    -- A8: FiO2 (SOFA respiratory)
    -- OR logic: cukup salah satu dari tiga sumber
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
    -- A9: Lactate (shock criterion -- Singer 2016)
    AND EXISTS (
      SELECT 1 FROM `physionet-data.mimiciv_3_1_derived.bg` bg
      WHERE bg.hadm_id = b.hadm_id AND bg.lactate IS NOT NULL
        AND bg.charttime > b.icu_intime AND bg.charttime <= b.effective_outtime
    )
)

SELECT * FROM cohort_final
ORDER BY stay_id;