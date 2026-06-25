"""
Inference pipeline — ICU Septic Shock Monitor (v4, 21 fitur, TCN)
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import joblib
import json
import numpy as np
import pandas as pd
import torch

from tcn_arch import TCNModel
from imputation import impute_dataframe, compute_missingness

CHECKPOINT_DIR = Path(__file__).parent / "assets" / "checkpoints"
DEMO_DIR       = Path(__file__).parent / "assets" / "demos"

# Threshold dari PKD Bagian 11 (TS-CUS optimized pada validation set)
THRESHOLD_HIGH   = 0.60
THRESHOLD_MEDIUM = 0.30

# Batas panjang sequence — O(T^2) growing window mahal di atas 1000 jam
SEQ_CAP = 1000


@lru_cache(maxsize=1)
def load_artifacts():
    """Load model, scaler, feature list — cached, hanya load sekali."""
    with open(CHECKPOINT_DIR / "feature_cols_final.json") as f:
        feature_cols = json.load(f)

    scaler = joblib.load(CHECKPOINT_DIR / "scaler.pkl")

    model = TCNModel(
        n_features  = len(feature_cols),
        hidden_size = 32,
        kernel_size = 3,
        n_blocks    = 3,
        dropout     = 0.4,
    )
    ckpt = torch.load(
        CHECKPOINT_DIR / "best_tcn.pt",
        map_location="cpu",
        weights_only=False,
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    return model, scaler, feature_cols


def get_risk_level(prob: float) -> str:
    if prob >= THRESHOLD_HIGH:
        return "TINGGI"
    if prob >= THRESHOLD_MEDIUM:
        return "SEDANG"
    return "RENDAH"


@lru_cache(maxsize=1)
def _load_feature_ranking() -> List[Dict]:
    """Muat peringkat fitur dari Captum ShapleyValueSampling."""
    fr = pd.read_csv(CHECKPOINT_DIR / "feature_ranking.csv")
    return fr.sort_values("importance", ascending=False).to_dict("records")


FEATURE_RANKING = None  # di-inisialisasi lazy saat pertama dipanggil


def get_feature_ranking() -> List[Dict]:
    global FEATURE_RANKING
    if FEATURE_RANKING is None:
        FEATURE_RANKING = _load_feature_ranking()
    return FEATURE_RANKING


def get_top_k_features(k: int = 5) -> List[Dict]:
    return get_feature_ranking()[:k]


def get_all_features() -> List[Dict]:
    return get_feature_ranking()


def compute_patient_shapley(scaled_t: "torch.Tensor", feature_cols: list, n_samples: int = 25) -> List[Dict]:
    """
    Hitung Shapley Value Sampling per fitur untuk sekuen terakhir pasien.
    Menggunakan feature_mask agar setiap fitur diperlakukan sebagai satu unit
    (konsisten dengan metodologi pelatihan).

    Returns: list of dict {feature, importance}, diurutkan descending.
    """
    from captum.attr import ShapleyValueSampling
    model, _, _ = load_artifacts()
    model.eval()

    # Ambil sekuen terakhir saja (jam terkini)
    last_seq = scaled_t[-1:].unsqueeze(0)  # (1, T, 21) — seluruh history hingga jam terakhir
    seq_len  = last_seq.shape[1]

    # feat_mask: fitur f → semua timestep bernilai f
    feat_mask = torch.zeros(1, seq_len, len(feature_cols), dtype=torch.long)
    for f in range(len(feature_cols)):
        feat_mask[:, :, f] = f

    def forward_fn(inp):
        return torch.sigmoid(model(inp))

    svs  = ShapleyValueSampling(forward_fn)
    attrs = svs.attribute(last_seq, n_samples=n_samples,
                          perturbations_per_eval=1,
                          feature_mask=feat_mask)

    # Ambil nilai per fitur (identik di semua timestep karena feat_mask)
    importances = attrs[0, 0, :].abs().detach().numpy()

    results = [
        {"feature": feature_cols[i], "importance": float(importances[i])}
        for i in range(len(feature_cols))
    ]
    return sorted(results, key=lambda x: x["importance"], reverse=True)


def predict_patient(patient_df: pd.DataFrame) -> Dict:
    """
    Pipeline prediksi lengkap untuk 1 pasien.

    Inference menggunakan growing window:
        Untuk tiap T = 0, 1, ..., N-1:
            model(sequence[0:T+1]) → prob(T)
    Ini menghasilkan satu nilai risiko per jam.

    Returns dict dengan keys:
        success, truncated_pe, features_all_empty,
        df_imputed, imputed_mask, missingness,
        trajectory, imputation_report
    """
    model, scaler, feature_cols = load_artifacts()

    missingness = compute_missingness(patient_df, feature_cols)
    df_imputed, imputed_mask, imp_report = impute_dataframe(
        patient_df, feature_cols
    )

    if imp_report["refused"]:
        return {
            "success":            False,
            "truncated_pe":       False,
            "features_all_empty": imp_report["features_all_empty"],
            "df_imputed":         df_imputed,
            "imputed_mask":       imputed_mask,
            "missingness":        missingness,
            "trajectory":         None,
            "imputation_report":  imp_report,
        }

    # Cap sequence panjang — O(T^2) growing window
    truncated_pe = False
    if len(df_imputed) > SEQ_CAP:
        df_imputed   = df_imputed.iloc[-SEQ_CAP:].reset_index(drop=True)
        imputed_mask = imputed_mask.iloc[-SEQ_CAP:].reset_index(drop=True)
        truncated_pe = True

    # Scale — pakai DataFrame supaya scaler verifikasi nama & urutan fitur
    raw_df   = df_imputed[feature_cols]
    scaled   = scaler.transform(raw_df)
    scaled_t = torch.tensor(scaled, dtype=torch.float32)

    # Growing window inference
    probs = []
    with torch.no_grad():
        for T in range(len(df_imputed)):
            seq   = scaled_t[: T + 1].unsqueeze(0)   # (1, T+1, 21)
            logit = model(seq)
            prob  = torch.sigmoid(logit).item()
            probs.append(prob)

    trajectory = df_imputed[["hr"]].copy()
    trajectory["prob"]       = probs
    trajectory["risk_level"] = trajectory["prob"].apply(get_risk_level)
    trajectory["seq_len"]    = range(1, len(df_imputed) + 1)

    # Shapley per-patient pada sekuen terakhir
    shapley_ranking = compute_patient_shapley(scaled_t, feature_cols)

    return {
        "success":            True,
        "truncated_pe":       truncated_pe,
        "features_all_empty": [],
        "df_imputed":         df_imputed,
        "imputed_mask":       imputed_mask,
        "missingness":        missingness,
        "trajectory":         trajectory,
        "imputation_report":  imp_report,
        "shapley_ranking":    shapley_ranking,
    }
