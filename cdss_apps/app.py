"""
ICU Syok Septik Monitor — Prototipe CDSS

Workflow (Polytron-inspired):
  1. Empty / Upload
  2. Validation Preview (per-row errors)
  3. Imputation Preview (before vs after, kalau ada NaN)
  4. Dashboard Multi-pasien

Jalankan: streamlit run app.py
"""

# Suppress warning non-kritis (sklearn version, PyTorch nested tensor)
# agar console bersih saat demo. Tidak mempengaruhi hasil komputasi.
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*InconsistentVersionWarning.*")

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from inference import (
    DEMO_DIR,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    get_all_features,
    get_feature_ranking,
    get_top_k_features,
    get_risk_level,
    load_artifacts,
    predict_patient,
)
from validation import (
    FEATURE_DISPLAY,
    HARD_RANGES,
    SOFT_RANGES,
    MAX_PATIENTS,
    is_abnormal,
    is_critical,
    validate_all,
)
from generate_template import build_template_excel

# ══════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ICU Syok Septik Monitor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════
# CSS — Plus Jakarta Sans, light medical theme
# ══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-page:      #f5f7fa;
    --bg-card:      #ffffff;
    --bg-soft:      #f8fafc;
    --bg-hover:     #f1f5f9;

    --border:       #e2e8f0;
    --border-soft:  #edf0f4;

    --text-primary:   #0f172a;
    --text-secondary: #475569;
    --text-muted:     #64748b;
    --text-faint:     #94a3b8;

    --primary:       #2b5998;
    --primary-dark:  #1c3a6e;
    --primary-light: #4a7bbf;
    --primary-soft:  #e8eff7;

    --accent:        #ff9a3c;
    --accent-dark:   #ff7e0d;

    --green:         #16a34a;
    --green-soft:    #dcfce7;
    --yellow:        #d97706;
    --yellow-soft:   #fef3c7;
    --red:           #dc2626;
    --red-soft:      #fee2e2;
    --blue:          #2563eb;
    --blue-soft:     #dbeafe;
    --gray:          #6b7280;
    --gray-soft:     #f3f4f6;
}

html, body, [class*="css"], .stApp, .stMarkdown {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    color: var(--text-primary);
}

.stApp { background-color: var(--bg-page); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--primary-dark) 0%, var(--primary) 100%);
    border-right: none;
}

/* Sidebar text content (specific, not aggressive *) */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] * {
    color: #ffffff !important;
}

/* Sidebar file uploader — preserve native dark text inside white dropzone */
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.95);
    border: 1px dashed rgba(255,255,255,0.5);
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
    color: #0f172a !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {
    color: #475569 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: 1px solid var(--primary) !important;
}

/* Sidebar primary buttons (demo, download) */
section[data-testid="stSidebar"] .stButton button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: var(--accent-dark) !important;
}
section[data-testid="stSidebar"] .stButton button p,
section[data-testid="stSidebar"] .stButton button span,
section[data-testid="stSidebar"] .stButton button div {
    color: #ffffff !important;
}

/* Sidebar download button */
section[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
}
section[data-testid="stSidebar"] [data-testid="stDownloadButton"] button p {
    color: #ffffff !important;
}

/* DESKTOP: sidebar fixed 280px, collapse button hidden */
@media (min-width: 769px) {
    button[data-testid="collapsedControl"],
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
        visibility: hidden !important;
    }
    section[data-testid="stSidebar"] {
        min-width: 280px !important;
        max-width: 280px !important;
        width: 280px !important;
        transform: translateX(0) !important;
        visibility: visible !important;
    }
    section[data-testid="stSidebar"] > div {
        width: 280px !important;
    }
}

/* MOBILE: allow native Streamlit sidebar behavior (collapsible) */
@media (max-width: 768px) {
    section[data-testid="stSidebar"] {
        min-width: unset !important;
        max-width: unset !important;
        width: unset !important;
    }
    section[data-testid="stSidebar"] > div {
        width: unset !important;
    }
}

header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }

/* App header card */
.app-header {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.app-title-block { display: flex; align-items: center; gap: 14px; }
.app-icon {
    width: 42px; height: 42px;
    background: var(--primary-soft);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
}
.app-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--primary-dark);
    letter-spacing: -0.3px;
    margin: 0;
    line-height: 1.2;
}
.app-subtitle {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* Step indicator */
.steps {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    padding: 14px 20px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
}
.step {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
}
.step-active { color: var(--primary); font-weight: 600; }
.step-done { color: var(--green); }
.step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: var(--gray-soft);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
}
.step-num-active { background: var(--primary); color: white; }
.step-num-done { background: var(--green); color: white; }
.step-arrow { color: var(--text-faint); }

/* Card */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* Section label */
.section-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--primary-soft);
    margin-bottom: 14px;
    font-weight: 700;
}

/* Risk badge */
.risk-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 700;
    border: 1.5px solid;
}
.badge-rendah  { color: var(--green);  border-color: var(--green);  background: var(--green-soft); }
.badge-sedang  { color: var(--yellow); border-color: var(--yellow); background: var(--yellow-soft); }
.badge-tinggi  { color: var(--red);    border-color: var(--red);    background: var(--red-soft); }
.badge-error   { color: var(--gray);   border-color: var(--gray);   background: var(--gray-soft); }

/* Metric card */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.metric-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}
.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 28px;
    font-weight: 700;
    line-height: 1.1;
    margin-top: 6px;
}
.metric-sub {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* Banner */
.banner {
    padding: 12px 18px;
    border-radius: 10px;
    margin-bottom: 16px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-size: 13px;
    line-height: 1.6;
}
.banner-info {
    background: var(--primary-soft);
    border-left: 4px solid var(--primary);
    color: var(--text-secondary);
}
.banner-success {
    background: var(--green-soft);
    border-left: 4px solid var(--green);
    color: #14532d;
}
.banner-warning {
    background: var(--yellow-soft);
    border-left: 4px solid var(--yellow);
    color: #78350f;
}
.banner-error {
    background: var(--red-soft);
    border-left: 4px solid var(--red);
    color: #7f1d1d;
}

/* Patient triage card */
.triage-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    cursor: pointer;
    transition: all 0.15s ease;
    height: 100%;
}
.triage-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    border-color: var(--primary);
}
.triage-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.5px;
}
.triage-prob {
    font-family: 'JetBrains Mono', monospace;
    font-size: 32px;
    font-weight: 700;
    line-height: 1.1;
    margin: 10px 0 6px 0;
}
.triage-status { font-size: 13px; margin-bottom: 8px; }
.triage-meta {
    font-size: 12px;
    color: var(--text-muted);
    padding-top: 10px;
    border-top: 1px solid var(--border-soft);
}

