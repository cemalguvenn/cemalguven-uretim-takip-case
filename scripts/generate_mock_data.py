"""Generate a large, realistic MES mock dataset for stress-testing import + validation.

Mirrors the real production_data.csv structure (18 columns, position-based,
cp1254, MM/DD/YYYY dates) and injects the same family of data-quality issues at
realistic proportions: missing values, sentinel -10, the 350/250 pattern,
out-of-range A/P/Q/OEE, formula mismatches, hatalı>üretilen, zero-production
runs, all-zero idle rows, and one systematic high-P product/station combo.

Usage:
    python scripts/generate_mock_data.py [rows] [output_path]
    # defaults: 60000 rows -> data/production_data_50k.csv
"""
from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta

SEED = 42
START_DATE = date(2025, 9, 1)
DAYS = 120  # ~4 months so volume spreads realistically

STATIONS = ["IMM-2700-1", "IMM-2700-2", "IMM-2700-3", "IMM-4000-1", "IMM-4000-2"]
WORK_CENTER = "INJECTION  EXTERIORS"
SYSTEMIC_PRODUCT = "ICA-2-S-FR-Lower Bumper Unpainted"
SYSTEMIC_STATION = "IMM-4000-2"

PRODUCTS = [
    "V710 BEV/PHEV MIC White Upper", "V710 BEV/PHEV MIC White Lower",
    "V363 BEV Base GOR SUBASSY", "V363 BEV Base MIC Black Upper",
    "U725 Front Bumper Lower", "U725 Rear Bumper Cover", "CX430 Skid Plate",
    "CX430 Lower Grille", "P703 Fender Liner FR", "P703 Fender Liner RR",
    "B920 Rocker Molding LH", "B920 Rocker Molding RH", "L663 Wheel Arch FR",
    "L663 Wheel Arch RR", "J72 Air Deflector", "J72 Splash Shield",
    "U611 Tow Hook Cover", "U611 Sensor Bracket", "MCA-2-S-FR-Lower Bumper Unpainted",
    "P702 Cowl Grille", "P702 Hood Seal", "D544 Lower Valance",
    "D544 Upper Trim", "X590 Underbody Panel", "X590 Diffuser",
    "K131 Side Skirt LH", "K131 Side Skirt RH", SYSTEMIC_PRODUCT,
]

# Garbled-but-faithful Turkish header (import is position-based; content ignored).
HEADER = [
    "record_id", "Tarih", "İş Emri No", "İş Merkezi No", "İşmerkezi Adı",
    "İş İstasyon Adı", "Stok Adı", "Vardiya", "A (Kullanılırlık)", "P (Performans)",
    "Q (Kalite)", "OEE", "Çalışma Süresi", "Duruş Süresi", "Planlı Duruş Süresi",
    "Plansız Duruş Süresi", "Üretilen Miktar", "Hatalı Üretilen Miktar",
]

rng = random.Random(SEED)


def f2(x: float) -> str:
    return f"{round(x, 2)}"


def gen_row(rid: int) -> list[str]:
    d = START_DATE + timedelta(days=rng.randint(0, DAYS - 1))
    tarih = f"{d.month}/{d.day}/{d.year}"
    job = f"302{rng.randint(1000000, 9999999)}"
    station = rng.choice(STATIONS)
    product = rng.choice(PRODUCTS)
    shift = rng.choice([1, 2, 3])

    # ----- base physically-consistent values -----
    calisma = round(rng.uniform(180, 470), 2)
    plansiz = round(rng.uniform(0, 120), 2)
    planli = round(rng.uniform(0, 60), 2)
    durus = round(planli + plansiz, 2)
    A = calisma / (calisma + plansiz) * 100 if (calisma + plansiz) else 0.0
    P = rng.uniform(78, 112)
    uretilen = int(calisma * rng.uniform(0.8, 3.5))
    hatali = int(uretilen * rng.uniform(0, 0.03))
    Q = (uretilen - hatali) / uretilen * 100 if uretilen else 0.0
    OEE = A * P * Q / 10000

    r = rng.random()

    # ----- inject anomalies (roughly matching the real file's mix) -----
    # 1) all-zero idle rows (~18%)
    if r < 0.18:
        A = P = Q = OEE = 0.0
        uretilen = 0
        hatali = 0
        if rng.random() < 0.3:  # some idle rows still ran a while
            calisma = round(rng.uniform(60, 200), 2)
    # 2) hatalı > üretilen (~8%) — impossible
    elif r < 0.26:
        uretilen = rng.randint(1, 90)
        hatali = uretilen + rng.randint(1, 80)
        Q = (uretilen - hatali) / uretilen * 100
        OEE = A * P * Q / 10000
    # 3) systematic combo: this product on this station always has huge P
    elif product == SYSTEMIC_PRODUCT or (station == SYSTEMIC_STATION and rng.random() < 0.5):
        product = SYSTEMIC_PRODUCT
        station = SYSTEMIC_STATION
        P = rng.uniform(3000, 350000)
        OEE = A * P * Q / 10000
    # 4) sentinel 350/250 pattern (~0.5%)
    elif r < 0.265:
        calisma, durus, planli, plansiz = 350.0, 250.0, 0.0, 0.0
    # 5) zero production despite long run (~3%)
    elif r < 0.295:
        uretilen = 0
        hatali = 0
        Q = 0.0
        OEE = 0.0
    # 6) Q out of range (~0.3%)
    elif r < 0.298:
        Q = rng.choice([120.0, -3.0, 130.0])
        OEE = A * P * 100 / 10000  # MES assumed Q=100 -> OEE formula mismatch too
    # 7) stop-time mismatch (~0.4%)
    elif r < 0.302:
        durus = round(planli + plansiz + rng.uniform(20, 120), 2)

    cells = {
        0: str(rid), 1: tarih, 2: job, 3: WORK_CENTER, 4: WORK_CENTER,
        5: station, 6: product, 7: str(shift),
        8: f2(A), 9: f2(P), 10: f2(Q), 11: f2(OEE),
        12: f2(calisma), 13: f2(durus), 14: f2(planli), 15: f2(plansiz),
        16: str(uretilen), 17: str(hatali),
    }

    # ----- field-level injections (blanks & sentinels) -----
    if rng.random() < 0.059:
        cells[6] = ""                       # missing product
    if rng.random() < 0.005:
        cells[7] = ""                       # missing shift
    if rng.random() < 0.005:
        cells[2] = ""                       # missing job order
    if rng.random() < 0.006:
        cells[3] = ""                       # missing work center
    if rng.random() < 0.003:
        cells[12] = ""                      # missing work time
    if rng.random() < 0.001:
        cells[13] = ""                      # missing stop time
    if rng.random() < 0.0005:
        cells[5] = ""                       # missing station
    if rng.random() < 0.002:
        cells[7] = str(rng.choice([0, 4, 9]))  # invalid shift value
    if rng.random() < 0.004:                # sentinel -10
        cells[rng.choice([12, 16, 17])] = "-10"

    return [cells[i] for i in range(18)]


def main() -> None:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
    out = sys.argv[2] if len(sys.argv) > 2 else "data/production_data_50k.csv"
    with open(out, "w", encoding="cp1254", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for rid in range(1, rows + 1):
            w.writerow(gen_row(rid))
    print(f"Wrote {rows} rows -> {out} (cp1254)")


if __name__ == "__main__":
    main()
