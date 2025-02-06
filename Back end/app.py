from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
import plotly.express as px

app = Flask(__name__)

# Définition du chemin des fichiers de manière robuste
input_dir = Path(__file__).resolve().parent.parent / "data"

# Chargement sécurisé des fichiers CSV
datasets = {}
for filename in ["theses.csv", "all_authors.csv", "auth_vect.csv", "coordinates_15dimensions.csv"]:
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
def search():
    query = request.args.get("q", "").strip().lower()

    dataset_name = request.args.get("dataset", "")
    if dataset_name not in datasets:
        return jsonify({"error": "Dataset not found"}), 400

    columns_search_str = request.args.get("columns_search", "") # Récupère les colonnes comme une chaîne
    columns_search = columns_search_str.split(",")  # Décompose les colonnes en liste

    columns_show_str = request.args.get("columns_show", "") # Récupère les colonnes comme une chaîne
    columns_show = columns_show_str.split(",")  # Décompose les colonnes en liste

    df = datasets[dataset_name]
    if not columns_search:
        columns_search = df.columns
    if columns_show == ['']:
        print("columns_show is empty")
        columns_show = df.columns

    valid_search_columns = [col for col in columns_search if col in df.columns]
    if not valid_search_columns:
        return jsonify({"error": "No valid search columns specified"}), 400

    valid_show_columns = [col for col in columns_show if col in df.columns]
    if not valid_show_columns:
        return jsonify({"error": "No valid show columns specified"}), 400

    search_space = df[valid_search_columns].fillna("").astype(str).agg(" ".join, axis=1)
    mask = search_space.str.contains(query, case=False, na=False)

    results = df.loc[mask, valid_show_columns].fillna("").to_dict(orient="records")
    return jsonify(results)

@app.route("/update_graph")
def update_graph():
    query = request.args.get("q", "").strip().lower()
    supervisor_names = query.split(",")
    # print(supervisor_names)
    researcher_df = datasets["all_authors"]
    # print(researcher_df.head())
    supervisors = []
    for name in supervisor_names :
        print("🔍 Recherche du directeur :", name)
        data = researcher_df[researcher_df["name"] == name]
        print("📩 Réponse reçue :", data , " || Nombre de directeurs : ", len(data))
        supervisors.append(data.values[0])
    print("supervisors : ", supervisors)
    auth_vect_df = datasets["auth_vect"]
    index_of_id = researcher_df.columns.get_loc("id")
    print("index_of_id : ", index_of_id)
    sup_vect = auth_vect_df.loc[
        auth_vect_df["id"].isin([supervisor[index_of_id] for supervisor in supervisors])
    ]
    coordinates_df = datasets["coordinates_15dimensions"]

    sup_vect.drop(["id"], axis=1, inplace=True)
    #drop the first column of coordinates_df
    coordinates_df.drop(coordinates_df.columns[0], axis=1, inplace=True)
    #print first 2 line of coorsinates_df
    # print("sup_vect shape : ", sup_vect.shape)
    # print("coordinates_df shape : ", coordinates_df.shape)
    # print(coordinates_df.head(2))
    #print first 2 line of sup_vect
    # print(sup_vect.head(2))
    matrix_auth = sup_vect.to_numpy()
    matrix_coord = coordinates_df.to_numpy()
    # dot product of the two dataframes
    dot_product = matrix_auth.dot(matrix_coord)
    print("dot product shape : ",dot_product.shape)
    print("dot product :",dot_product)
    fig = go.Figure(data=[go.Scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16], mode="markers", hoverlabel=supervisor_names)])
    return fig.to_json()

if __name__ == "__main__":
    app.run(debug=True)
