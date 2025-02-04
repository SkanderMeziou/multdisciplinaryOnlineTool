from flask import Flask, request, render_template, jsonify
import pandas as pd

app = Flask(__name__)

# Load CSV data
df = pd.read_csv("data.csv")


@app.route("/")
def index():
    return render_template("index.html", columns=df.columns.tolist())


@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    column = request.args.get("column", "")

    if query and column in df.columns:
        results = df[df[column].astype(str).str.contains(query, case=False, na=False)]
        return jsonify(results.to_dict(orient="records"))

    return jsonify([])


if __name__ == "__main__":
    app.run(debug=True)