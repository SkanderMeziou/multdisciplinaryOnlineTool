from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path

app = Flask(__name__)

# Load multiple CSV datasets into a dictionary
input_dir = Path('../data')
datasets = {
    "theses": pd.read_csv(f"{input_dir}/theses.csv"),
    "reduced": pd.read_csv(f"{input_dir}/reduced.csv")
}
print("successfully charged datasets")

@app.route("/")
def index():
    # Passer les noms des datasets et leurs colonnes pour la sélection dans l'interface
    datasets_info = {name: list(df.columns) for name, df in datasets.items()}
    return render_template("index.html", datasets=datasets_info)

#exemple de recherche /search?dataset=theses&q=Giroire&columns=auteur.nom
@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    dataset_name = request.args.get("dataset", "")
    columns = request.args.getlist("columns")  
    print("query:", query)
    if dataset_name not in datasets:
        return jsonify({"error": "Dataset not found"}), 400

    df = datasets[dataset_name]

    if not columns:
        columns = df.columns

    valid_columns = [col for col in columns if col in df.columns]
    if not valid_columns:
        return jsonify({"error": "No valid columns specified"}), 400
    print("valid_columns:", valid_columns)
    mask = df[valid_columns].apply(
        lambda row: row.astype(str).str.contains(query, case=False, na=False).any(),
        axis=1
    )
    print("mask:", mask)
    results = df[mask]
    print("results:\n", results["auteur.nom"])
    return jsonify(results.to_dict(orient="records"))




if __name__ == "__main__":
    app.run(debug=True)
