import numpy as np
from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
from sklearn.manifold import TSNE

app = Flask(__name__)

#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------fonctions utilitaires---------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------

def arrow(coordX,coordY,color):
    return dict(
        x=coordX, y=coordY, xref="x", yref="y",
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
    supervisor_names = supervisor_param.split(",")
    researcher_df = datasets["all_authors"]
    supervisors = []
    for name in supervisor_names :
        print("🔍 Recherche du directeur :", name)
        data = researcher_df[researcher_df["name"] == name]
        print("📩 Réponse reçue :", data , " || Nombre de directeurs : ", len(data))
        supervisors.append(data.values[0])
    student_data = researcher_df[researcher_df["name"] == phdStudent_param].values[0]
    print("supervisors : ", supervisors)
    print("student_data : ", student_data)
    auth_vect_df = datasets["auth_vect"]
    index_of_id = researcher_df.columns.get_loc("id")
    sup_vectors = auth_vect_df.loc[
        auth_vect_df["id"].isin([supervisor[index_of_id] for supervisor in supervisors])
    ]
    stud_vector = auth_vect_df.loc[auth_vect_df["id"] == student_data[index_of_id]]
    coordinates_df = datasets["coordinates_15dimensions"]
    sup_vectors.drop(["id"], axis=1, inplace=True)
    stud_vector.drop(["id"], axis=1, inplace=True)
    coordinates_df = coordinates_df.iloc[:, 1:]
    matrix_auth = sup_vectors.to_numpy()
    # print("Matrix_auth: ", matrix_auth)
    matrix_stud = stud_vector.to_numpy()
    # print("Matrix_stud: ", matrix_stud)
    matrix = np.concatenate((matrix_auth, matrix_stud), axis=0)
    # print("Matrix shape : ", matrix.shape)
    # print("Matrix : ", matrix)
    matrix_coord = coordinates_df.to_numpy()
    # print("Matrix_coord shape : ", matrix_coord.shape)
    dot_product = matrix.dot(matrix_coord)
    full_coords = np.concatenate((matrix_coord, dot_product), axis=0)
    # print("Dot product shape : ", dot_product.shape)

    embedded = (TSNE(n_components=2, learning_rate='auto', random_state=42, perplexity=5)
                .fit_transform(full_coords))
    # print("Embedded shape : ", embedded.shape)
    x = embedded[:, 0].tolist()
    y = embedded[:, 1].tolist()

    # les premiers vecteurs representnet les disciplines, le dernier represente le phd et cux au milieu representent les superviseurs 
    

    disciplines = auth_vect_df.columns[1:]
    names = disciplines.tolist()
    names += supervisor_names
    names.append(phdStudent_param)
    # print("names : ", names)
    # print("names length : ", len(names))
    new_columns = disciplines.tolist()+supervisor_names+["student"]
    row = []
    # fill the row with the values of the embedded coordinates
    for i in range(len(x)):
        row.append( [x[i], y[i]])

    # print(new_columns)
    # print(row)
    colors = ["blue"] * len(disciplines) + ["red"] * len(supervisor_names) + ["green"]
    sizes = [30] * len(disciplines) + [20] * len(supervisor_names) + [10]
    text_position = ["top center"] * len(disciplines) + ["bottom left"] * len(supervisor_names) + ["bottom right"]
    # total_len = len(embedded)
    fig = go.Figure(go.Scatter(x=x, y=y, mode='markers+text', text=names, textposition=text_position, marker=dict(color=colors, size=sizes)))

    #positionnement des flèches
    arrows=[]
    if((len(x)>len(disciplines)+1)):
        for i in range(25,len(x)-1):
            arrows.append(arrow(x[i],y[i],"red"))
        arrows.append(arrow(x[len(x)-1],y[len(y)-1],"green"))

    for a in arrows: 
        fig.add_annotation(a)

    fig.update_layout(
        title="Plot with Lines and Vectors",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        showlegend=True
    )

    return fig.to_json()

if __name__ == "__main__":
    app.run(debug=True)
