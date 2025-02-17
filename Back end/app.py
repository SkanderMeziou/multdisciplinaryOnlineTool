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
for filename in ["coordinates.csv", "matchings_with_id.csv"]:
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
    name = request.args.get("q", "").strip().lower()

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
    mask = search_space.str.contains(name, case=False, na=False)

    results = df.loc[mask, valid_show_columns].fillna("").to_dict(orient="records")
    return jsonify(results)

@app.route("/update_graph")
def update_graph():
    # Load data
    main_df = datasets["matchings_with_id"]

    # Define disciplines and their coordinates
    coordinates_df = datasets["coordinates"]
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

    # Break down query parameters
    isShowSup = request.args.get("isShowSup") == "1"
    phdIds = [int(phdId) for phdId in request.args.get("phd").split(",")]

    # Retrieve the data of the PhD students
    phdStudents = main_df[main_df["id"].isin(phdIds)]

    for i, student in phdStudents.iterrows():
        print("Processing student : ",student["name_student"])
        print(student)
        main_disc = student["discipline_student_scopus"]
        student_name = student["name_student"]
        areas = np.array([float(x) for x in student["areas_student"][2:-2].split(", ")])
        pubs = areas*int(student["num_pubs_student"])
        labeled_pubs = dict(zip(disciplines, pubs))
        labeled_pubs = {k: v for k, v in sorted(labeled_pubs.items(), key=lambda item: item[1], reverse=True)}
        # remove zero values
        labeled_pubs = {k: v for k, v in labeled_pubs.items() if v != 0}
        labeled_pubs = [f"{disc} ({pub})" for disc, pub in labeled_pubs.items()]
        label = f"{student_name} ({main_disc})\n{labeled_pubs}"
        coordinates = areas.dot(embedded)
        df_to_plot.loc[len(df_to_plot)] = {
            "x": coordinates[0],
            "y": coordinates[1],
            "type": "phd",
            "name": student_name,
            "color": disc_colors[np.argmax(areas)],
            "size": 10,
            "text": student_name,
            "label": label,
            "text_position": "top left"
        }
        if isShowSup :
            # Retrieve the data of the supervisors
            supervisors = [student["name_supervisor1"], student["name_supervisor2"]]
            for j, supervisor_name in enumerate(supervisors):
                areas = np.array([float(x) for x in student[f"areas_supervisor{j+1}"][2:-2].split(", ")])
                # pubs = areas*int(student[f"num_pubs_supervisor{j+1}"])
                labeled_pubs = dict(zip(disciplines, areas))
                # labeled_pubs = {k: v for k, v in sorted(labeled_pubs.items(), key=lambda item: item[1], reverse=True)}
                # remove zero values
                labeled_pubs = {k: v for k, v in labeled_pubs.items() if v != 0}
                labeled_pubs = {k: v for k, v in sorted(labeled_pubs.items(), key=lambda item: item[1], reverse=True)}
                labeled_pubs = [f"{disc} ({pub})" for disc, pub in labeled_pubs.items()]
                label = f"{supervisor_name} ({main_disc})\n{labeled_pubs}"
                coordinates = areas.dot(embedded)
                df_to_plot.loc[len(df_to_plot)] = {
                    "x": coordinates[0],
                    "y": coordinates[1],
                    "type": "supervisor",
                    "name": supervisor_name,
                    "color": disc_colors[np.argmax(areas)],
                    "size": 20,
                    "text": supervisor_name,
                    "label": label,
                    "text_position": "top right"
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
