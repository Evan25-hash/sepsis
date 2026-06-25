"""
Generate Excel template untuk user upload.
"""

from io import BytesIO
import pandas as pd

from validation import HARD_RANGES, SOFT_RANGES, FEATURE_DISPLAY


def build_template_excel() -> bytes:
    """Return bytes Excel template dengan multiple sheets."""
    feature_cols = list(HARD_RANGES.keys())

    # Sheet 1: patient_data (kolom + 5 baris contoh untuk 1 pasien)
    columns = ["stay_id", "hr"] + feature_cols
    example_rows = []
    for i in range(5):
        row = {"stay_id": "1001", "hr": i}
        for f in feature_cols:
            row[f] = None
        example_rows.append(row)
    template_df = pd.DataFrame(example_rows)

    # Sheet 2: keterangan
    keterangan_rows = []
    keterangan_rows.append({
        "kolom":          "stay_id",
        "deskripsi":      "ID pasien (bisa angka atau teks). Pasien yang sama harus pakai stay_id sama.",
        "satuan":         "-",
        "rentang_valid":  "-",
        "rentang_normal": "-",
    })
    keterangan_rows.append({
        "kolom":          "hr",
        "deskripsi":      "Jam ke berapa di ICU (mulai dari 0), berurutan tanpa lompatan.",
        "satuan":         "jam",
        "rentang_valid":  ">= 0",
        "rentang_normal": "-",
    })
    for feat in feature_cols:
        display_name = FEATURE_DISPLAY.get(feat, feat)
        hard_lo, hard_hi = HARD_RANGES[feat]
        soft_lo, soft_hi, unit = SOFT_RANGES[feat]
        keterangan_rows.append({
            "kolom":          feat,
            "deskripsi":      display_name,
            "satuan":         unit if unit else "-",
            "rentang_valid":  f"{hard_lo} – {hard_hi}",
            "rentang_normal": (f"{soft_lo} – {soft_hi}" if soft_lo != soft_hi
                               else f"~{soft_lo}"),
        })
    keterangan_df = pd.DataFrame(keterangan_rows)

    # Sheet 3: panduan
    panduan_rows = [
        ("Format File",  "Sheet harus bernama 'patient_data' dengan kolom sesuai."),
        ("Multi-Pasien", "Satu file bisa berisi banyak pasien (max 20). Bedakan dengan kolom stay_id."),
        ("Jam (hr)",     "Mulai dari 0 atau angka berapa saja, harus berurutan tanpa lompatan per pasien."),
        ("Nilai Kosong", "Boleh dikosongkan, sistem akan otomatis mengisi. Tapi setiap kolom harus punya minimal 1 nilai."),
        ("Validasi",     "Nilai diluar batas wajar akan ditolak. Lihat sheet 'keterangan' untuk batas."),
        ("Tujuan",       "Sistem akan memberikan estimasi risiko syok septik per jam berdasarkan data."),
        ("Catatan",      "Sistem ini adalah prototipe penelitian."),
    ]
    panduan_df = pd.DataFrame(panduan_rows, columns=["Topik", "Penjelasan"])

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        template_df.to_excel(w, sheet_name="patient_data", index=False)
        keterangan_df.to_excel(w, sheet_name="keterangan", index=False)
        panduan_df.to_excel(w, sheet_name="panduan", index=False)

    return buf.getvalue()


if __name__ == "__main__":
    bytes_data = build_template_excel()
    with open("assets/templates/template.xlsx", "wb") as f:
        f.write(bytes_data)
    print(f"Template generated ({len(bytes_data)} bytes)")
