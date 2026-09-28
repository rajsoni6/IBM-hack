#!/usr/bin/env python3
"""
scripts/generate_synthetic_data.py
===================================
Generates a self-consistent synthetic investigation / demo dataset for the
Cyber Fraud Network Analyzer.

Output: data/sample/*.json   (14 files)
Extra:  data/ml/             (empty directory placeholder for Part 7)

This script will NEVER touch the existing ML training CSVs that live under
src/data/  (accounts, transactions, fraud_cases).

Fraud patterns embedded:
  P1  SIM-swap sequence
  P2  Mule-account network
  P3  Transaction layering
  P4  Shared-device cluster
  P5  Shared-SIM cluster
  P6  Communication hub
  P7  Rapid multi-hop fund movement
  P8  Normal legitimate activity

Run:
  cd cyber-fraud-network-analyzer   (project root)
  python scripts/generate_synthetic_data.py
"""

from __future__ import annotations

import json
import random
import string
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── reproducibility ──────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)

# ── output paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR   = PROJECT_ROOT / "data" / "sample"
ML_DIR       = PROJECT_ROOT / "data" / "ml"

# ── helper utilities ─────────────────────────────────────────────────────────

def uid(prefix: str = "") -> str:
    s = uuid.uuid4().hex[:12]
    return f"{prefix}_{s}" if prefix else s

def ts(base: datetime, offset_minutes: float = 0) -> str:
    return (base + timedelta(minutes=offset_minutes)).isoformat() + "Z"

def rdate(start: str = "2023-01-01", end: str = "2024-06-30") -> str:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end,   "%Y-%m-%d")
    return (s + timedelta(days=random.randint(0, (e - s).days))).strftime("%Y-%m-%d")

def save(name: str, data: list | dict) -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLE_DIR / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    count = len(data) if isinstance(data, list) else 1
    print(f"  [+] {name:<30} {count:>5} records")

def pick(seq):
    return random.choice(seq)

def wt_pick(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]

# ── name / address pools ─────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Aditi","Akash","Alok","Amit","Ananya","Anjali","Ankit","Anuj","Arjun",
    "Arun","Asha","Ashish","Avinash","Deepak","Deepika","Divya","Gaurav","Geeta","Harish",
    "Isha","Jaya","Karan","Kavita","Kedar","Krishna","Lata","Mahesh","Manish","Meena",
    "Mohan","Mukesh","Naina","Neha","Nikhil","Nilesh","Pankaj","Pooja","Pradeep","Priya",
    "Rahul","Rajesh","Rakesh","Ramesh","Reema","Rohit","Sachin","Sangeeta","Sanjay","Sanket",
]
LAST_NAMES = [
    "Agarwal","Bhat","Chaudhary","Desai","Doshi","Garg","Ghosh","Gupta","Iyer","Jain",
    "Joshi","Kapoor","Kaur","Khan","Kumar","Mehta","Mishra","Nair","Patel","Patil",
    "Pillai","Rao","Rathod","Reddy","Saxena","Shah","Sharma","Singh","Sinha","Tiwari",
    "Trivedi","Varma","Verma","Yadav",
]
CITIES = [
    "Mumbai","Delhi","Bengaluru","Hyderabad","Chennai","Kolkata","Pune","Ahmedabad",
    "Jaipur","Surat","Lucknow","Kanpur","Nagpur","Indore","Thane","Bhopal","Patna",
    "Vadodara","Ludhiana","Agra",
]
STATES = {
    "Mumbai":"Maharashtra","Delhi":"Delhi","Bengaluru":"Karnataka","Hyderabad":"Telangana",
    "Chennai":"Tamil Nadu","Kolkata":"West Bengal","Pune":"Maharashtra","Ahmedabad":"Gujarat",
    "Jaipur":"Rajasthan","Surat":"Gujarat","Lucknow":"Uttar Pradesh","Kanpur":"Uttar Pradesh",
    "Nagpur":"Maharashtra","Indore":"Madhya Pradesh","Thane":"Maharashtra","Bhopal":"Madhya Pradesh",
    "Patna":"Bihar","Vadodara":"Gujarat","Ludhiana":"Punjab","Agra":"Uttar Pradesh",
}
BANKS = ["SBI","HDFC","ICICI","Axis","PNB","BOB","Kotak","Canara","IDBI","Yes Bank",
         "IndusInd","Union Bank","UCO Bank","Indian Bank","Federal Bank"]
