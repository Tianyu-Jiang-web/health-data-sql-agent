import sqlite3, random
from datetime import date, timedelta

random.seed(42)   # 固定随机种子,每次生成的数据相同

con = sqlite3.connect("hospital.db")
con.executescript("""
DROP TABLE IF EXISTS admissions;
DROP TABLE IF EXISTS patients;
CREATE TABLE patients (
  patient_id INTEGER PRIMARY KEY, sex TEXT, birth_year INTEGER);
CREATE TABLE admissions (
  admission_id INTEGER PRIMARY KEY, patient_id INTEGER,
  admit_date TEXT, los_days INTEGER, ward TEXT,
  diagnosis_group TEXT, died INTEGER);
""")

for pid in range(1, 501):
    con.execute("INSERT INTO patients VALUES (?,?,?)",
                (pid, random.choice(["F", "M"]), random.randint(1935, 2005)))

wards = ["ICU", "Cardiology", "Respiratory", "General"]
dx = ["Cardiac", "Respiratory", "Infection", "Trauma", "Other"]
for aid in range(1, 1201):
    ward = random.choice(wards)
    mu = 1.4 if ward == "ICU" else 1.0          # ICU 平均住得更久
    los = max(1, int(random.lognormvariate(mu, 0.7)))
    d = date(2023, 1, 1) + timedelta(days=random.randint(0, 700))
    con.execute("INSERT INTO admissions VALUES (?,?,?,?,?,?,?)",
                (aid, random.randint(1, 500), d.isoformat(), los, ward,
                 random.choice(dx), int(random.random() < 0.06)))

con.commit()
con.close()
print("done")