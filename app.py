# ======================================================
# Be Healthy AI - Web Chat App
# Backend (Python + Flask + SQLite + CSV)
# ======================================================

from flask import Flask, request, jsonify, render_template
import sqlite3
import csv
import os
import random
import re
from difflib import get_close_matches
from datetime import datetime

# -------------------
# SQLite wrapper class
# -------------------
class SQL:
    def __init__(self, db_url):
        # db_url: "sqlite:///filename.db"
        self.db_file = db_url.replace("sqlite:///", "")
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # fetch results as dict
        self.cur = self.conn.cursor()

    def execute(self, query, *args):
        try:
            self.cur.execute(query, args)
            if query.strip().lower().startswith("select"):
                return [dict(row) for row in self.cur.fetchall()]
            else:
                self.conn.commit()
                return []
        except Exception as e:
            print("SQL Error:", e)
            return []

# -------------------
# Flask app setup
# -------------------
app = Flask(__name__)
DB_FILE = "be_healthy_ai.db"
CSV_FILE = "foods_global.csv"

# Ensure the database file exists
if not os.path.exists(DB_FILE):
    open(DB_FILE, 'w').close()

db = SQL(f"sqlite:///{DB_FILE}")

# -------------------
# Database tables
# -------------------
db.execute("""
CREATE TABLE IF NOT EXISTS nutrition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name TEXT NOT NULL UNIQUE,
    calories REAL,
    protein REAL,
    carbs REAL,
    fat REAL
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    query TEXT,
    weight_g INTEGER,
    calories REAL,
    protein REAL,
    carbs REAL,
    fat REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# -------------------
# Generate CSV if missing
# -------------------
def generate_csv(path=CSV_FILE, total=5000):
    if os.path.exists(path):
        return
    random.seed(42)
    base_foods = {
        "chicken breast": (165, 31.0, 0.0, 3.6),
        "beef steak": (250, 26.0, 0.0, 17.0),
        "salmon": (208, 20.4, 0.0, 13.4),
        "rice (cooked)": (130, 2.4, 28.0, 0.3),
        "pasta": (131, 5.0, 25.0, 1.1),
        "apple": (52, 0.3, 14.0, 0.2),
        "banana": (89, 1.1, 23.0, 0.3),
        "milk": (61, 3.2, 4.8, 3.3),
        "cheese": (403, 24.9, 1.3, 33.1),
        "avocado": (160, 2.0, 9.0, 15.0)
    }
    methods = ["raw", "boiled", "grilled", "fried", "baked",
               "steamed", "roasted", "pan-fried", "smoked"]
    portion_templates = ["{name}", "{method} {name}",
                         "{name} ({method})", "{method} {name} with herbs"]
    candidates = []
    # generate variations of base foods
    for name, macros in base_foods.items():
        candidates.append((name, macros))
        for _ in range(4):
            method = random.choice(methods)
            template = random.choice(portion_templates)
            new_name = template.format(name=name, method=method)
            c = max(0.1, round(macros[0]*random.uniform(0.86, 1.22), 1))
            p = round(macros[1]*random.uniform(0.88, 1.06), 1)
            cb = round(macros[2]*random.uniform(0.88, 1.1), 1)
            f = round(macros[3]*random.uniform(0.8, 1.4), 1)
            candidates.append((new_name, (c, p, cb, f)))
    # create final list of foods
    final_list = []
    idx = 0
    suffixes = ["", " - restaurant style",
                " (home cooked)", " - small serving", " - large serving", "with sauce"]
    while len(final_list) < total:
        base_name, base_macros = candidates[idx % len(candidates)]
        suffix = random.choice(suffixes) if (idx % 5 == 0) else ""
        name = f"{base_name}{suffix}"
        c = max(0.1, round(base_macros[0]*random.uniform(0.9, 1.12), 1))
        p = round(base_macros[1]*random.uniform(0.9, 1.05), 1)
        cb = round(base_macros[2]*random.uniform(0.9, 1.08), 1)
        f = round(base_macros[3]*random.uniform(0.85, 1.25), 1)
        final_list.append((name, (c, p, cb, f)))
        idx += 1
    # save CSV
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Food", "Calories", "Protein", "Carbs", "Fat"])
        for name, macros in final_list[:total]:
            writer.writerow([name, macros[0], macros[1], macros[2], macros[3]])

generate_csv()

# -------------------
# Load CSV into DB
# -------------------
def load_csv(path=CSV_FILE):
    if db.execute("SELECT COUNT(*) AS c FROM nutrition")[0]["c"] > 0:
        return
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO nutrition (food_name, calories, protein, carbs, fat) VALUES (?,?,?,?,?)",
                    row["Food"].strip(), float(row["Calories"]), float(row["Protein"]),
                    float(row["Carbs"]), float(row["Fat"])
                )
            except Exception:
                continue

load_csv()

# -------------------
# Food index for search
# -------------------
FOOD_INDEX = [r["food_name"] for r in db.execute("SELECT food_name FROM nutrition")]
FOOD_INDEX.sort()

# -------------------
# Parse query and weight
# -------------------
def parse_query(text):
    weight = None
    m = re.search(r"(\d{1,5})\s*(g|gram|grams)?", text, flags=re.I)
    if m:
        try:
            weight = int(m.group(1))
            text = text[:m.start()]+text[m.end():]
        except:
            weight = None
    if not weight:
        weight = 100
    return text.strip(), max(1, weight)

# -------------------
# Find food by name
# -------------------
def find_food(query):
    q = query.strip()
    if not q:
        return None, None, 0
    rows = db.execute("SELECT * FROM nutrition WHERE LOWER(food_name)=LOWER(?) LIMIT 1", q)
    if rows:
        return rows[0], rows[0]["food_name"], 1.0
    matches = get_close_matches(q, FOOD_INDEX, n=3, cutoff=0.5)
    if matches:
        best = matches[0]
        row = db.execute("SELECT * FROM nutrition WHERE food_name=? LIMIT 1", best)[0]
        conf = 0.85 if q.lower() in best.lower() else 0.7
        return row, best, conf
    return None, None, 0

# -------------------
# Routes
# -------------------
@app.route("/")
def index_page():
    return render_template("index.html")

@app.route("/api/nutrition", methods=["POST"])
def api_nutrition():
    data = request.get_json(silent=True) or {}
    raw = data.get("query", "").strip()
    explicit = data.get("weight_g")
    query, weight = parse_query(raw)
    if explicit:
        try:
            weight = int(explicit)
        except:
            pass
    db.execute("INSERT INTO messages (role,text,query,weight_g,created_at) VALUES (?,?,?,?,?)",
               "user", raw, query, weight, datetime.utcnow().isoformat())
    if not query:
        msg = "Please provide a food name."
        db.execute("INSERT INTO messages (role,text,created_at) VALUES (?,?,?)",
                   "assistant", msg, datetime.utcnow().isoformat())
        return jsonify({"ok": False, "message": msg}), 400
    item, name, conf = find_food(query)
    if not item:
        suggestions = get_close_matches(query, FOOD_INDEX, n=5, cutoff=0.4)
        msg = "Food not found."
        if suggestions:
            msg += " Did you mean: "+", ".join(suggestions[:5])
        db.execute("INSERT INTO messages (role,text,created_at) VALUES (?,?,?)",
                   "assistant", msg, datetime.utcnow().isoformat())
        return jsonify({"ok": False, "message": msg, "suggestions": suggestions}), 404
    factor = weight/100.0
    cal = round(item["calories"]*factor, 2)
    prot = round(item["protein"]*factor, 2)
    carbs = round(item["carbs"]*factor, 2)
    fat = round(item["fat"]*factor, 2)
    reply = f"{name} ({weight}g) Calories:{cal} Protein:{prot} Carbs:{carbs} Fat:{fat}"
    db.execute("INSERT INTO messages (role,text,query,weight_g,calories,protein,carbs,fat,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
               "assistant", reply, name, weight, cal, prot, carbs, fat, datetime.utcnow().isoformat())
    return jsonify({"ok": True, "matched_name": name, "confidence": conf, "weight_g": weight,
                    "calories": cal, "protein": prot, "carbs": carbs, "fat": fat, "text": reply})

@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        limit = int(request.args.get("limit", 30))
    except:
        limit = 30
    rows = db.execute(
        "SELECT role,text,query,weight_g,calories,protein,carbs,fat,created_at FROM messages ORDER BY id DESC LIMIT ?", limit)
    return jsonify({"ok": True, "messages": rows})

# -------------------
# Run server
# -------------------
if __name__ == "__main__":
    print("Starting server on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

