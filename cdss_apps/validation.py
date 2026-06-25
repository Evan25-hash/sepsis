"""
Validasi input — ICU Septic Shock Monitor (v4, 21 fitur, TCN)
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

MAX_PATIENTS = 20

# Urutan harus cocok dengan feature_cols_final.json
FEATURE_COLS_ORDER = [
    "lactate", "bilirubin", "baseexcess", "sbp", "aniongap", "inr",
    "bicarbonate", "totalco2", "pt", "fio2", "map", "urine_output",
    "creatinine", "platelet", "dbp", "ast", "ptt", "ph",
    "wbc", "rdw", "sodium",
]

# Rentang hard — nilai di luar ini pasti error input
HARD_RANGES: Dict[str, Tuple[float, float]] = {
    "lactate":      (0.0,   40.0),
    "bilirubin":    (0.0,   80.0),
    "baseexcess":   (-50.0, 50.0),
    "sbp":          (0.0,   300.0),
    "aniongap":     (0.0,   60.0),
    "inr":          (0.0,   20.0),
    "bicarbonate":  (0.0,   60.0),
    "totalco2":     (0.0,   60.0),
    "pt":           (0.0,   200.0),
    "fio2":         (21.0,  100.0),
    "map":          (0.0,   200.0),
    "urine_output": (0.0,   2000.0),
    "creatinine":   (0.0,   150.0),
    "platelet":     (0.0,   2000.0),
    "dbp":          (0.0,   200.0),
    "ast":          (0.0,   10000.0),
    "ptt":          (0.0,   300.0),
    "ph":           (6.5,   8.0),
    "wbc":          (0.0,   200.0),
    "rdw":          (0.0,   40.0),
    "sodium":       (100.0, 200.0),
}

# Rentang normal klinis (soft) — di luar ini ditandai tapi tidak ditolak
SOFT_RANGES: Dict[str, Tuple[float, float, str]] = {
    "lactate":      (0.5,   2.2,    "mmol/L"),
    "bilirubin":    (0.2,   1.2,    "mg/dL"),
    "baseexcess":   (-2.0,  2.0,    "mEq/L"),
    "sbp":          (90.0,  140.0,  "mmHg"),
    "aniongap":     (8.0,   16.0,   "mEq/L"),
    "inr":          (0.8,   1.2,    ""),
    "bicarbonate":  (22.0,  29.0,   "mEq/L"),
    "totalco2":     (23.0,  29.0,   "mEq/L"),
    "pt":           (11.0,  13.5,   "detik"),
    "fio2":         (21.0,  40.0,   "%"),
    "map":          (70.0,  100.0,  "mmHg"),
    "urine_output": (30.0,  200.0,  "mL/jam"),
    "creatinine":   (0.6,   1.2,    "mg/dL"),
    "platelet":     (150.0, 450.0,  "rb/µL"),
    "dbp":          (60.0,  90.0,   "mmHg"),
    "ast":          (10.0,  40.0,   "U/L"),
    "ptt":          (25.0,  35.0,   "detik"),
    "ph":           (7.35,  7.45,   ""),
    "wbc":          (4.0,   11.0,   "rb/µL"),
    "rdw":          (11.5,  14.5,   "%"),
    "sodium":       (136.0, 145.0,  "mEq/L"),
}

# Nilai kritis yang perlu perhatian segera
CRITICAL_FLAGS: Dict[str, Tuple[str, float, str]] = {
    "lactate":      ("ge",  4.0,   "Laktat kritis (≥4 mmol/L)"),
    "map":          ("lt",  65.0,  "MAP kritis (<65 mmHg)"),
    "ph":           ("lt",  7.2,   "Asidosis berat (pH <7.2)"),
    "sbp":          ("lt",  90.0,  "Hipotensi (SBP <90 mmHg)"),
    "platelet":     ("lt",  50.0,  "Trombositopenia berat (<50 rb/µL)"),
    "creatinine":   ("ge",  3.0,   "AKI berat (kreatinin ≥3 mg/dL)"),
    "bilirubin":    ("ge",  2.0,   "Disfungsi hepatik (bilirubin ≥2 mg/dL)"),
    "inr":          ("ge",  1.5,   "Koagulopati (INR ≥1.5)"),
    "wbc":          ("ge",  20.0,  "Leukositosis berat (WBC ≥20 rb/µL)"),
}

# Label tampilan Indonesia
FEATURE_DISPLAY: Dict[str, str] = {
    "lactate":      "Laktat",
    "bilirubin":    "Bilirubin",
    "baseexcess":   "Base Excess",
    "sbp":          "Tekanan Darah Sistolik (SBP)",
    "aniongap":     "Anion Gap",
    "inr":          "INR",
    "bicarbonate":  "Bikarbonat",
    "totalco2":     "Total CO₂",
    "pt":           "PT",
    "fio2":         "FiO₂",
    "map":          "Tekanan Arteri Rata-Rata (MAP)",
    "urine_output": "Volume Keluaran Urin",
    "creatinine":   "Kreatinin",
    "platelet":     "Trombosit",
    "dbp":          "Tekanan Darah Diastolik (DBP)",
    "ast":          "AST",
    "ptt":          "PTT",
    "ph":           "pH Darah",
    "wbc":          "WBC",
    "rdw":          "RDW",
    "sodium":       "Sodium",
}


def is_abnormal(feature: str, value: float) -> Tuple[bool, str]:
    """Periksa apakah nilai di luar rentang normal (soft)."""
    if pd.isna(value):
        return False, ""
    lo, hi, _ = SOFT_RANGES[feature]
    if value < lo:
        return True, "low"
    if value > hi:
        return True, "high"
    return False, "normal"


def is_critical(feature: str, value: float) -> bool:
    """Periksa apakah nilai masuk kategori kritis."""
    if feature not in CRITICAL_FLAGS or pd.isna(value):
        return False
    op, thr, _ = CRITICAL_FLAGS[feature]
    if op == "ge":
        return value >= thr
    if op == "lt":
        return value < thr
    return False


def validate_row(row: pd.Series, row_index: int) -> List[str]:
    """Validasi satu baris data."""
    errors = []
    feature_cols = list(HARD_RANGES.keys())

    # hr harus integer non-negatif
    hr_val = row.get("hr", None)
    if pd.isna(hr_val):
        errors.append("Jam (hr) tidak boleh kosong.")
    else:
        try:
            hr_f = float(hr_val)
            if hr_f != round(hr_f):
                errors.append(
                    f"Jam (hr): harus bilangan bulat, bukan desimal ({hr_val})."
                )
            elif hr_f < 0:
                errors.append(f"Jam (hr): tidak boleh negatif ({hr_val}).")
        except (ValueError, TypeError):
            errors.append(f"Jam (hr): bukan angka ({hr_val}).")

    # Setiap fitur: cek tipe dan hard range
    for feat in feature_cols:
        val = row.get(feat, None)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue  # NaN diperbolehkan — akan diimputasi
        # Cek boolean (Python bool subclass of int — cukup jarang, tapi kita tolak)
        if isinstance(val, bool):
            errors.append(
                f"{FEATURE_DISPLAY.get(feat, feat)}: nilai boolean tidak valid."
            )
            continue
        try:
            val_f = float(val)
        except (ValueError, TypeError):
            errors.append(
                f"{FEATURE_DISPLAY.get(feat, feat)}: bukan angka ({val})."
            )
            continue

        if not np.isfinite(val_f):
            errors.append(
                f"{FEATURE_DISPLAY.get(feat, feat)}: nilai tidak valid (inf/nan)."
            )
            continue

        lo, hi = HARD_RANGES[feat]
        _, _, unit = SOFT_RANGES[feat]
        if val_f < lo or val_f > hi:
            unit_str = f" {unit}" if unit else ""
            errors.append(
                f"{FEATURE_DISPLAY.get(feat, feat)}: {val_f}{unit_str} "
                f"diluar batas wajar ({lo}–{hi})."
            )

    return errors


def validate_patient(patient_df: pd.DataFrame, stay_id,
                     feature_cols: list) -> List[str]:
    """Validasi satu pasien — cek hr dan fitur kosong total."""
    errors = []

    # hr harus bilangan bulat
    hr_raw = patient_df["hr"].dropna()
    non_integer = hr_raw[hr_raw != hr_raw.round()]
    if len(non_integer) > 0:
        errors.append(
            "Jam (hr) harus bilangan bulat, tidak boleh desimal."
        )

    # hr berurutan tanpa lompatan
    hrs = hr_raw.round().astype(int).sort_values().tolist()
    if len(hrs) > 0:
        expected = list(range(hrs[0], hrs[0] + len(hrs)))
        if hrs != expected:
            errors.append(
                "Jam (hr) harus berurutan tanpa lompatan. "
                "Contoh yang benar: 0, 1, 2, 3..."
            )
        if len(set(hrs)) != len(hrs):
            errors.append("Jam (hr) tidak boleh duplikat.")

    # Cek fitur yang 100% kosong → tidak bisa diimputasi → refused
    all_empty = [
        f for f in feature_cols
        if patient_df[f].isna().all()
    ]
    if all_empty:
        names = ", ".join(FEATURE_DISPLAY.get(f, f) for f in all_empty[:5])
        suffix = f" (dan {len(all_empty)-5} lainnya)" if len(all_empty) > 5 else ""
        errors.append(
            f"Fitur berikut tidak memiliki data sama sekali: "
            f"{names}{suffix}. Prediksi tidak dapat dilakukan."
        )

    return errors


def validate_all(df: pd.DataFrame) -> Dict:
    """
    Validasi seluruh DataFrame multi-pasien.
    Returns dict:
        is_valid, preflight_errors, row_errors,
        patient_errors, patient_summary, n_total_rows, n_invalid_rows
    """
    feature_cols = list(HARD_RANGES.keys())
    preflight_errors: List[str] = []
    row_errors: Dict[int, List[str]] = {}
    patient_errors: Dict = {}
    patient_summary: Dict = {}

    # Preflight
    if df is None or len(df) == 0:
        preflight_errors.append("File Excel kosong, tidak ada data sama sekali.")
        return _result(False, preflight_errors, row_errors,
                       patient_errors, patient_summary, 0, 0)

    required = ["stay_id", "hr"] + feature_cols
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        preflight_errors.append(
            f"Kolom berikut tidak ditemukan di file: {', '.join(missing_cols)}"
        )
        return _result(False, preflight_errors, row_errors,
                       patient_errors, patient_summary, len(df), 0)

    # stay_id tidak boleh kosong/whitespace
    sid_col = df["stay_id"]
    sid_empty = sid_col.isna() | (
        sid_col.astype(str).str.strip().isin(["", "nan", "None"])
    )
    if sid_empty.any():
        preflight_errors.append("Kolom 'stay_id' tidak boleh ada yang kosong.")

    n_patients = df["stay_id"].nunique()
    if n_patients > MAX_PATIENTS:
        preflight_errors.append(
            f"File berisi {n_patients} pasien. "
            f"Maksimal {MAX_PATIENTS} pasien per file."
        )

    if preflight_errors:
        return _result(False, preflight_errors, row_errors,
                       patient_errors, patient_summary, len(df), 0)

    # Per-row validation
    n_invalid_rows = 0
    for idx, row in df.iterrows():
        errs = validate_row(row, idx)
        if errs:
            row_errors[idx] = errs
            n_invalid_rows += 1

    # Per-patient validation
    for stay_id, pdf in df.groupby("stay_id"):
        errs = validate_patient(pdf, stay_id, feature_cols)
        n_row_errs = sum(
            1 for i in pdf.index if i in row_errors
        )
        has_patient_errs = len(errs) > 0
        patient_summary[stay_id] = {
            "n_rows":          len(pdf),
            "n_row_errs":      n_row_errs,
            "has_patient_errs": has_patient_errs,
            "is_valid":        (n_row_errs == 0 and not has_patient_errs),
        }
        if errs:
            patient_errors[stay_id] = errs

    is_valid = (
        len(row_errors) == 0
        and len(patient_errors) == 0
        and len(preflight_errors) == 0
    )

    return _result(is_valid, preflight_errors, row_errors,
                   patient_errors, patient_summary, len(df), n_invalid_rows)


def _result(is_valid, preflight_errors, row_errors,
            patient_errors, patient_summary, n_total_rows, n_invalid_rows):
    return {
        "is_valid":         is_valid,
        "preflight_errors": preflight_errors,
        "row_errors":       row_errors,
        "patient_errors":   patient_errors,
        "patient_summary":  patient_summary,
        "n_total_rows":     n_total_rows,
        "n_invalid_rows":   n_invalid_rows,
    }