TELECOM_OPS = ["Jio","Airtel","Vi","BSNL"]
DEVICE_BRANDS = ["Samsung","Xiaomi","Realme","OnePlus","Vivo","Oppo","Apple","Nokia","Motorola"]
DEVICE_MODELS = {
    "Samsung": ["Galaxy A52","Galaxy M31","Galaxy S21","Galaxy A23","Galaxy F41"],
    "Xiaomi":  ["Redmi Note 10","Redmi 9","Mi 11X","POCO X3","Redmi 9A"],
    "Realme":  ["Realme 8","Realme Narzo 30","Realme 7","Realme C25","Realme GT"],
    "OnePlus": ["OnePlus 9R","OnePlus Nord CE","OnePlus 8T","OnePlus Nord 2","OnePlus 9"],
    "Vivo":    ["Vivo V21","Vivo Y73","Vivo V20","Vivo Y51","Vivo X60"],
    "Oppo":    ["Oppo A74","Oppo F19","Oppo Reno5","Oppo A54","Oppo A16"],
    "Apple":   ["iPhone 13","iPhone 12","iPhone SE 2022","iPhone 11","iPhone XR"],
    "Nokia":   ["Nokia 5.4","Nokia 3.4","Nokia G20","Nokia 2.4","Nokia 8.3"],
    "Motorola":["Moto G60","Moto G40","Moto E7","Moto G30","Moto G Power"],
}
UPI_SUFFIXES = ["@okaxis","@oksbi","@okicici","@okhdfcbank","@ybl","@ibl","@paytm","@upi"]
EVIDENCE_TYPES = ["call_record","transaction_log","device_fingerprint","location_ping",
                  "document","photograph","witness_statement","bank_statement"]

# ── BASE TIME ─────────────────────────────────────────────────────────────────
BASE_DT = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOCATIONS  (50)
# ═════════════════════════════════════════════════════════════════════════════
def gen_locations(n: int = 50) -> list[dict]:
    locs = []
    for i in range(n):
        city = pick(CITIES)
        lat  = round(random.uniform(8.0, 35.0), 6)
        lon  = round(random.uniform(68.0, 97.0), 6)
        locs.append({
            "id":         f"loc_{i+1:03d}",
            "city":       city,
            "state":      STATES[city],
            "pincode":    str(random.randint(100000, 999999)),
            "address":    f"{random.randint(1,999)}, {pick(['Main Rd','MG Road','Station Rd','Ring Rd','NH-8'])}, {city}",
            "lat":        lat,
            "lon":        lon,
            "created_at": rdate(),
        })
    return locs


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — PERSONS  (50)
# ═════════════════════════════════════════════════════════════════════════════
def gen_persons(n: int = 50, locations: list[dict] = []) -> list[dict]:
    loc_ids = [l["id"] for l in locations]
    persons = []
    for i in range(n):
        fn, ln = pick(FIRST_NAMES), pick(LAST_NAMES)
        dob_year = random.randint(1965, 2000)
        tag = wt_pick(
            ["suspect","person_of_interest","witness","victim","associate","unknown"],
            [20, 20, 10, 15, 20, 15],
        )
        persons.append({
            "id":           f"per_{i+1:03d}",
            "name":         f"{fn} {ln}",
            "dob":          f"{dob_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "gender":       pick(["M","F","M","M","F"]),
            "aadhaar_hash": uuid.uuid4().hex,   # fake hash, never real Aadhaar
            "pan_hash":     uuid.uuid4().hex[:10].upper(),
            "occupation":   pick(["Business","Service","Student","Retired","Farmer","Unemployed","Freelancer"]),
            "risk_score":   round(random.uniform(0.1, 0.95), 3),
            "tag":          tag,
            "home_location": pick(loc_ids) if loc_ids else None,
            "created_at":   rdate(),
        })
    return persons


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — PHONES  (100)
# ═════════════════════════════════════════════════════════════════════════════
def gen_phones(n: int = 100, persons: list[dict] = []) -> list[dict]:
    per_ids = [p["id"] for p in persons]
    phones  = []
    used_nums: set[str] = set()
    for i in range(n):
        num = "9" + "".join(random.choices(string.digits, k=9))
        while num in used_nums:
            num = "9" + "".join(random.choices(string.digits, k=9))
        used_nums.add(num)
        phones.append({
            "id":          f"ph_{i+1:03d}",
            "number":      num,
            "operator":    pick(TELECOM_OPS),
            "circle":      pick(CITIES),
            "registered_to": pick(per_ids) if per_ids else None,
            "is_active":   wt_pick([True, False], [85, 15]),
            "created_at":  rdate(),
        })
    return phones


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — SIM RECORDS  (50)
# ═════════════════════════════════════════════════════════════════════════════
def gen_sims(n: int = 50, phones: list[dict] = [], persons: list[dict] = []) -> list[dict]:
    ph_ids  = [p["id"] for p in phones]
    per_ids = [p["id"] for p in persons]
    sims    = []
    for i in range(n):
        issue_date = rdate("2022-01-01", "2024-01-01")
        sims.append({
            "id":            f"sim_{i+1:03d}",
            "iccid":         "89914" + "".join(random.choices(string.digits, k=15)),
            "imsi":          "404" + "".join(random.choices(string.digits, k=12)),
            "operator":      pick(TELECOM_OPS),
            "phone_id":      pick(ph_ids) if ph_ids else None,
            "registered_to": pick(per_ids) if per_ids else None,
            "issue_date":    issue_date,
            "kyc_verified":  wt_pick([True, False], [70, 30]),
            "swap_count":    wt_pick([0, 1, 2, 3, 4], [60, 20, 10, 6, 4]),
            "last_swap_date": rdate("2023-06-01", "2024-06-01") if random.random() < 0.35 else None,
            "created_at":    issue_date,
        })
    return sims


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — DEVICES  (50)
# ═════════════════════════════════════════════════════════════════════════════
def gen_devices(n: int = 50, persons: list[dict] = []) -> list[dict]:
    per_ids = [p["id"] for p in persons]
    devices = []
    used_imei: set[str] = set()
    for i in range(n):
        imei = "35" + "".join(random.choices(string.digits, k=13))
        while imei in used_imei:
            imei = "35" + "".join(random.choices(string.digits, k=13))
        used_imei.add(imei)
        brand = pick(DEVICE_BRANDS)
        model = pick(DEVICE_MODELS[brand])
        devices.append({
            "id":           f"dev_{i+1:03d}",
            "imei":         imei,
            "brand":        brand,
            "model":        model,
            "os":           pick(["Android 12","Android 13","Android 11","iOS 16","iOS 17","Android 10"]),
            "registered_to": pick(per_ids) if per_ids else None,
            "first_seen":   rdate("2022-01-01", "2023-12-31"),
            "last_seen":    rdate("2024-01-01", "2024-06-30"),
            "risk_score":   round(random.uniform(0.05, 0.9), 3),
            "created_at":   rdate("2022-01-01", "2023-12-31"),
        })
    return devices


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — BANK ACCOUNTS  (100)
# ═════════════════════════════════════════════════════════════════════════════
def gen_bank_accounts(n: int = 100, persons: list[dict] = [],
                      locations: list[dict] = []) -> list[dict]:
    per_ids = [p["id"] for p in persons]
    loc_ids = [l["id"] for l in locations]
    accs    = []
    used_acc: set[str] = set()
    for i in range(n):
        acn = "".join(random.choices(string.digits, k=12))
        while acn in used_acc:
            acn = "".join(random.choices(string.digits, k=12))
        used_acc.add(acn)
        bank = pick(BANKS)
        accs.append({
            "id":            f"acc_{i+1:03d}",
            "account_number": acn,
            "bank":          bank,
            "ifsc":          bank[:4].upper() + "0" + "".join(random.choices(string.digits, k=6)),
            "account_type":  pick(["savings","current","savings","savings","joint"]),
            "holder_id":     pick(per_ids) if per_ids else None,
            "balance":       round(random.uniform(500, 250000), 2),
            "opened_date":   rdate("2018-01-01", "2023-12-31"),
            "is_frozen":     wt_pick([False, True], [85, 15]),
            "kyc_status":    wt_pick(["verified","pending","failed"], [72, 18, 10]),
            "branch_location": pick(loc_ids) if loc_ids else None,
            "risk_score":    round(random.uniform(0.05, 0.95), 3),
            "created_at":    rdate("2018-01-01", "2023-12-31"),
        })
    return accs


# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 — UPI IDs  (75)
# ═════════════════════════════════════════════════════════════════════════════
def gen_upi_ids(n: int = 75, persons: list[dict] = [],
                bank_accounts: list[dict] = []) -> list[dict]:
    per_ids = [p["id"] for p in persons]
    acc_ids = [a["id"] for a in bank_accounts]
    upis    = []
    for i in range(n):
        handle = pick(FIRST_NAMES).lower() + str(random.randint(1, 9999))
        suffix = pick(UPI_SUFFIXES)
        upis.append({
            "id":          f"upi_{i+1:03d}",
            "vpa":         handle + suffix,
            "registered_to": pick(per_ids) if per_ids else None,
            "linked_account": pick(acc_ids) if acc_ids else None,
            "is_active":   wt_pick([True, False], [82, 18]),
            "txn_count":   random.randint(0, 500),
            "created_at":  rdate("2020-01-01", "2024-03-01"),
        })
    return upis


# ═════════════════════════════════════════════════════════════════════════════
# STEP 8 — VICTIMS  (50)
# ═════════════════════════════════════════════════════════════════════════════
def gen_victims(n: int = 50, persons: list[dict] = [],
                bank_accounts: list[dict] = [],
                phones: list[dict] = []) -> list[dict]:
    per_ids = [p["id"] for p in persons]
    acc_ids = [a["id"] for a in bank_accounts]
    ph_ids  = [p["id"] for p in phones]
    victims = []
    for i in range(n):
        loss = round(random.uniform(2000, 500000), 2)
        victims.append({
            "id":               f"vic_{i+1:03d}",
            "person_id":        pick(per_ids) if per_ids else None,
            "complaint_number": f"CMP{random.randint(10000,99999)}",
            "fraud_type":       pick(["UPI fraud","SIM swap","phishing","OTP fraud",
                                      "fake investment","romance scam","job fraud","lottery fraud"]),
            "loss_amount":      loss,
            "currency":         "INR",
            "incident_date":    rdate("2023-06-01", "2024-06-01"),
            "reported_date":    rdate("2023-06-01", "2024-06-30"),
            "police_station":   pick(CITIES) + " PS",
            "fir_number":       f"FIR/{random.randint(1,999)}/{random.randint(2023,2024)}",
            "status":           pick(["open","under_investigation","chargesheeted","closed"]),
            "victim_account":   pick(acc_ids) if acc_ids else None,
            "victim_phone":     pick(ph_ids)  if ph_ids  else None,
            "recovery_amount":  round(loss * random.uniform(0, 0.4), 2),
            "created_at":       rdate("2023-06-01", "2024-06-30"),
        })
    return victims