/* Feature snapshot */
.snap-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-soft);
}
.snap-row:last-child { border-bottom: none; }
.snap-name { font-size: 13.5px; color: var(--text-primary); font-weight: 500; }
.snap-norm { font-size: 10.5px; color: var(--text-faint); margin-left: 6px; }
.snap-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    color: var(--text-primary);
    font-weight: 600;
}
.snap-unit { color: var(--text-faint); font-weight: 400; }
.val-low    { color: var(--blue) !important; }
.val-high   { color: var(--accent-dark) !important; }
.val-crit   { color: var(--red) !important; font-weight: 700 !important; }
.snap-imp {
    display: inline-block;
    background: transparent;
    color: var(--blue);
    font-size: 11px;
    padding: 0 2px;
    margin-left: 4px;
    cursor: default;
    opacity: 0.7;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: transparent; }
.stTabs [data-baseweb="tab"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px 8px 0 0;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: white !important;
    border-color: var(--primary) !important;
}

/* Dataframe */
.stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 600;
}

/* Primary button override */
.stButton button[kind="primary"] {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
}
.stButton button[kind="primary"]:hover { background: var(--accent-dark) !important; }
.stButton button[kind="primary"]:disabled {
    background: var(--gray-soft) !important;
    color: var(--text-faint) !important;
    cursor: not-allowed;
}

/* Secondary button */
.stButton button[kind="secondary"] {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    font-weight: 500 !important;
}
.stButton button[kind="secondary"]:hover { background: var(--bg-hover) !important; }

/* ── MOBILE RESPONSIVE ── */
@media (max-width: 768px) {
    /* Metric cards: smaller text on mobile */
    .metric-value {
        font-size: 22px !important;
    }
    .metric-label {
        font-size: 10px !important;
    }
    .metric-sub {
        font-size: 11px !important;
    }
    .metric-card {
        padding: 14px 14px !important;
    }

    /* App header: stack vertically on mobile */
    .app-title {
        font-size: 16px !important;
    }
    .app-subtitle {
        font-size: 10px !important;
    }
    .app-icon {
        width: 34px !important;
        height: 34px !important;
        font-size: 18px !important;
    }

    /* Step indicator: smaller text */
    .step {
        font-size: 11px !important;
    }

    /* Triage cards: full width on mobile (via flex wrap) */
    .triage-card {
        min-width: 100% !important;
    }
    .triage-prob {
        font-size: 26px !important;
    }

    /* Snap rows: smaller font */
    .snap-name {
        font-size: 12px !important;
    }
    .snap-value {
        font-size: 13px !important;
    }
    .snap-norm {
        font-size: 9.5px !important;
    }

    /* Section label */
    .section-label {
        font-size: 10px !important;
    }

    /* Banner: smaller padding */
    .banner {
        padding: 10px 14px !important;
        font-size: 12px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "view":              "empty",      # empty | validate | impute_preview | dashboard
        "raw_df":            None,
        "data_source":       None,         # nama file atau "demo:..."
        "validation_result": None,
        "predictions":       {},           # stay_id -> result dict
        "selected_patient":  None,
        "show_overview":     True,
        "confirm_reset":     False,
        "uploader_key":      0,            # increment on reset to clear file uploader
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def reset_session():
    # Increment uploader_key BEFORE clearing, so it persists into new session
    next_uploader_key = st.session_state.get("uploader_key", 0) + 1
    keys_to_clear = ["view", "raw_df", "data_source", "validation_result",
                     "predictions", "selected_patient", "show_overview",
                     "confirm_reset", "last_uploaded_name"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    init_session()
    st.session_state.uploader_key = next_uploader_key

init_session()

# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def risk_color(level: str) -> str:
    return {"RENDAH": "#16a34a", "SEDANG": "#d97706", "TINGGI": "#dc2626"}.get(level, "#6b7280")

def risk_icon(level: str) -> str:
    return {"RENDAH": "●", "SEDANG": "▲", "TINGGI": "■"}.get(level, "○")

def risk_badge(level: str) -> str:
    cls = {"RENDAH": "badge-rendah", "SEDANG": "badge-sedang", "TINGGI": "badge-tinggi"}.get(level, "badge-error")
    icon = risk_icon(level)
    return f'<span class="risk-badge {cls}">{icon} {level}</span>'

def fmt_value(feat: str, val: float) -> str:
    if pd.isna(val):
        return "—"
    if feat in ("platelet", "urine_output", "fio2"):
        return f"{val:.0f}"
    return f"{val:.1f}"

def fmt_stay_id(sid) -> str:
    """
    Format stay_id untuk display.
    Excel sering menyimpan ID numerik sebagai float (30074108.0).
    Tampilkan sebagai integer kalau memungkinkan, string kalau tidak.
    """
    try:
        f = float(sid)
        if f == int(f):
            return str(int(f))
        return str(sid)
    except (ValueError, TypeError):
        return str(sid)

def fmt_ribuan(n) -> str:
    """
    Format angka dengan pemisah ribuan gaya Indonesia (titik).
    Contoh: 1234 -> '1.234', 1234567 -> '1.234.567'.
    """
    return f"{int(n):,}".replace(",", ".")

def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalisasi nama kolom supaya toleran terhadap variasi penulisan user:
    - Hapus spasi di awal/akhir (' lactate' -> 'lactate')
    - Konversi ke huruf kecil ('HR' -> 'hr', 'Lactate' -> 'lactate')

    Kalau ada kolom duplikat setelah normalisasi (mis. 2 kolom 'lactate'),
    kolom pertama yang dipertahankan.
    """
    # Strip + lowercase semua nama kolom
    new_cols = [str(c).strip().lower() for c in df.columns]
    df.columns = new_cols

    # Buang kolom duplikat — pertahankan yang pertama
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df

def _normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalisasi kolom numerik:
    - Konversi desimal koma ('3,5') ke titik ('3.5') — umum di Excel lokal Indonesia
    - Hapus spasi berlebih
    Hanya diterapkan pada kolom fitur, bukan stay_id.
    """
    from validation import HARD_RANGES
    feature_cols = list(HARD_RANGES.keys()) + ["hr"]

    for col in feature_cols:
        if col not in df.columns:
            continue
        # Kalau kolom bukan numerik (string/object), coba bersihkan.
        # Pandas 3.x menyimpan string sebagai dtype 'str', bukan 'object',
        # jadi cek "bukan numerik" lebih robust daripada cek == object.
        if not pd.api.types.is_numeric_dtype(df[col]):
            cleaned = (
                df[col]
                .astype(str)
                .str.strip()
                .str.replace(",", ".", regex=False)
            )
            # Kembalikan string kosong / 'nan' jadi NaN
            cleaned = cleaned.replace({"": None, "nan": None, "None": None})
            df[col] = pd.to_numeric(cleaned, errors="coerce")
    return df

def load_excel(uploaded_file) -> Optional[pd.DataFrame]:
    """Load Excel with fallback dan pesan error yang ramah."""
    friendly_error = (
        "File tidak dapat dibaca. Pastikan file berformat Excel (.xlsx) "
        "yang valid dan tidak rusak. Gunakan template yang tersedia di sidebar."
    )
    try:
        df = pd.read_excel(uploaded_file, sheet_name="patient_data")
    except (KeyError, ValueError):
        # Sheet 'patient_data' tidak ada — coba sheet pertama
        try:
            df = pd.read_excel(uploaded_file)
        except Exception:
            st.error(friendly_error)
            return None
    except Exception:
        st.error(friendly_error)
        return None

    df = _normalize_column_names(df)
    return _normalize_numeric_columns(df)

def load_demo(filename: str) -> pd.DataFrame:
    df = pd.read_excel(DEMO_DIR / filename, sheet_name="patient_data")
    df = _normalize_column_names(df)
    return _normalize_numeric_columns(df)

# ══════════════════════════════════════════════════════════════════════════
# CHARTS
# ══════════════════════════════════════════════════════════════════════════

def plot_risk_trajectory(traj: pd.DataFrame, patient_id: str) -> go.Figure:
    """Risk trajectory chart."""
    hrs   = traj["hr"]
    probs = traj["prob"] * 100
    max_hr = hrs.max()

    fig = go.Figure()

    # Threshold horizontal lines
    fig.add_hline(y=THRESHOLD_MEDIUM * 100, line_dash="dot",
                  line_color="#d97706", line_width=1.2,
                  annotation_text=f"Sedang", annotation_position="right",
                  annotation_font=dict(color="#d97706", size=10))
    fig.add_hline(y=THRESHOLD_HIGH * 100, line_dash="dot",
                  line_color="#dc2626", line_width=1.2,
                  annotation_text=f"Tinggi", annotation_position="right",
                  annotation_font=dict(color="#dc2626", size=10))

    # Main line + fill
    fig.add_trace(go.Scatter(
        x=hrs, y=probs,
        fill="tozeroy",
        fillcolor="rgba(43,89,152,0.08)",
        line=dict(color="#2b5998", width=2.4),
        mode="lines",
        hovertemplate="<b>Jam %{x}</b><br>Risiko: %{y:.1f}%<extra></extra>",
        showlegend=False,
    ))

    # Colored markers
    marker_size = 8 if len(traj) <= 72 else 5
    for level, color in [("RENDAH", "#16a34a"), ("SEDANG", "#d97706"), ("TINGGI", "#dc2626")]:
        mask = traj["risk_level"] == level
        if mask.any():
            fig.add_trace(go.Scatter(
                x=hrs[mask], y=probs[mask],
                mode="markers",
                marker=dict(color=color, size=marker_size,
                            line=dict(color="#ffffff", width=1.5)),
                name=level,
                hovertemplate=f"<b>Jam %{{x}}</b><br>{level} · %{{y:.1f}}%<extra></extra>",
            ))

    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="Plus Jakarta Sans", color="#0f172a", size=11),
        xaxis=dict(
            title=dict(text="Jam di ICU", font=dict(size=12, color="#475569")),
            gridcolor="#edf0f4",
            tickfont=dict(family="JetBrains Mono", size=10, color="#64748b"),
        ),
        yaxis=dict(
            title=dict(text="Risiko syok septik (%)", font=dict(size=12, color="#475569")),
            range=[0, 100],
            gridcolor="#edf0f4",
            tickfont=dict(family="JetBrains Mono", size=10, color="#64748b"),
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,0.9)", bordercolor="#e2e8f0", borderwidth=1,
            font=dict(size=11, family="Plus Jakarta Sans"),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#e2e8f0",
                        font=dict(family="Plus Jakarta Sans", size=12, color="#0f172a")),
    )
    return fig

