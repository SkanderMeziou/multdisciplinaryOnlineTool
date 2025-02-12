import numpy as np
from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
from sklearn.manifold import TSNE
import plotly.express as px

app = Flask(__name__)

#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------fonctions utilitaires---------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------

def arrow(coord_x,coord_y,color):
    return dict(
        x=coord_x, y=coord_y, xref="x", yref="y",
        ax=0, ay=0, axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor=color
    )


#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------application et routes---------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------

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
    supervisor_param = request.args.get("sup", "").strip().lower()
    phdStudent_param = request.args.get("phd", "").strip().lower()
    supervisor_param = supervisor_param.split(",")
    supervisor_names = []
    supervisors = []

    researcher_df = datasets["all_authors"]
    index_of_id = researcher_df.columns.get_loc("id")
    index_of_areas = researcher_df.columns.get_loc("areas")
    auth_vect_df = datasets["auth_vect"]
    matrix_auth = []

    disciplines = auth_vect_df.columns[1:]
    names = disciplines.tolist()
    labels = disciplines.tolist()

    if supervisor_names != ['']:
        for name in supervisor_param :
            print("🔍 Recherche du directeur :", name)
            data = researcher_df[researcher_df["name"] == name]
            print("📩 Réponse reçue :", data , " || Nombre de directeurs : ", len(data))
            if len(data) > 0:
                supervisors.append(data.values[0])
                names.append(name)
                supervisor_names.append(name)
                discs, counts = np.unique(data.values[0][index_of_areas].split("; "), return_counts=True)
                sup_label = name
                for disc, count in zip(discs, counts):
                    sup_label += f" [{disc} ({count})] "
                labels.append(sup_label)
        sup_vectors = auth_vect_df.loc[
            auth_vect_df["id"].isin([supervisor[index_of_id] for supervisor in supervisors])
        ]
        sup_vectors.drop(["id"], axis=1, inplace=True)
        matrix_auth = sup_vectors.to_numpy()

    student_data = researcher_df[researcher_df["name"] == phdStudent_param].values[0]
    stud_discs, stud_counts = np.unique(student_data[index_of_areas].split("; "), return_counts=True)
    stud_label = phdStudent_param
    for disc, count in zip(stud_discs, stud_counts):
        stud_label += f" [{disc} ({count})] "
    labels.append(stud_label)
    stud_vector = auth_vect_df.loc[auth_vect_df["id"] == student_data[index_of_id]]
    coordinates_df = datasets["coordinates_15dimensions"]

    stud_vector.drop(["id"], axis=1, inplace=True)
    coordinates_df = coordinates_df.iloc[:, 1:]

    matrix_stud = stud_vector.to_numpy()


    n = len(disciplines)
    disc_colors = (px.colors.qualitative.Set1+px.colors.qualitative.Set2+px.colors.qualitative.Set3)[:n]  # Pick the first `n` colors from Set1
    colors = disc_colors + [disc_colors[np.argmax(researcher)] for researcher in matrix_auth] + [disc_colors[np.argmax(matrix_stud[0])]]

    matrix_coord = coordinates_df.to_numpy()
    embedded = (TSNE(n_components=2, learning_rate='auto', random_state=42, perplexity=5)
                .fit_transform(matrix_coord))
    matrix_stud = matrix_stud.dot(embedded)
    matrix = matrix_stud
    if len(matrix_auth) > 0:
        matrix_auth = matrix_auth.dot(embedded)
        matrix = np.concatenate((matrix_auth, matrix_stud), axis=0)
    full_coords = np.concatenate((embedded, matrix), axis=0)
    x = full_coords[:, 0].tolist()
    y = full_coords[:, 1].tolist()

    names.append(phdStudent_param)

    sizes = [30] * len(disciplines) + [20] * len(supervisor_names) + [10]
    text_position = ["top center"] * len(disciplines) + ["bottom left"] * len(supervisor_names) + ["bottom right"]

    fig = go.Figure(go.Scatter(x=x, y=y, mode='markers+text', text=names, hovertext=labels, hoverinfo='text',
                               textposition=text_position, marker=dict(color=colors, size=sizes)))

    #positionnement des flèches
    arrows=[]
    if len(x)>len(disciplines) :
        for i in range(25,len(x)-1):
            arrows.append(arrow(x[i],y[i],colors[i]))
        arrows.append(arrow(x[len(x)-1],y[len(y)-1],colors[len(x)-1]))

    for a in arrows:
        fig.add_annotation(a)

    fig.update_layout(
        title="Plot with Lines and Vectors",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        showlegend=False
    )

    return fig.to_json()

if __name__ == "__main__":
    app.run(debug=True)