# ═════════════════════════════════════════════════════════════════════════════
# STEP 9 — CASES  (20)
# ═════════════════════════════════════════════════════════════════════════════
CASE_DESCRIPTIONS = [
    ("SIM swap attack on victim UPI accounts",                     "P1"),
    ("Mule account network draining victim funds",                  "P2"),
    ("Layered fund transfers to obscure origin",                    "P3"),
    ("Multiple accounts accessed from single device",               "P4"),
    ("Multiple accounts controlled via same SIM",                   "P5"),
    ("Central phone coordinating fraud network calls",              "P6"),
    ("Rapid multi-hop fund movement before freeze",                 "P7"),
    ("Routine investigation — low risk baseline",                   "P8"),
    ("OTP interception via SIM swap",                               "P1"),
    ("Smurfing: breaking large sum into small transfers",           "P3"),
    ("Device cluster linked to 12 accounts",                        "P4"),
    ("Communication hub directing 8 mule accounts",                 "P6"),
    ("Investment fraud with mule network payout",                   "P2"),
    ("UPI fraud via phishing link",                                 "P8"),
    ("Rapid hop: ₹8L moved in 4 hours across 6 accounts",          "P7"),
    ("SIM swap + UPI takeover dual pattern",                       "P1"),
    ("Shared-SIM operation: 5 users one SIM",                      "P5"),
    ("Transaction layering + mule network combo",                   "P2"),
    ("Job fraud with advance fee collection",                       "P8"),
    ("Romance scam with layered crypto-to-bank transfers",          "P3"),
]

FRAUD_PATTERN_MAP = {
    "P1": "sim_swap",
    "P2": "mule_network",
    "P3": "transaction_layering",
    "P4": "shared_device",
    "P5": "shared_sim",
    "P6": "communication_hub",
    "P7": "rapid_multi_hop",
    "P8": "legitimate",
}

def gen_cases(victims: list[dict] = []) -> list[dict]:
    vic_ids = [v["id"] for v in victims]
    cases   = []
    for i, (desc, pattern_code) in enumerate(CASE_DESCRIPTIONS):
        severity = wt_pick(["critical","high","medium","low"],
                           [25, 30, 30, 15] if pattern_code != "P8" else [0, 5, 40, 55])
        loss = round(random.uniform(10000, 2000000), 2)
        cases.append({
            "id":             f"case_{i+1:03d}",
            "title":          desc,
            "fraud_pattern":  FRAUD_PATTERN_MAP[pattern_code],
            "pattern_code":   pattern_code,
            "severity":       severity,
            "status":         pick(["open","under_investigation","closed","chargesheeted"]),
            "total_loss_inr": loss,
            "victim_ids":     random.sample(vic_ids, min(random.randint(1,4), len(vic_ids))),
            "assigned_to":    pick(["IO-Sharma","IO-Gupta","IO-Reddy","IO-Patel","IO-Singh","IO-Khan"]),
            "opened_date":    rdate("2023-07-01", "2024-04-01"),
            "last_updated":   rdate("2024-04-01", "2024-06-30"),
            "jurisdiction":   pick(CITIES),
            "created_at":     rdate("2023-07-01", "2024-04-01"),
        })
    return cases


# ═════════════════════════════════════════════════════════════════════════════
# STEP 10 — TRANSACTIONS  (300)
# Weave fraud patterns into the transaction graph.
# ═════════════════════════════════════════════════════════════════════════════
TX_METHODS = ["NEFT","IMPS","UPI","RTGS","NACH","Cheque","Cash","IMPS","UPI","UPI"]
TX_NARRATIONS = [
    "Fund transfer","Payment received","Online purchase","Salary credit",
    "EMI debit","Insurance premium","Utility bill payment","Recharge",
    "Dividend credit","Rent payment","Loan disbursement","Commission",
    "Investment redemption","Gift","Personal transfer",
]

