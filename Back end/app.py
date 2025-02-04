from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path

app = Flask(__name__)

# Définition du chemin des fichiers de manière robuste
input_dir = Path(__file__).resolve().parent.parent / "data"

# Chargement sécurisé des fichiers CSV
datasets = {}
for filename in ["theses.csv", "reduced.csv"]:
    file_path = input_dir / filename
    if file_path.exists():
        datasets[filename.split(".")[0]] = pd.read_csv(file_path, encoding="utf-8")
    else:
        print(f"Fichier manquant : {file_path}")

print("Datasets chargés avec succès :", list(datasets.keys()))

@app.route("/")
def index():
    datasets_info = {name: list(df.columns) for name, df in datasets.items()}
    return render_template("index.html", datasets=datasets_info)

@app.route("/search")
@app.route("/search")
def search():
    query = request.args.get("q", "").strip().lower()
    dataset_name = request.args.get("dataset", "")
    columns = request.args.getlist("columns")  

    if dataset_name not in datasets:
        return jsonify({"error": "Dataset not found"}), 400

    df = datasets[dataset_name]
    if not columns:
        columns = df.columns

    valid_columns = [col for col in columns if col in df.columns]
    if not valid_columns:
        return jsonify({"error": "No valid columns specified"}), 400

    # Recherche avec remplacement des NaN
    search_space = df[valid_columns].fillna("").astype(str).agg(" ".join, axis=1)
    mask = search_space.str.contains(query, case=False, na=False)

    # Remplacement des NaN par des chaînes vides dans les résultats
    results = df[mask].fillna("").to_dict(orient="records")
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)
