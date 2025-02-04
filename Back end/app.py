from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path

app = Flask(__name__)

# Load CSV data
input_dir = Path('../data')
phd_df = pd.read_csv(f"{input_dir}/theses.csv")


@app.route("/")
def index():
    return render_template("index.html", columns=phd_df.columns)


@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    column = request.args.get("column", "")

    if query and column in phd_df.columns:
        results = phd_df[phd_df[column].astype(str).str.contains(query, case=False, na=False)]
        return jsonify(results.to_dict(orient="records"))

    return jsonify([])


if __name__ == "__main__":
    app.run(debug=True)