def gen_transactions(
    n_total: int,
    bank_accounts: list[dict],
    upi_ids:        list[dict],
    cases:          list[dict],
    persons:        list[dict],
) -> list[dict]:
    acc_ids  = [a["id"] for a in bank_accounts]
    upi_list = [u["id"] for u in upi_ids]
    case_ids = [c["id"] for c in cases]
    per_ids  = [p["id"] for p in persons]

    txns: list[dict] = []
    idx  = [0]  # mutable counter

    def make_txn(src, dst, amount, dt: datetime, method, narration,
                 pattern: str, case_id: str | None, risk: float,
                 upi_src=None, upi_dst=None, flagged=False) -> dict:
        idx[0] += 1
        return {
            "id":            f"txn_{idx[0]:04d}",
            "src_account":   src,
            "dst_account":   dst,
            "src_upi":       upi_src,
            "dst_upi":       upi_dst,
            "amount":        round(amount, 2),
            "currency":      "INR",
            "method":        method,
            "narration":     narration,
            "timestamp":     dt.isoformat() + "Z",
            "pattern":       pattern,
            "case_id":       case_id,
            "risk_score":    round(risk, 3),
            "flagged":       flagged,
            "created_at":    dt.isoformat() + "Z",
        }

    # ── P7: Rapid multi-hop (case_007, case_015) ──────────────────────────
    # ₹8 lakh moved through 6 accounts in 4 hours
    hop_accounts = random.sample(acc_ids, 6)
    hop_start    = BASE_DT + timedelta(days=10)
    hop_amount   = 800000
    for hop in range(5):
        t = hop_start + timedelta(minutes=hop * 45)
        txns.append(make_txn(
            hop_accounts[hop], hop_accounts[hop+1],
            hop_amount * random.uniform(0.88, 0.97),
            t, "IMPS", "Fund transfer",
            "rapid_multi_hop", pick(["case_007","case_015"]), 0.91, flagged=True,
        ))

    # ── P3: Transaction layering (case_003, case_010, case_020) ───────────
    layer_src  = pick(acc_ids)
    layer_pool = random.sample([a for a in acc_ids if a != layer_src], 8)
    layer_base = BASE_DT + timedelta(days=5)
    big_amount = random.uniform(300000, 900000)
    # Placement
    for j in range(3):
        txns.append(make_txn(
            layer_src, layer_pool[j],
            big_amount / 3 * random.uniform(0.95, 1.05),
            layer_base + timedelta(hours=j * 2), "NEFT", "Fund transfer",
            "transaction_layering", pick(["case_003","case_010","case_020"]), 0.78, flagged=True,
        ))
    # Layering
    for j in range(3, 6):
        txns.append(make_txn(
            layer_pool[j-3], layer_pool[j],
            big_amount / 3 * random.uniform(0.7, 0.9),
            layer_base + timedelta(hours=8 + j), "IMPS", "Commission",
            "transaction_layering", pick(["case_003","case_010","case_020"]), 0.82, flagged=True,
        ))
    # Integration
    for j in range(6, 8):
        txns.append(make_txn(
            layer_pool[j-3], pick([a for a in acc_ids if a not in layer_pool]),
            big_amount / 4 * random.uniform(0.5, 0.7),
            layer_base + timedelta(hours=20 + j), "UPI", "Investment redemption",
            "transaction_layering", pick(["case_003","case_010","case_020"]), 0.85, flagged=True,
        ))

    # ── P2: Mule network (case_002, case_013, case_018) ───────────────────
    mule_src   = pick(acc_ids)
    mule_accts = random.sample([a for a in acc_ids if a != mule_src], 7)
    mule_base  = BASE_DT + timedelta(days=3)
    mule_total = random.uniform(150000, 600000)
    for j, mule in enumerate(mule_accts):
        slice_amt = mule_total / len(mule_accts) * random.uniform(0.8, 1.2)
        txns.append(make_txn(
            mule_src, mule,
            slice_amt,
            mule_base + timedelta(hours=j * 3), pick(["UPI","IMPS"]),
            pick(["Gift","Personal transfer"]),
            "mule_network", pick(["case_002","case_013","case_018"]), 0.87, flagged=True,
        ))
    # Mules cash out
    for mule in mule_accts[:4]:
        txns.append(make_txn(
            mule, pick([a for a in acc_ids if a != mule]),
            random.uniform(10000, 80000),
            mule_base + timedelta(hours=random.randint(6, 48)), "Cash",
            "Fund transfer",
            "mule_network", pick(["case_002","case_013","case_018"]), 0.88, flagged=True,
        ))

    # ── P1: SIM-swap victim transactions ──────────────────────────────────
    # Victim accounts drained shortly after swap
    sim_victim_accts  = random.sample(acc_ids, 4)
    sim_suspect_accts = random.sample([a for a in acc_ids if a not in sim_victim_accts], 4)
    sim_base = BASE_DT + timedelta(days=2)
    for j in range(4):
        drain_amt = random.uniform(20000, 200000)
        txns.append(make_txn(
            sim_victim_accts[j], sim_suspect_accts[j],
            drain_amt,
            sim_base + timedelta(minutes=j * 20 + random.uniform(1, 15)),
            "UPI", "UPI transfer",
            "sim_swap", pick(["case_001","case_009","case_016"]), 0.94, flagged=True,
        ))

    # ── P8: Normal legitimate transactions ────────────────────────────────
    legit_count = 0
    legit_target = 200
    while legit_count < legit_target:
        src = pick(acc_ids)
        dst = pick([a for a in acc_ids if a != src])
        amt = random.uniform(100, 50000)
        days_offset = random.uniform(0, 150)
        upi_s = pick(upi_list) if random.random() < 0.4 else None
        upi_d = pick(upi_list) if random.random() < 0.4 else None
        txns.append(make_txn(
            src, dst, amt,
            BASE_DT + timedelta(days=days_offset, minutes=random.uniform(0, 1440)),
            pick(TX_METHODS), pick(TX_NARRATIONS),
            "legitimate", None, round(random.uniform(0.02, 0.35), 3),
            upi_src=upi_s, upi_dst=upi_d,
        ))
        legit_count += 1

    # Fill remaining with mixed flagged
    while len(txns) < n_total:
        src = pick(acc_ids)
        dst = pick([a for a in acc_ids if a != src])
        pat = pick(["mule_network","transaction_layering","rapid_multi_hop",
                    "sim_swap","shared_device"])
        flagged = random.random() > 0.5
        txns.append(make_txn(
            src, dst,
            random.uniform(5000, 300000),
            BASE_DT + timedelta(days=random.uniform(0, 150), minutes=random.uniform(0, 1440)),
            pick(TX_METHODS), pick(TX_NARRATIONS),
            pat, pick(case_ids) if flagged else None,
            round(random.uniform(0.4, 0.95), 3) if flagged else round(random.uniform(0.1, 0.4), 3),
            flagged=flagged,
        ))

    return txns[:n_total]


