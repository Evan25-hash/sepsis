"""
Imputation pipeline — ICU Septic Shock Monitor (v4, 21 fitur)
Replikasi Cell 4B notebook, per-pasien.

Kategori imputasi (dari PKD Bagian 6):
  Vital signs   : interpolasi linear → ffill → bfill
  Lab & lainnya : ffill → bfill
  Urine output  : ffill → bfill (kategori tersendiri)

21 fitur final:
  Vitals : sbp, dbp, map
  Lab    : lactate, bilirubin, baseexcess, aniongap, inr, bicarbonate,
           totalco2, pt, fio2, creatinine, platelet, ast, ptt, ph, wbc,
           rdw, sodium
  Urine  : urine_output
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Klasifikasi fitur berdasarkan strategi imputasi
VITAL_SIGNS = ["sbp", "dbp", "map"]
URINE_FEATS = ["urine_output"]
# Lab = semua sisanya (ffill → bfill)


def impute_dataframe(
    patient_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Imputasi per-pasien, replikasi Cell 4B.

    Returns:
        df_imputed  : DataFrame setelah imputasi
        imputed_mask: Boolean mask — True berarti nilai diisi otomatis
        report      : dict berisi refused, features_all_empty
    """
    df = patient_df.copy().reset_index(drop=True)

    # Identifikasi fitur yang 100% kosong — tidak bisa diimputasi
    features_all_empty = [
        f for f in feature_cols if df[f].isna().all()
    ]
    if features_all_empty:
        return df, pd.DataFrame(False, index=df.index, columns=feature_cols), {
            "refused":            True,
            "features_all_empty": features_all_empty,
        }

    # Simpan mask sebelum imputasi
    original_mask = df[feature_cols].isna().copy()

    # Imputasi per kategori
    for feat in feature_cols:
        if feat in VITAL_SIGNS:
            # Interpolasi linear untuk tren halus antar pengukuran
            df[feat] = (
                df[feat]
                .interpolate(method="linear", limit_direction="both")
                .ffill()
                .bfill()
            )
        elif feat in URINE_FEATS:
            # Urine: ffill → bfill
            df[feat] = df[feat].ffill().bfill()
        else:
            # Lab: carry-forward (ffill) lalu backward-fill untuk awal sequence
            df[feat] = df[feat].ffill().bfill()

    # Mask: True = nilai yang semula kosong dan sekarang sudah diisi
    imputed_mask = original_mask & df[feature_cols].notna()

    return df, imputed_mask, {
        "refused":            False,
        "features_all_empty": [],
    }


def compute_missingness(
    patient_df: pd.DataFrame,
    feature_cols: List[str],
) -> pd.DataFrame:
    """Hitung ringkasan missing per fitur."""
    rows = []
    for feat in feature_cols:
        n_total   = len(patient_df)
        n_missing = int(patient_df[feat].isna().sum())
        rows.append({
            "feature":   feat,
            "n_total":   n_total,
            "n_missing": n_missing,
            "pct":       round(100 * n_missing / n_total, 1) if n_total > 0 else 0.0,
        })
    return pd.DataFrame(rows)