def plot_top_factors_patient(shapley_data: list, top_k: int = 5) -> go.Figure:
    """Top factors bar chart — berdasarkan Shapley per pasien (jam terakhir)."""
    features = shapley_data[:top_k]
    features_sorted = sorted(features, key=lambda x: x["importance"])

    names  = [FEATURE_DISPLAY.get(f["feature"], f["feature"]) for f in features_sorted]
    values = [f["importance"] for f in features_sorted]

    fig = go.Figure(go.Bar(
        x=values, y=names,
        orientation="h",
        marker=dict(
            color=values,
            colorscale=[[0, "#4a7bbf"], [1, "#dc2626"]],
            line=dict(color="#ffffff", width=1),
        ),
        text=[f"{v/sum(values)*100:.1f}%" for v in values] if sum(values) > 0 else [""] * len(values),
        textposition="outside",
        textfont=dict(family="JetBrains Mono", size=10, color="#475569"),
        hovertemplate="<b>%{y}</b><br>Kontribusi: %{text}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="Plus Jakarta Sans", color="#0f172a", size=11),
        xaxis=dict(
            title=dict(text="Tingkat Pengaruh", font=dict(size=10, color="#475569")),
            gridcolor="#edf0f4",
            tickfont=dict(family="JetBrains Mono", size=9, color="#64748b"),
        ),
        yaxis=dict(tickfont=dict(size=12, color="#0f172a"), gridcolor="#edf0f4"),
        margin=dict(l=10, r=70, t=10, b=10),
        height=240,
    )
    return fig

# ══════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════

# Banner icons per type
_BANNER_ICONS = {
    "info":    "ⓘ",
    "success": "✓",
    "warning": "⚠",
    "error":   "✕",
}

def render_banner(banner_type: str, title: str, body: str = ""):
    """
    Render banner safely as single-line HTML.
    Prevents HTML rendering bugs from multi-line f-strings.

    banner_type: 'info' | 'success' | 'warning' | 'error'
    title:       bold heading
    body:        plain text content (already-formatted HTML or list ul allowed)
    """
    icon = _BANNER_ICONS.get(banner_type, "ⓘ")
    body_html = (
        f'<div style="font-weight: 700; margin-bottom: 4px;">{title}</div>'
        f'<div>{body}</div>'
    ) if body else f'<div style="font-weight: 700;">{title}</div>'

    html = (
        f'<div class="banner banner-{banner_type}">'
        f'<div style="font-size: 18px;">{icon}</div>'
        f'<div>{body_html}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def render_steps(current: str):
    """Step indicator."""
    steps_def = [
        ("upload",         "Unggah Data"),
        ("validate",       "Validasi"),
        ("impute_preview", "Tinjau Data"),
        ("dashboard",      "Hasil Prediksi"),
    ]

    state_order = {"empty": 0, "validate": 1, "impute_preview": 2, "dashboard": 3}
    current_idx = state_order.get(current, 0)

    items = []
    for i, (key, label) in enumerate(steps_def):
        if i < current_idx:
            cls = "step-done"; num_cls = "step-num-done"; num_content = "✓"
        elif i == current_idx:
            cls = "step-active"; num_cls = "step-num-active"; num_content = str(i + 1)
        else:
            cls = ""; num_cls = ""; num_content = str(i + 1)

        item_html = (
            f'<div class="step {cls}">'
            f'<span class="step-num {num_cls}">{num_content}</span>{label}'
            f'</div>'
        )
        items.append(item_html)
        if i < len(steps_def) - 1:
            items.append('<div class="step-arrow">→</div>')

    st.markdown(
        '<div class="steps">' + "".join(items) + '</div>',
        unsafe_allow_html=True
    )

def render_app_header():
    """Top header with title and reset button."""
    has_data = st.session_state.view != "empty"
    col_title, col_btn = st.columns([4, 1])

    with col_title:
        st.markdown("""
        <div class="app-header" style="margin: 0; border: none; padding: 0; background: transparent;">
            <div class="app-title-block">
                <div class="app-icon">🏥</div>
                <div>
                    <div class="app-title">ICU Syok Septik Monitor</div>
                    <div class="app-subtitle">Sistem Pendukung Keputusan untuk Pemantauan Risiko Syok Septik</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_btn:
        if has_data:
            st.write("")  # spacing
            # Konfirmasi dua-langkah: cegah reset tidak sengaja
            if st.session_state.get("confirm_reset", False):
                st.markdown(
                    '<div style="font-size: 11px; color: var(--text-muted); '
                    'margin-bottom: 4px; text-align: center;">Yakin mulai ulang?</div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Ya", use_container_width=True, key="btn_reset_yes",
                                 type="primary"):
                        reset_session()
                        st.rerun()
                with c2:
                    if st.button("Batal", use_container_width=True, key="btn_reset_no"):
                        st.session_state.confirm_reset = False
                        st.rerun()
            else:
                if st.button("↺ Mulai Ulang", use_container_width=True, key="btn_reset"):
                    st.session_state.confirm_reset = True
                    st.rerun()

def render_current_values(latest_imputed: pd.Series, latest_mask: pd.Series, hr: int):
    """Clinical snapshot panel."""
    feature_cols = list(HARD_RANGES.keys())

    rows = []
    for feat in feature_cols:
        val = latest_imputed[feat]
        was_imputed = bool(latest_mask[feat]) if feat in latest_mask else False
        display_name = FEATURE_DISPLAY.get(feat, feat)
        _, _, unit = SOFT_RANGES[feat]

        critical = is_critical(feat, val)
        abnormal, level = is_abnormal(feat, val)

        if critical:
            val_class = "val-crit"; icon = "●"
        elif abnormal and level == "high":
            val_class = "val-high"; icon = "↑"
        elif abnormal and level == "low":
            val_class = "val-low"; icon = "↓"
        else:
            val_class = ""; icon = ""

        val_str = fmt_value(feat, val)

        soft_lo, soft_hi, _ = SOFT_RANGES[feat]
        range_str = (f"{soft_lo:g}–{soft_hi:g}" if soft_lo != soft_hi else f"~{soft_lo:g}")

        imp_tag = '<span class="snap-imp" title="Nilai diisi otomatis">•</span>' if was_imputed else ""

        row_html = (
            f'<div class="snap-row">'
            f'<div><span class="snap-name">{display_name}</span>'
            f'<span class="snap-norm">normal {range_str}</span>{imp_tag}</div>'
            f'<div class="snap-value {val_class}">{icon} {val_str} '
            f'<span class="snap-unit">{unit}</span></div>'
            f'</div>'
        )
        rows.append(row_html)

    header = (
        f'<div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">'
        f'Jam ke-{hr} · '
        f'<span style="color: var(--accent-dark);">↑ tinggi</span> · '
        f'<span style="color: var(--blue);">↓ rendah</span> · '
        f'<span style="color: var(--red);">● kritis</span>'
        f'</div>'
    )
    st.markdown(header + "".join(rows), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# VIEW: SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 8px 0 28px 0;">
            <div style="font-size: 22px; font-weight: 700; color: #ffffff;">
                🏥 ICU Monitor
            </div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px;">
                Prediksi syok septik
            </div>
            <div style="height: 1px; background: rgba(255,255,255,0.15); margin-top: 18px;"></div>
        </div>
        """, unsafe_allow_html=True)

        # Upload section (always available)
        st.markdown(
            '<div style="font-size: 11px; letter-spacing: 1.5px; color: rgba(255,255,255,0.7); '
            'margin-bottom: 4px; font-weight: 600;">UNGGAH DATA PASIEN</div>'
            '<div style="font-size: 10.5px; color: rgba(255,255,255,0.5); margin-bottom: 8px;">'
            'Maks. 20 pasien per file</div>',
            unsafe_allow_html=True
        )
        uploaded = st.file_uploader(
            "Pilih file Excel (.xlsx)",
            type=["xlsx"],
            help="File bisa berisi 1 atau beberapa pasien. Lihat sheet 'panduan' di template.",
            label_visibility="collapsed",
            key=f"file_uploader_{st.session_state.get('uploader_key', 0)}",
        )

        if uploaded is not None and st.session_state.get("last_uploaded_name") != uploaded.name:
            df = load_excel(uploaded)
            if df is not None:
                st.session_state.raw_df = df
                st.session_state.data_source = uploaded.name
                st.session_state.last_uploaded_name = uploaded.name
                st.session_state.view = "validate"
                st.session_state.validation_result = None
                st.session_state.predictions = {}
                st.session_state.selected_patient = None
                st.session_state.show_overview = True
                st.rerun()

        st.markdown(
            '<div style="font-size: 11px; letter-spacing: 1.5px; color: rgba(255,255,255,0.7); '
            'margin: 22px 0 8px 0; font-weight: 600;">CONTOH DATA</div>',
            unsafe_allow_html=True
        )

        demo_options = [
            ("Contoh 1 Pasien",      "demo_single.xlsx"),
            ("Contoh Multi-Pasien",  "demo_multi.xlsx"),
        ]

        for label, fname in demo_options:
            if st.button(label, use_container_width=True, key=f"demo_{fname}"):
                df = load_demo(fname)
                st.session_state.raw_df = df
                st.session_state.data_source = f"contoh: {label}"
                st.session_state.last_uploaded_name = None
                st.session_state.view = "validate"
                st.session_state.validation_result = None
                st.session_state.predictions = {}
                st.session_state.selected_patient = None
                st.session_state.show_overview = True
                st.rerun()

        st.markdown(
            '<div style="font-size: 11px; letter-spacing: 1.5px; color: rgba(255,255,255,0.7); '
            'margin: 22px 0 8px 0; font-weight: 600;">UNDUH</div>',
            unsafe_allow_html=True
        )
        template_bytes = build_template_excel()
        st.download_button(
            "Template Kosong",
            data=template_bytes,
            file_name="template_sepsiswatch.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )





# ══════════════════════════════════════════════════════════════════════════
# VIEW: EMPTY (Landing)
# ══════════════════════════════════════════════════════════════════════════

def view_empty():
    render_app_header()

    st.markdown("""
    <div style="text-align: center; padding: 50px 20px 30px;">
        <div style="font-size: 56px; margin-bottom: 16px;">🏥</div>
        <div style="font-size: 22px; font-weight: 700; color: var(--text-primary);
                    margin-bottom: 10px;">
            Selamat Datang
        </div>
        <div style="font-size: 14px; color: var(--text-secondary);
                    max-width: 580px; margin: 0 auto 32px auto; line-height: 1.7;">
            Sistem ini membantu memantau dan memprediksi risiko terjadinya
            <b>syok septik</b> pada pasien ICU berdasarkan data klinis per jam.
            Untuk memulai, unggah file Excel atau pilih salah satu contoh di
            samping kiri.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3 step cards
    col1, col2, col3 = st.columns(3)
    step_cards = [
        ("1", "Unggah Data Pasien",
         "Pilih file Excel dengan data klinis per jam. File bisa berisi satu atau beberapa pasien."),
        ("2", "Tinjau & Verifikasi",
         "Sistem akan memeriksa data dan menampilkan jika ada nilai yang perlu diperbaiki."),
        ("3", "Lihat Hasil Prediksi",
         "Dapatkan estimasi risiko syok septik per jam beserta faktor yang berkontribusi."),
    ]
    for col, (num, title, desc) in zip([col1, col2, col3], step_cards):
        with col:
            st.markdown(f"""
            <div class="card" style="text-align: center; min-height: 180px;">
                <div style="display: inline-flex; align-items: center; justify-content: center;
                            width: 36px; height: 36px; border-radius: 50%;
                            background: var(--primary-soft); color: var(--primary);
                            font-weight: 700; font-size: 16px; margin-bottom: 14px;">
                    {num}
                </div>
                <div style="font-size: 15px; font-weight: 600; margin-bottom: 8px;
                            color: var(--text-primary);">
                    {title}
                </div>
                <div style="font-size: 12.5px; color: var(--text-muted); line-height: 1.6;">
                    {desc}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Belum punya file? Coba salah satu **contoh data** di panel sebelah kiri.")

# ══════════════════════════════════════════════════════════════════════════
# VIEW: VALIDATION
# ══════════════════════════════════════════════════════════════════════════

def view_validate():
    render_app_header()
    render_steps("validate")

    df = st.session_state.raw_df

    # Run validation
    if st.session_state.validation_result is None:
        st.session_state.validation_result = validate_all(df)

    val = st.session_state.validation_result

    # Preflight errors — show and stop
    if val.get("preflight_errors"):
        err_items = "".join(f"<li>{e}</li>" for e in val["preflight_errors"])
        render_banner(
            "error",
            "File Tidak Dapat Diproses",
            f'<ul style="margin: 0; padding-left: 18px;">{err_items}</ul>',
        )

        if st.button("← Kembali", use_container_width=False):
            reset_session()
            st.rerun()
        return

    # Summary banner
    n_total   = val["n_total_rows"]
    n_invalid = val["n_invalid_rows"]
    n_valid   = n_total - n_invalid
    n_patient_errs = len(val["patient_errors"])
    n_patients = len(val["patient_summary"])

    if val["is_valid"]:
        render_banner(
            "success",
            "Data Lulus Validasi",
            f"{n_patients} pasien, {n_total} baris data. "
            f"Siap untuk dilanjutkan ke tahap berikutnya.",
        )
    else:
        struct_note = (
            f" · {n_patient_errs} pasien dengan masalah struktur"
            if n_patient_errs > 0 else ""
        )
        body = (
            f'{n_total} baris total · '
            f'<b style="color: var(--green);">{n_valid} valid</b> · '
            f'<b style="color: var(--red);">{n_invalid} bermasalah</b>'
            f'{struct_note}. '
            f'Perbaiki baris yang bermasalah di file Excel Anda, lalu unggah ulang.'
        )
        render_banner("warning", "Ada Data yang Perlu Diperbaiki", body)

    # Patient-level errors first
    if val["patient_errors"]:
        st.markdown('<div class="section-label">Masalah Per Pasien</div>', unsafe_allow_html=True)
        for stay_id, errs in val["patient_errors"].items():
            err_items = "".join(f"<li>{e}</li>" for e in errs)
            body = (
                f'<ul style="margin: 0; padding-left: 18px; font-size: 12.5px;">'
                f'{err_items}</ul>'
            )
            patient_error_html = (
                f'<div class="banner banner-error" style="margin-bottom: 10px;">'
                f'<div style="font-size: 16px;">●</div>'
                f'<div>'
                f'<div style="font-weight: 600; margin-bottom: 4px;">Pasien {fmt_stay_id(stay_id)}</div>'
                f'{body}'
                f'</div>'
                f'</div>'
            )
            st.markdown(patient_error_html, unsafe_allow_html=True)

    # Data preview with error column
    st.markdown('<div class="section-label">Tinjauan Data</div>', unsafe_allow_html=True)

    # Build preview dataframe
    preview = df.copy().reset_index(drop=True)

    # Add status & error column
    statuses = []
    error_msgs = []
    for idx in preview.index:
        if idx in val["row_errors"]:
            statuses.append("⚠ Bermasalah")
            error_msgs.append(" · ".join(val["row_errors"][idx]))
        else:
            statuses.append("✓ Valid")
            error_msgs.append("")

    preview.insert(0, "Status", statuses)
    # Reorder columns: Status, stay_id, hr, features (no Informasi column)
    feature_cols = list(HARD_RANGES.keys())
    col_order = ["Status", "stay_id", "hr"] + feature_cols
    preview = preview[[c for c in col_order if c in preview.columns]]

    # Display
    st.dataframe(
        preview,
        use_container_width=True,
        height=420,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(width="small"),
        }
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Action buttons
    col_back, col_spacer, col_next = st.columns([1, 2, 1])
    with col_back:
        if st.button("← Kembali", use_container_width=True, key="btn_validate_back"):
            reset_session()
            st.rerun()
    with col_next:
        next_btn = st.button(
            "Lanjutkan →",
            use_container_width=True,
            type="primary",
            disabled=not val["is_valid"],
            key="btn_validate_next",
        )
        if next_btn:
            st.session_state.view = "impute_preview"
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# VIEW: IMPUTATION PREVIEW
# ══════════════════════════════════════════════════════════════════════════

def view_impute_preview():
    render_app_header()
    render_steps("impute_preview")

    df = st.session_state.raw_df
    feature_cols = list(HARD_RANGES.keys())

    # Quick missing check
    total_cells = sum(len(df[df["stay_id"] == sid]) * len(feature_cols)
                      for sid in df["stay_id"].unique())
    total_missing = df[feature_cols].isna().sum().sum()
    pct_missing = (total_missing / total_cells * 100) if total_cells > 0 else 0

    n_patients = df["stay_id"].nunique()

    # Header info
    if total_missing == 0:
        render_banner(
            "success",
            "Data Lengkap",
            f"Tidak ada nilai yang kosong. {n_patients} pasien siap untuk prediksi.",
        )
    else:
        body = (
            f'Total <b>{fmt_ribuan(total_missing)} nilai kosong</b> '
            f'({pct_missing:.1f}% dari data) akan diisi oleh sistem '
            f'berdasarkan pola dari nilai-nilai yang tersedia.'
        )
        render_banner("info", "Ada Nilai Kosong yang Akan Diisi Otomatis", body)

    # Per-patient overview
    st.markdown('<div class="section-label">Ringkasan Per Pasien</div>', unsafe_allow_html=True)

    summary_rows = []
    for stay_id, patient_df in df.groupby("stay_id"):
        n_rows = len(patient_df)
        n_miss = int(patient_df[feature_cols].isna().sum().sum())
        n_total_p = n_rows * len(feature_cols)
        pct_p = (n_miss / n_total_p * 100) if n_total_p > 0 else 0
        summary_rows.append({
            "ID Pasien":      str(stay_id),
            "Jumlah Jam":     n_rows,
            "Nilai Kosong":   n_miss,
            "% Kosong":       f"{pct_p:.1f}%",
        })
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True, height=min(400, 50 + 36 * len(summary_df)))

    # Missing per column + comparison preview
    if total_missing > 0:
        st.markdown('<div class="section-label">Nilai Kosong Per Kolom</div>', unsafe_allow_html=True)

        missing_per_col = []
        for feat in feature_cols:
            n_miss_col = int(df[feat].isna().sum())
            pct_col = (n_miss_col / len(df) * 100) if len(df) > 0 else 0
            display_name = FEATURE_DISPLAY.get(feat, feat)
            missing_per_col.append({
                "Fitur":         display_name,
                "Nilai Kosong":  n_miss_col,
                "Persentase":    f"{pct_col:.1f}%",
            })
        st.dataframe(pd.DataFrame(missing_per_col),
                     use_container_width=True, hide_index=True, height=min(400, 50 + 36 * 13))

        # ── Pratinjau Hasil Pengisian (per pasien) ──────────────────────
        st.markdown(
            '<div class="section-label">Pratinjau Hasil Pengisian</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div style="font-size: 12.5px; color: var(--text-muted); '
            'margin-bottom: 12px;">'
            'Sel berwarna biru muda menandakan nilai yang diisi otomatis oleh sistem. '
            'Pilih pasien untuk melihat detailnya.'
            '</div>',
            unsafe_allow_html=True
        )

        # Patient selector (kalau multi-pasien)
        stay_id_list = sorted(df["stay_id"].unique(), key=lambda x: str(x))
        if len(stay_id_list) > 1:
            selected_sid_preview = st.selectbox(
                "Pilih pasien untuk pratinjau",
                options=stay_id_list,
                format_func=lambda x: f"Pasien {fmt_stay_id(x)}",
                key="impute_preview_patient",
                label_visibility="collapsed",
            )
        else:
            selected_sid_preview = stay_id_list[0]

        # Get patient data
        patient_raw = df[df["stay_id"] == selected_sid_preview][
            ["hr"] + feature_cols
        ].sort_values("hr").reset_index(drop=True)

        # Run imputation on this patient (without prediction)
        from imputation import impute_dataframe
        patient_imputed, imputed_mask, _ = impute_dataframe(patient_raw, feature_cols)

        # Stats
        n_imp_patient = int(imputed_mask.sum().sum())
        n_total_patient = imputed_mask.size
        pct_imp_patient = (n_imp_patient / n_total_patient * 100) if n_total_patient > 0 else 0

        info_html = (
            f'<div style="font-family: \'JetBrains Mono\', monospace; font-size: 11.5px; '
            f'color: var(--text-muted); margin-bottom: 10px;">'
            f'Pasien <b style="color: var(--text-primary);">{selected_sid_preview}</b> · '
            f'{fmt_ribuan(n_imp_patient)} nilai diisi otomatis ({pct_imp_patient:.1f}% dari total)'
            f'</div>'
        )
        st.markdown(info_html, unsafe_allow_html=True)

        # Build manual HTML table with highlighted imputed cells
        # (Streamlit's Styler has issues in pandas 3.x; manual HTML is more reliable)
        thead_cells = '<th style="padding: 8px 12px; text-align: left; font-weight: 600; ' \
                      'background: #f1f5f9; border-bottom: 2px solid #2b5998; ' \
                      'font-size: 12px; color: #475569;">Jam</th>'
        for feat in feature_cols:
            display_name = FEATURE_DISPLAY.get(feat, feat)
            thead_cells += (
                f'<th style="padding: 8px 12px; text-align: left; font-weight: 600; '
                f'background: #f1f5f9; border-bottom: 2px solid #2b5998; '
                f'font-size: 12px; color: #475569;">{display_name}</th>'
            )

        tbody_rows = []
        for i in range(len(patient_imputed)):
            row_cells = []
            jam_val = int(patient_imputed["hr"].iloc[i])
            row_cells.append(
                f'<td style="padding: 7px 12px; border-bottom: 1px solid #edf0f4; '
                f'font-family: \'JetBrains Mono\', monospace; font-size: 12px; '
                f'color: #475569; font-weight: 600;">{jam_val}</td>'
            )
            for feat in feature_cols:
                val = patient_imputed[feat].iloc[i]
                was_imputed = bool(imputed_mask[feat].iloc[i])

                # Format value
                if feat in ("platelet", "urine_output", "fio2"):
                    val_str = f"{val:.0f}"
                else:
                    val_str = f"{val:.1f}"

                if was_imputed:
                    cell_style = (
                        "padding: 7px 12px; border-bottom: 1px solid #edf0f4; "
                        "font-family: 'JetBrains Mono', monospace; font-size: 12px; "
                        "background: #dbeafe; color: #2563eb; font-weight: 700;"
                    )
                else:
                    cell_style = (
                        "padding: 7px 12px; border-bottom: 1px solid #edf0f4; "
                        "font-family: 'JetBrains Mono', monospace; font-size: 12px; "
                        "color: #0f172a;"
                    )
                row_cells.append(f'<td style="{cell_style}">{val_str}</td>')
            tbody_rows.append(f'<tr>{"".join(row_cells)}</tr>')

        table_html = (
            '<div style="overflow-x: auto; max-height: 420px; overflow-y: auto; '
            'border: 1px solid #e2e8f0; border-radius: 8px;">'
            '<table style="width: 100%; border-collapse: collapse; '
            'font-family: \'Plus Jakarta Sans\', sans-serif;">'
            f'<thead><tr>{thead_cells}</tr></thead>'
            f'<tbody>{"".join(tbody_rows)}</tbody>'
            '</table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)



    st.markdown("<br>", unsafe_allow_html=True)

    # Action buttons
    col_back, col_spacer, col_next = st.columns([1, 2, 1])
    with col_back:
        if st.button("← Kembali", use_container_width=True, key="btn_imp_back"):
            st.session_state.view = "validate"
            st.rerun()
    with col_next:
        next_btn = st.button(
            "Hasilkan Prediksi →",
            use_container_width=True,
            type="primary",
            key="btn_imp_next",
        )
        if next_btn:
            # Run predictions for all patients (lazy / progress)
            run_all_predictions()
            st.session_state.view = "dashboard"
            st.rerun()

def run_all_predictions():
    """Run inference for all patients with progress."""
    df = st.session_state.raw_df
    feature_cols = list(HARD_RANGES.keys())

    progress = st.progress(0.0)
    status = st.empty()

    stay_ids = sorted(df["stay_id"].unique(), key=lambda x: str(x))
    n_total = len(stay_ids)

    predictions = {}
    for i, stay_id in enumerate(stay_ids):
        status.text(f"Menghitung pasien {i+1}/{n_total} (ID: {fmt_stay_id(stay_id)})...")
        patient_df = df[df["stay_id"] == stay_id][["hr"] + feature_cols].copy()
        result = predict_patient(patient_df)
        predictions[stay_id] = result
        progress.progress((i + 1) / n_total)

    st.session_state.predictions = predictions

    # Auto-select first valid patient
    for sid in stay_ids:
        if predictions[sid]["success"]:
            st.session_state.selected_patient = sid
            break

    # Show overview if >1 patient
    st.session_state.show_overview = (n_total > 1)

    progress.empty()
    status.empty()

# ══════════════════════════════════════════════════════════════════════════
# VIEW: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════

def view_dashboard():
    render_app_header()
    render_steps("dashboard")

    predictions = st.session_state.predictions
    stay_ids = sorted(predictions.keys(), key=lambda x: str(x))

    n_patients = len(stay_ids)
    n_success = sum(1 for sid in stay_ids if predictions[sid]["success"])

    # If multi-patient AND show_overview, render triage view
    if n_patients > 1 and st.session_state.show_overview:
        render_triage_overview(stay_ids, predictions)
        return

    # Single patient view
    if n_success == 0:
        render_banner(
            "error",
            "Tidak Ada Prediksi yang Dapat Ditampilkan",
            "Semua pasien tidak dapat diprediksi karena data tidak lengkap.",
        )
        for sid in stay_ids:
            res = predictions[sid]
            if not res["success"]:
                features = res["features_all_empty"]
                names = ", ".join(FEATURE_DISPLAY.get(f, f) for f in features)
                card_html = (
                    f'<div class="card" style="margin-bottom: 10px;">'
                    f'<div style="font-weight: 600;">Pasien {fmt_stay_id(sid)}</div>'
                    f'<div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">'
                    f'Fitur kosong total: {names}'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
        return

    # Patient selector (only if multi-patient)
    if n_patients > 1:
        col_back, col_select = st.columns([1, 3])
        with col_back:
            if st.button("← Daftar Pasien", use_container_width=True, key="btn_back_overview"):
                st.session_state.show_overview = True
                st.rerun()

        with col_select:
            options = []
            for sid in stay_ids:
                res = predictions[sid]
                if res["success"]:
                    last_prob = res["trajectory"].iloc[-1]["prob"]
                    last_level = res["trajectory"].iloc[-1]["risk_level"]
                    label = f"Pasien {fmt_stay_id(sid)}  ·  {risk_icon(last_level)} {last_level} ({last_prob*100:.0f}%)"
                else:
                    label = f"Pasien {fmt_stay_id(sid)}  ·  Tidak dapat diprediksi"
                options.append((sid, label))

            selected_label = st.selectbox(
                "Pilih Pasien",
                options=[lbl for _, lbl in options],
                index=next(i for i, (sid, _) in enumerate(options)
                          if sid == st.session_state.selected_patient),
                key="patient_selector",
                label_visibility="collapsed",
            )
            new_sid = next(sid for sid, lbl in options if lbl == selected_label)
            if new_sid != st.session_state.selected_patient:
                st.session_state.selected_patient = new_sid
                st.rerun()

    # Render selected patient
    sid = st.session_state.selected_patient
    result = predictions[sid]

    if not result["success"]:
        features = result["features_all_empty"]
        names = ", ".join(FEATURE_DISPLAY.get(f, f) for f in features)
        render_banner(
            "error",
            f"Pasien {fmt_stay_id(sid)}: Tidak Dapat Diprediksi",
            f"Fitur berikut tidak memiliki data sama sekali: <b>{names}</b>. "
            f"Tambahkan minimal 1 nilai pada salah satu jam untuk dapat memprediksi.",
        )
        return

    render_patient_dashboard(sid, result)

def render_triage_overview(stay_ids: List, predictions: Dict):
    """Multi-patient triage card grid."""
    st.markdown('<div class="section-label">Ringkasan Semua Pasien</div>', unsafe_allow_html=True)

    n_success = sum(1 for sid in stay_ids if predictions[sid]["success"])
    n_failed = len(stay_ids) - n_success

    failed_note = (
        f" ({n_failed} pasien tidak dapat diprediksi karena data tidak lengkap.)"
        if n_failed > 0 else ""
    )

    banner_html = (
        f'<div class="banner banner-info">'
        f'<div style="font-size: 18px;">ⓘ</div>'
        f'<div>'
        f'<div style="font-weight: 700; margin-bottom: 4px;">{len(stay_ids)} Pasien Dimuat</div>'
        f'<div>{n_success} pasien siap dilihat detailnya. Klik kartu pasien untuk melihat '
        f'tren risiko dan kondisi klinis.{failed_note}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(banner_html, unsafe_allow_html=True)

    # Cards in grid (3 per row)
    cols_per_row = 3
    for i in range(0, len(stay_ids), cols_per_row):
        row_sids = stay_ids[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, sid in zip(cols, row_sids):
            with col:
                res = predictions[sid]
                if res["success"]:
                    last = res["trajectory"].iloc[-1]
                    last_prob = last["prob"]
                    last_level = last["risk_level"]
                    n_hours = len(res["trajectory"])
                    peak_prob = res["trajectory"]["prob"].max()
                    peak_hr = int(res["trajectory"].loc[res["trajectory"]["prob"].idxmax(), "hr"])

                    color = risk_color(last_level)

                    st.markdown(f"""
                    <div class="triage-card">
                        <div class="triage-id">PASIEN {fmt_stay_id(sid)}</div>
                        <div class="triage-prob" style="color: {color};">
                            {last_prob*100:.0f}%
                        </div>
                        <div class="triage-status">{risk_badge(last_level)}</div>
                        <div class="triage-meta">
                            {n_hours} jam dimonitor · puncak {peak_prob*100:.0f}% (jam {peak_hr})
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("Lihat Detail →", key=f"detail_{sid}",
                                 use_container_width=True, type="primary"):
                        st.session_state.selected_patient = sid
                        st.session_state.show_overview = False
                        st.rerun()
                else:
                    features = res["features_all_empty"]
                    names = ", ".join(FEATURE_DISPLAY.get(f, f) for f in features[:2])
                    if len(features) > 2:
                        names += f" (+{len(features)-2})"
                    st.markdown(f"""
                    <div class="triage-card" style="opacity: 0.6;">
                        <div class="triage-id">PASIEN {fmt_stay_id(sid)}</div>
                        <div style="font-size: 14px; color: var(--text-muted);
                                    margin: 16px 0 8px 0;">
                            Tidak dapat diprediksi
                        </div>
                        <div class="triage-status">
                            <span class="risk-badge badge-error">— DATA KURANG</span>
                        </div>
                        <div class="triage-meta">
                            Kosong: {names}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

def render_patient_dashboard(sid, result: Dict):
    """Full patient detail dashboard."""
    traj         = result["trajectory"]
    df_imputed   = result["df_imputed"]
    imputed_mask = result["imputed_mask"]
    imp_report   = result["imputation_report"]

    last_row = traj.iloc[-1]
    current_hr    = int(last_row["hr"])
    current_prob  = last_row["prob"]
    current_level = last_row["risk_level"]

    n_high   = (traj["risk_level"] == "TINGGI").sum()
    n_medium = (traj["risk_level"] == "SEDANG").sum()
    n_low    = (traj["risk_level"] == "RENDAH").sum()
    max_prob = traj["prob"].max()
    max_hr   = int(traj.loc[traj["prob"].idxmax(), "hr"])

    # Hitung statistik imputasi untuk indikator
    n_imp = int(imputed_mask.sum().sum())
    n_cells = imputed_mask.size
    pct_imp = (n_imp / n_cells * 100) if n_cells > 0 else 0

    # Patient header
    imp_note = (
        f" · {pct_imp:.0f}% data diisi otomatis" if n_imp > 0 else ""
    )
    st.markdown(f"""
    <div style="margin-bottom: 16px;">
        <div style="font-size: 11px; color: var(--text-muted); letter-spacing: 1px;
                    text-transform: uppercase; font-weight: 600;">
            Pasien
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700;
                    color: var(--text-primary); margin-top: 2px;">
            {fmt_stay_id(sid)}
        </div>
        <div style="font-size: 12.5px; color: var(--text-muted); margin-top: 4px;">
            {len(traj)} jam dimonitor{imp_note} · Sumber: {st.session_state.data_source}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Disclaimer untuk data sangat pendek
    if len(traj) < 3:
        render_banner(
            "warning",
            "Data Masih Sangat Singkat",
            f"Pasien ini baru dimonitor {len(traj)} jam. Prediksi pada data "
            f"yang sangat singkat memiliki keandalan terbatas karena sistem "
            f"belum dapat melihat tren perubahan kondisi pasien.",
        )

    # Pemberitahuan kalau data dipangkas karena terlalu panjang
    if result.get("truncated_pe", False):
        render_banner(
            "info",
            "Data Dipersingkat",
            "Data pasien ini sangat panjang (lebih dari 1.000 jam). "
            "Sistem menampilkan 1.000 jam terakhir yang paling relevan "
            "untuk prediksi kondisi terkini.",
        )

    # Top metrics
    col_a, col_b, col_c, col_d = st.columns([1.4, 1, 1, 1])

    with col_a:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Risiko Saat Ini · Jam {current_hr}</div>
            <div style="margin: 10px 0 6px 0;">{risk_badge(current_level)}</div>
            <div class="metric-value" style="color: {risk_color(current_level)};">
                {current_prob*100:.1f}%
            </div>
            <div class="metric-sub">kemungkinan syok septik</div>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Risiko Tertinggi</div>
            <div class="metric-value" style="color: #ff7e0d;">{max_prob*100:.1f}%</div>
            <div class="metric-sub">pada jam {max_hr}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_c:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Jam Risiko Tinggi</div>
            <div class="metric-value" style="color: var(--red);">{n_high}</div>
            <div class="metric-sub">dari {len(traj)} jam</div>
        </div>
        """, unsafe_allow_html=True)

    with col_d:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Distribusi Status</div>
            <div style="margin-top: 14px; display: flex; justify-content: space-around;
                        font-family: 'JetBrains Mono', monospace; font-size: 15px;">
                <div><span style="color: var(--green); font-weight: 700;">{n_low}</span>
                    <div style="color: var(--text-muted); font-size: 9.5px; margin-top: 2px;
                                letter-spacing: 0.5px;">RENDAH</div></div>
                <div><span style="color: var(--yellow); font-weight: 700;">{n_medium}</span>
                    <div style="color: var(--text-muted); font-size: 9.5px; margin-top: 2px;
                                letter-spacing: 0.5px;">SEDANG</div></div>
                <div><span style="color: var(--red); font-weight: 700;">{n_high}</span>
                    <div style="color: var(--text-muted); font-size: 9.5px; margin-top: 2px;
                                letter-spacing: 0.5px;">TINGGI</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Risk trajectory chart
    st.markdown('<div class="section-label">Tren Risiko Per Jam</div>', unsafe_allow_html=True)
    st.plotly_chart(plot_risk_trajectory(traj, str(sid)),
                    use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        '<div style="font-size: 11.5px; color: var(--text-muted); '
        'margin-top: -8px; margin-bottom: 8px;">'
        'Status risiko: '
        '<span style="color: var(--green); font-weight: 600;">Rendah</span> di bawah 30% · '
        '<span style="color: var(--yellow); font-weight: 600;">Sedang</span> 30–70% · '
        '<span style="color: var(--red); font-weight: 600;">Tinggi</span> di atas 60%'
        '</div>',
        unsafe_allow_html=True,
    )

    # Tabs: Kondisi Pasien | Faktor Utama
    tab_snap, tab_factor = st.tabs(["Kondisi Pasien", "Faktor Utama"])

    with tab_snap:
        latest_imputed = df_imputed.iloc[-1]
        latest_mask    = imputed_mask.iloc[-1]
        render_current_values(latest_imputed, latest_mask, current_hr)

    with tab_factor:
        col_chart, col_text = st.columns([1.2, 1])
        with col_chart:
            shapley_data = result.get("shapley_ranking", [])
            st.plotly_chart(
                plot_top_factors_patient(shapley_data, top_k=5),
                use_container_width=True,
                config={"displayModeBar": False}
            )
        with col_text:
            st.markdown("""
            <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.7;">
            Grafik menunjukkan <b>5 fitur klinis yang paling berpengaruh</b>
            terhadap prediksi risiko pasien ini pada jam terakhir.
            <br><br>
            Nilai yang lebih tinggi berarti fitur tersebut lebih menentukan
            hasil prediksi model untuk pasien ini.
            </div>
            """, unsafe_allow_html=True)

        with st.expander("Lihat semua 21 faktor"):
            rows = []
            total_imp = sum(f["importance"] for f in shapley_data) or 1.0
            for i, f in enumerate(shapley_data, 1):
                display_name = FEATURE_DISPLAY.get(f["feature"], f["feature"])
                pct = f["importance"] / total_imp * 100
                rows.append({
                    "Peringkat":       i,
                    "Faktor":          display_name,
                    "Kontribusi (%)":  f"{pct:.1f}%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True, height=500)

    # Download section
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Unduh hasil prediksi"):
        out_buf = BytesIO()
        with pd.ExcelWriter(out_buf, engine="openpyxl") as w:
            traj_out = traj[["hr", "prob", "risk_level"]].copy()
            traj_out.columns = ["Jam", "Risiko (0-1)", "Status"]
            traj_out["Risiko %"] = (traj["prob"] * 100).round(2)
            traj_out.to_excel(w, sheet_name="prediksi", index=False)
            df_imputed.to_excel(w, sheet_name="data_hasil_pengisian", index=False)

        st.download_button(
            "Unduh hasil prediksi pasien ini (.xlsx)",
            data=out_buf.getvalue(),
            file_name=f"prediksi_pasien_{fmt_stay_id(sid)}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False,
        )

    # Footer disclaimer
    st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════

# Preload model
try:
    load_artifacts()
except Exception as e:
    st.error(f"Gagal load model: {e}")
    st.stop()

render_sidebar()

view = st.session_state.view
if view == "empty":
    view_empty()
elif view == "validate":
    view_validate()
elif view == "impute_preview":
    view_impute_preview()
elif view == "dashboard":
    view_dashboard()
else:
    view_empty()