# ═════════════════════════════════════════════════════════════════════════════
# STEP 11 — CALL RECORDS  (100)
# P6: communication hub + P1: SIM-swap coordination
# ═════════════════════════════════════════════════════════════════════════════
def gen_call_records(n: int = 100, phones: list[dict] = [],
                     cases: list[dict] = []) -> list[dict]:
    ph_ids   = [p["id"] for p in phones]
    case_ids = [c["id"] for c in cases]
    calls    = []

    # P6 hub — one phone calls many
    hub_phone   = ph_ids[0]
    spoke_phones = ph_ids[1:9]
    hub_base     = BASE_DT + timedelta(days=1)
    for j, spoke in enumerate(spoke_phones):
        calls.append({
            "id":          f"call_{len(calls)+1:04d}",
            "caller_id":   hub_phone,
            "receiver_id": spoke,
            "duration_sec": random.randint(30, 360),
            "call_type":   "outgoing",
            "timestamp":   (hub_base + timedelta(hours=j * 2)).isoformat() + "Z",
            "cell_tower":  pick(CITIES),
            "pattern":     "communication_hub",
            "case_id":     pick(["case_006","case_012"]),
            "risk_score":  round(random.uniform(0.65, 0.92), 3),
            "flagged":     True,
            "created_at":  (hub_base + timedelta(hours=j * 2)).isoformat() + "Z",
        })

    # P1 SIM-swap coordination calls
    swap_base = BASE_DT + timedelta(days=2)
    for j in range(6):
        caller   = pick(ph_ids[5:20])
        receiver = pick(ph_ids[20:35])
        calls.append({
            "id":          f"call_{len(calls)+1:04d}",
            "caller_id":   caller,
            "receiver_id": receiver,
            "duration_sec": random.randint(10, 90),
            "call_type":   pick(["outgoing","incoming"]),
            "timestamp":   (swap_base + timedelta(minutes=j * 15)).isoformat() + "Z",
            "cell_tower":  pick(CITIES),
            "pattern":     "sim_swap",
            "case_id":     pick(["case_001","case_009","case_016"]),
            "risk_score":  round(random.uniform(0.75, 0.95), 3),
            "flagged":     True,
            "created_at":  (swap_base + timedelta(minutes=j * 15)).isoformat() + "Z",
        })

    # Remaining — normal / low-risk
    while len(calls) < n:
        caller   = pick(ph_ids)
        receiver = pick([p for p in ph_ids if p != caller])
        days_off = random.uniform(0, 150)
        calls.append({
            "id":          f"call_{len(calls)+1:04d}",
            "caller_id":   caller,
            "receiver_id": receiver,
            "duration_sec": random.randint(5, 600),
            "call_type":   pick(["outgoing","incoming","missed"]),
            "timestamp":   (BASE_DT + timedelta(days=days_off, minutes=random.uniform(0,1440))).isoformat() + "Z",
            "cell_tower":  pick(CITIES),
            "pattern":     "legitimate",
            "case_id":     None,
            "risk_score":  round(random.uniform(0.02, 0.30), 3),
            "flagged":     False,
            "created_at":  (BASE_DT + timedelta(days=days_off)).isoformat() + "Z",
        })

    return calls[:n]


# ═════════════════════════════════════════════════════════════════════════════
# STEP 12 — EVIDENCE  (one or more per case)
# ═════════════════════════════════════════════════════════════════════════════
def gen_evidence(cases: list[dict]) -> list[dict]:
    evs  = []
    for case in cases:
        n_ev = random.randint(1, 5)
        for j in range(n_ev):
            etype = pick(EVIDENCE_TYPES)
            evs.append({
                "id":           f"ev_{len(evs)+1:04d}",
                "case_id":      case["id"],
                "type":         etype,
                "description":  f"{etype.replace('_',' ').title()} collected for {case['title']}",
                "file_path":    f"data/evidence/{case['id']}_{j+1:02d}_{etype}.json",
                "collected_by": pick(["IO-Sharma","IO-Gupta","IO-Reddy","IO-Patel"]),
                "collected_at": rdate("2024-01-01", "2024-06-30"),
                "hash_sha256":  uuid.uuid4().hex * 2,   # fake SHA256
                "is_verified":  wt_pick([True, False], [65, 35]),
                "created_at":   rdate("2024-01-01", "2024-06-30"),
            })
    return evs


