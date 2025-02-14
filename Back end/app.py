import numpy as np
from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
from sklearn.manifold import TSNE
import plotly.express as px
from datetime import datetime
import json

app = Flask(__name__)
REPORTS_FILE = "reports.json"

#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------fonctions utilitaires---------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------

def create_arrow(coord_x, coord_y, color):
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
for filename in ["theses.csv", "all_authors.csv", "auth_vect.csv", "coordinates_15dimensions.csv", "coordinates_25dimensions.csv"]:
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
    nb_dim = 15
    # Load data
    auth_vect_df = datasets["auth_vect"]
    researcher_df = datasets["all_authors"]
    # Define disciplines and their coordinates
    coordinates_df = datasets[f"coordinates_{nb_dim}dimensions"]
    disciplines = coordinates_df.iloc[:, 0]
    coordinates_df = coordinates_df.iloc[:, 1:]


    # TSNE transformation
    matrix_coord = coordinates_df.to_numpy()
    embedded = TSNE(n_components=2, learning_rate='auto',
                    random_state=42, perplexity=5).fit_transform(matrix_coord)

    # Define colors
    n = len(disciplines)
    disc_colors = (px.colors.qualitative.Set2 + px.colors.qualitative.Set1 + px.colors.qualitative.Set3)[:n]

    # Create a dataframe to plot
    df_to_plot = pd.DataFrame(columns=["x", "y", "type", "name", "color", "size", "text", "label", "text_position"])
    # Add disciplines
    for i, disc in enumerate(disciplines):
        df_to_plot.loc[len(df_to_plot)] = {
            "x": embedded[i, 0],
            "y": embedded[i, 1],
            "type": "discipline",
            "name": disc,
            "color": disc_colors[i],
            "size": 30,
            "text": disc,
            "label": disc,
            "text_position": "middle center"
        }

    # Add supervisors and PhD students
    index_of_id = researcher_df.columns.get_loc("id")
    index_of_areas = researcher_df.columns.get_loc("areas")

    # Add supervisors
    supervisor_param = request.args.get("sup", "").strip()
    supervisor_param = supervisor_param.split(",")
    supervisor_names = []
    if supervisor_param != [""] :
        for name in supervisor_param:
            print("🔍 Recherche du directeur :", name)
            data = researcher_df[researcher_df["name"] == name]
            if len(data) == 0:
                inverse_name = name.split(" ")[-1] + " " + " ".join(name.split(" ")[:-1])
                data = researcher_df[researcher_df["name"] == inverse_name]
            if len(data) > 0:
                supervisor = data.values[0]
                supervisor_names.append(name)
                discs, counts = np.unique(supervisor[index_of_areas].split("; "), return_counts=True)
                print("📚 Disciplines du directeur :", supervisor[index_of_areas])
                label = "Supervisor : " + name
                for disc, count in zip(discs, counts):
                    label += f" [{disc} ({count})] "
                # Compute coordinates using auth_vect
                sup_vector = auth_vect_df.loc[auth_vect_df["id"] == supervisor[index_of_id]]
                sup_vector = sup_vector.drop(columns=["id"])
                print("vector : ", np.array(sup_vector))
                if not sup_vector.empty:
                    coords = sup_vector.to_numpy().dot(embedded)
                    df_to_plot.loc[len(df_to_plot)] = {
                        "x": coords[0, 0],
                        "y": coords[0, 1],
                        "type": "supervisor",
                        "name": name,
                        "color": disc_colors[np.argmax(sup_vector)],
                        "size": 20,
                        "text": name,
                        "label": label,
                        "text_position": "bottom right"
                    }

    # Add PhD students
    phdStudent_param = request.args.get("phd", "").strip()
    phdStudent_names = [name.strip() for name in phdStudent_param.split(",")] if phdStudent_param else []
    for student_name in phdStudent_names:
        print("🔍 Recherche de l'étudiant :", student_name)
        student_data = researcher_df[researcher_df["name"] == student_name]
        if len(student_data) == 0:
            inverse_name = student_name.split(" ")[-1] + " " + " ".join(student_name.split(" ")[:-1])
            student_data = researcher_df[researcher_df["name"] == inverse_name]
        if len(student_data) > 0:
            print("📚 Disciplines de l'étudiant :", student_data.values[0][index_of_areas])
            student = student_data.values[0]
            discs, counts = np.unique(student[index_of_areas].split("; "), return_counts=True)
            label = student_name
            for disc, count in zip(discs, counts):
                label += f" [{disc} ({count})] "
            # Compute coordinates using auth_vect
            stud_vector = auth_vect_df.loc[auth_vect_df["id"] == student[index_of_id]]
            stud_vector = stud_vector.drop(columns=["id"])
            print("vector : ", np.array(stud_vector))
            print("index : ", np.argmax(stud_vector))
            print("disciplines : ", disciplines)
            print("Main disciplines of the student : ", disciplines[np.argmax(stud_vector)])
            if not stud_vector.empty:
                coords = stud_vector.to_numpy().dot(embedded)
                df_to_plot.loc[len(df_to_plot)] = {
                    "x": coords[0, 0],
                    "y": coords[0, 1],
                    "type": "phd",
                    "name": student_name,
                    "color": disc_colors[np.argmax(stud_vector)],
                    "size": 10,
                    "text": student_name,
                    "label": label,
                    "text_position": "top left"
                }


    fig = go.Figure(go.Scatter(
        x=df_to_plot["x"].tolist(),
        y=df_to_plot["y"].tolist(),
        mode='markers+text',
        marker=dict(
            color=df_to_plot["color"].tolist(),
            size=df_to_plot["size"].tolist(),
        ),
        text=df_to_plot["name"].tolist(),
        hoverinfo='text',
        hovertext=df_to_plot["label"].tolist(),
        textposition=df_to_plot["text_position"].tolist()
    ))

    fig.write_html(f"graph{nb_dim}.html")

    x = df_to_plot["x"]
    y = df_to_plot["y"]
    colors = df_to_plot["color"]
    # Add arrows
    arrows = []
    if len(x) > len(disciplines):
        for i in range(len(disciplines), len(x)):
            arrows.append(create_arrow(x[i], y[i], colors[i]))

    for arrow in arrows:
        fig.add_annotation(arrow)

    fig.update_layout(
        title="Plot with Lines and Vectors",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        showlegend=False
    )

    return fig.to_json()

# Charger les reports existants (ou créer un fichier vide)
def load_reports():
    try:
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Sauvegarder un nouveau report
def save_report(report):
    reports = load_reports()
    reports.append(report)
    with open(REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=4, ensure_ascii=False)

@app.route('/report', methods=['POST'])
def handle_report():
    data = request.json
    if not data or "name" not in data or "issue" not in data:
        return jsonify({"message": "Données invalides"}), 400

    report = {
        "name": data["name"],
        "issue": data["issue"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    save_report(report)

    return jsonify({"message": "Report enregistré avec succès", "report": report})



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