# ═════════════════════════════════════════════════════════════════════════════
# STEP 13 — ENTITIES  (unified view of all entity types)
# ═════════════════════════════════════════════════════════════════════════════
def gen_entities(
    persons, phones, sims, devices, bank_accounts, upi_ids
) -> list[dict]:
    entities: list[dict] = []

    for p in persons:
        entities.append({"id": p["id"], "type": "person",       "label": p["name"],
                          "risk_score": p["risk_score"],          "source_id": p["id"]})
    for p in phones:
        entities.append({"id": p["id"], "type": "phone",        "label": p["number"],
                          "risk_score": round(random.uniform(0.05,0.85),3), "source_id": p["id"]})
    for s in sims:
        entities.append({"id": s["id"], "type": "sim",          "label": s["iccid"][-8:],
                          "risk_score": round(0.3 + s.get("swap_count",0)*0.1, 3), "source_id": s["id"]})
    for d in devices:
        entities.append({"id": d["id"], "type": "device",       "label": f"{d['brand']} {d['model']}",
                          "risk_score": d["risk_score"],          "source_id": d["id"]})
    for a in bank_accounts:
        entities.append({"id": a["id"], "type": "bank_account", "label": f"***{a['account_number'][-4:]} {a['bank']}",
                          "risk_score": a["risk_score"],          "source_id": a["id"]})
    for u in upi_ids:
        entities.append({"id": u["id"], "type": "upi",          "label": u["vpa"],
                          "risk_score": round(random.uniform(0.05,0.85),3), "source_id": u["id"]})
    return entities


# ═════════════════════════════════════════════════════════════════════════════
# STEP 14 — RELATIONSHIPS
# ═════════════════════════════════════════════════════════════════════════════
REL_TYPES = [
    "owns","uses","linked_to","transferred_to","called","registered_on",
    "associated_with","swapped_sim","controls","reported_by",
]

def gen_relationships(
    persons, phones, sims, devices, bank_accounts, upi_ids,
    transactions, call_records, cases, victims,
) -> list[dict]:
    rels: list[dict] = []
    rel_set: set[tuple] = set()

    def add(src, dst, rel_type, case_id=None, confidence=None, pattern=None):
        key = (src, dst, rel_type)
        if key in rel_set:
            return
        rel_set.add(key)
        rels.append({
            "id":           f"rel_{len(rels)+1:04d}",
            "src_id":       src,
            "dst_id":       dst,
            "relationship": rel_type,
            "case_id":      case_id,
            "confidence":   confidence if confidence is not None else round(random.uniform(0.6,0.99),3),
            "pattern":      pattern,
            "created_at":   rdate("2024-01-01","2024-06-30"),
        })

    # person → phone (owns)
    for ph in phones:
        if ph["registered_to"]:
            add(ph["registered_to"], ph["id"], "owns")

    # person → device (uses)
    for dev in devices:
        if dev["registered_to"]:
            add(dev["registered_to"], dev["id"], "uses")

    # person → bank_account (owns)
    for acc in bank_accounts:
        if acc["holder_id"]:
            add(acc["holder_id"], acc["id"], "owns")

    # person → upi (owns)
    for u in upi_ids:
        if u["registered_to"]:
            add(u["registered_to"], u["id"], "owns")

    # sim → phone (registered_on)
    for s in sims:
        if s["phone_id"]:
            add(s["id"], s["phone_id"], "registered_on")

    # upi → bank_account (linked_to)
    for u in upi_ids:
        if u["linked_account"]:
            add(u["id"], u["linked_account"], "linked_to")

    # transactions → transferred_to
    for txn in transactions:
        if txn.get("flagged"):
            add(txn["src_account"], txn["dst_account"], "transferred_to",
                case_id=txn["case_id"], confidence=round(txn["risk_score"],3),
                pattern=txn["pattern"])

    # call records → called
    for call in call_records:
        if call.get("flagged"):
            add(call["caller_id"], call["receiver_id"], "called",
                case_id=call["case_id"], confidence=round(call["risk_score"],3),
                pattern=call["pattern"])

    # P4: shared-device cluster — same device → multiple persons
    shared_dev = random.choice(devices)["id"]
    cluster_persons = random.sample([p["id"] for p in persons], 5)
    for cp in cluster_persons:
        add(cp, shared_dev, "uses",
            case_id="case_004", confidence=0.88, pattern="shared_device")

    # P5: shared-SIM cluster — one SIM → multiple persons
    shared_sim = random.choice(sims)["id"]
    cluster_persons2 = random.sample([p["id"] for p in persons], 5)
    for cp in cluster_persons2:
        add(cp, shared_sim, "uses",
            case_id="case_005", confidence=0.91, pattern="shared_sim")

    # P6: hub → spoke call associations
    hub_ph = phones[0]["id"]
    for spoke_ph in [p["id"] for p in phones[1:9]]:
        add(hub_ph, spoke_ph, "associated_with",
            case_id="case_006", confidence=0.85, pattern="communication_hub")

    # SIM swap associations
    for s in sims:
        if s.get("swap_count", 0) >= 2:
            add(s["id"], s.get("registered_to", s["phone_id"]), "swapped_sim",
                case_id="case_001", confidence=0.93, pattern="sim_swap")

    # Victim → case associations
    for v in victims:
        for case_id in random.sample([c["id"] for c in cases], min(2, len(cases))):
            add(v["id"], case_id, "reported_by", confidence=0.99)

    return rels


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print("\n[*] Cyber Fraud Network Analyzer -- Synthetic Data Generator")
    print(f"   Output: {SAMPLE_DIR}")
    print(f"   Seed  : {SEED}\n")

    # Ensure ML placeholder directory exists (no files written)
    ML_DIR.mkdir(parents=True, exist_ok=True)
    readme = ML_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# data/ml/\n\nThis directory holds ML training data (Part 7).\n"
            "**Do NOT commit raw training CSVs here.**\n"
            "The 50K+ training dataset is located at `src/data/`.\n",
            encoding="utf-8",
        )
        print(f"  [+] {'data/ml/README.md':<30} placeholder created\n")

    print("Generating entities...")
    locations     = gen_locations(50)
    persons       = gen_persons(50, locations)
    phones        = gen_phones(100, persons)
    sims          = gen_sims(50, phones, persons)
    devices       = gen_devices(50, persons)
    bank_accounts = gen_bank_accounts(100, persons, locations)
    upi_ids       = gen_upi_ids(75, persons, bank_accounts)
    victims       = gen_victims(50, persons, bank_accounts, phones)
    cases         = gen_cases(victims)

    print("\nGenerating activity data...")
    transactions  = gen_transactions(300, bank_accounts, upi_ids, cases, persons)
    call_records  = gen_call_records(100, phones, cases)

    print("\nGenerating derived / aggregate data...")
    evidence      = gen_evidence(cases)
    entities      = gen_entities(persons, phones, sims, devices, bank_accounts, upi_ids)
    relationships = gen_relationships(
        persons, phones, sims, devices, bank_accounts, upi_ids,
        transactions, call_records, cases, victims,
    )

    print("\nWriting JSON files to data/sample/ ...")
    save("locations.json",     locations)
    save("persons.json",       persons)
    save("phones.json",        phones)
    save("sims.json",          sims)
    save("devices.json",       devices)
    save("bank_accounts.json", bank_accounts)
    save("upi_ids.json",       upi_ids)
    save("victims.json",       victims)
    save("cases.json",         cases)
    save("transactions.json",  transactions)
    save("call_records.json",  call_records)
    save("evidence.json",      evidence)
    save("entities.json",      entities)
    save("relationships.json", relationships)

    # ── summary ───────────────────────────────────────────────────────────
    print("\n[+] Summary")
    print(f"   Locations     : {len(locations)}")
    print(f"   Persons       : {len(persons)}")
    print(f"   Phones        : {len(phones)}")
    print(f"   SIMs          : {len(sims)}")
    print(f"   Devices       : {len(devices)}")
    print(f"   Bank accounts : {len(bank_accounts)}")
    print(f"   UPI IDs       : {len(upi_ids)}")
    print(f"   Victims       : {len(victims)}")
    print(f"   Cases         : {len(cases)}")
    print(f"   Transactions  : {len(transactions)}")
    print(f"   Call records  : {len(call_records)}")
    print(f"   Evidence items: {len(evidence)}")
    print(f"   Entities      : {len(entities)}")
    print(f"   Relationships : {len(relationships)}")

    print("\n[>] Fraud patterns embedded:")
    pattern_counts: dict[str, int] = {}
    for r in relationships:
        if r.get("pattern"):
            pattern_counts[r["pattern"]] = pattern_counts.get(r["pattern"], 0) + 1
    for txn in transactions:
        if txn.get("flagged"):
            p = txn["pattern"]
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
    for p, cnt in sorted(pattern_counts.items()):
        label = {
            "sim_swap":             "P1 SIM-swap sequence",
            "mule_network":         "P2 Mule-account network",
            "transaction_layering": "P3 Transaction layering",
            "shared_device":        "P4 Shared-device cluster",
            "shared_sim":           "P5 Shared-SIM cluster",
            "communication_hub":    "P6 Communication hub",
            "rapid_multi_hop":      "P7 Rapid multi-hop fund movement",
            "legitimate":           "P8 Normal legitimate activity",
        }.get(p, p)
        print(f"   {label:<40}: {cnt:>4} events")

    print("\n[OK] Done. Synthetic investigation dataset written to data/sample/\n")


if __name__ == "__main__":
    main()
