import numpy as np
from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
from sklearn.manifold import TSNE
import plotly.express as px
from datetime import datetime
import json
from unidecode import unidecode
import time

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
for filename in [
    "coordinates.csv",
    "phd_students.h5"
]:
    file_path = input_dir / filename
    if file_path.exists():
        match file_path.suffix:
            case ".csv":
                dataset = pd.read_csv(file_path, encoding="utf-8")
            case ".parquet":
                dataset = pd.read_parquet(file_path, engine="pyarrow")
            case ".h5":
                dataset = pd.read_hdf(file_path)
            case _:
                print(f"Format de fichier non pris en charge : {file_path}")
                continue
        datasets[filename.split(".")[0]] = dataset
    else:
        print(f"Fichier manquant : {file_path}")


# Initialisation des variables dataset
matching_df = pd.DataFrame(datasets["phd_students"])
coordinates_df = datasets["coordinates"]
# Récupération des disciplines et des coordonnées
disciplines = coordinates_df.iloc[:, 0].tolist()
coordinates_df = coordinates_df.iloc[:, 1:]
matrix_coord = coordinates_df.to_numpy()
# Création d'un DataFrame pour les données à traiter
main_df = matching_df.copy()
# Initialisation des variables
disc_filters = []
nb_sups = 2
n = len(disciplines)
disc_colors = (px.colors.qualitative.Set2 + px.colors.qualitative.Set1 + px.colors.qualitative.Set3)[:n]
embedded = TSNE(n_components=2, learning_rate='auto', random_state=42, perplexity=5).fit_transform(matrix_coord)

print("Datasets chargés avec succès :", list(datasets.keys()))

@app.route("/")
def index():
    datasets_info = {name: list(df.columns) for name, df in datasets.items()}
    return render_template("index.html", datasets=datasets_info)

def row_satisfies_conditions(values, filters_param):
    for disc_filter in values:
        if disc_filter in filters_param:
            filters_param.remove(disc_filter)
    return filters_param == [''] or filters_param == []

@app.route("/filter_supervisors")
def filter_supervisors():
    global disc_filters
    disc_filters = [disc for disc in request.args.get("discs").split(",")]
    return "", 204  # No response content

@app.route("/filter")
def filter_students():
    global main_df
    main_df = matching_df.copy()

    mask = pd.Series(True, index=main_df.index)  # Start with all True

    nb_pub_filter = int(request.args.get("nb_pubs"))
    if nb_pub_filter > 0:
        mask &= main_df["num_pubs_student"] >= nb_pub_filter

    multidisciplinary_filter = float(request.args.get("multidisciplinarity"))
    if multidisciplinary_filter > 0:
        mask &= main_df["distance_areas_supervisors"] >= multidisciplinary_filter

    if disc_filters:
        # List of all supervisor discipline columns
        discipline_columns = [f"discipline_supervisor{i}_scopus" for i in range(1, nb_sups + 1)]
        mask &= main_df.apply(lambda row: row_satisfies_conditions(row[discipline_columns].values, disc_filters.copy()),
                             axis=1)

    if not mask.all() :
        main_df = main_df[mask]

    return "", 204  # No response content

@app.route("/search")
def search():
    name = request.args.get("q", "").strip().lower()
    # Take into account french special characters
    name = unidecode(name)

    columns_search_str = request.args.get("columns_search", "") # Récupère les colonnes comme une chaîne
    columns_search = columns_search_str.split(",")  # Décompose les colonnes en liste

    columns_show_str = request.args.get("columns_show", "") # Récupère les colonnes comme une chaîne
    columns_show = columns_show_str.split(",")  # Décompose les colonnes en liste

    global main_df
    # if main_df is empty then tell user no user found
    if main_df.empty:
        return jsonify("")
    if not columns_search:
        columns_search = main_df.columnsg
    if columns_show == ['']:
        print("columns_show is empty")
        columns_show = main_df.columns

    valid_search_columns = [col for col in columns_search if col in main_df.columns]
    if not valid_search_columns:
        return jsonify({"error": "No valid search columns specified"}), 400

    valid_show_columns = [col for col in columns_show if col in main_df.columns]
    if not valid_show_columns:
        return jsonify({"error": "No valid show columns specified"}), 400

    search_space = main_df[valid_search_columns].fillna("").astype(str).agg(" ".join, axis=1)
    mask = search_space.str.contains(name, case=False, na=False)


    results = main_df.loc[mask, valid_show_columns].fillna("")
    # apply title case to name
    results["name_student"] = results["name_student"].str.title()
    results = results.to_dict(orient="records")

    return jsonify(results)

@app.route("/update_graph")
def update_graph():
    begin = time.time()
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
            "marker_symbol": "circle",
            "text_position": "middle center"
        }

    # Break down query parameters
    isShowSup = request.args.get("isShowSup") == "1"
    phdIds = [int(phdId) for phdId in request.args.get("phd").split(",")]

    # Retrieve the data of the PhD students
    # phdStudents = main_df[main_df["id_scopus_student"].isin(phdIds)]

    discs_done = time.time()

    # Sample all the PhD students
    phdStudents = main_df.sort_values(by=["distance_areas_supervisors","id_scopus_student"], ascending=False)
    sample_size = len(phdStudents)
    loop_index = 1
    for i, student in phdStudents.head(sample_size).iterrows():
        # print("Processing student : ",student["name_student"])
        print(f"Processing student {loop_index}/{sample_size} ")
        loop_index += 1
        main_disc = student["discipline_student_scopus"]
        student_name = student["name_student"].title()
        areas = np.array([float(x) for x in student["areas_student"][2:-2].split(", ")])
        nb_pub_student = int(student["num_pubs_student"])

        if nb_pub_student != 0:
            pubs = areas*nb_pub_student
            # to int values
            pubs = [int(x) for x in pubs]
            labeled_pubs = dict(zip(disciplines, pubs))
            labeled_pubs = {k: v for k, v in sorted(labeled_pubs.items(), key=lambda item: item[1], reverse=True)}
            # remove zero values
            labeled_pubs = {k: v for k, v in labeled_pubs.items() if v != 0}
            labeled_pubs = [f"{disc} ({pub})" for disc, pub in labeled_pubs.items()]
            label = f"{student_name} ({main_disc}) {labeled_pubs}"
            #compute coordinates
            coordinates = areas.dot(embedded)
            color = disc_colors[np.argmax(areas)] if areas.sum() > 0 else disc_colors[
                list.index(disciplines, main_disc)]
        else:
            #special label
            label = f"{student_name} ({main_disc}) has no publication"
            #give baricenter of supervisors for coordinates
            supervisors = [student[f"name_supervisor{i}"] for i in range(1, nb_sups+1)]
            supervisors = [sup for sup in supervisors if type(sup) == str and sup != "nan" and sup != ""]
            supervisors_coords = [
                np.array([float(x) for x in student[f"areas_supervisor{i}"][2:-2].split(", ")]).dot(embedded)
                for i in range(1, len(supervisors)+1)
            ]
            coordinates = np.mean(supervisors_coords, axis=0)
            color = "black"
        df_to_plot.loc[len(df_to_plot)] = {
            "x": coordinates[0],
            "y": coordinates[1],
            "type": "phd",
            "name": student_name,
            "color": color,
            "size": 10,
            "text": student_name,
            "label": label,
            "marker_symbol": "triangle",
            "text_position": "top left"
        }
        if isShowSup :
            # Retrieve the data of the supervisors
            supervisors = [student[f"name_supervisor{i}"] for i in range(1, nb_sups+1)]
            for j, supervisor_name in enumerate(supervisors):
                if not supervisor_name or supervisor_name == "nan" or supervisor_name == "" or type(supervisor_name) != str:
                    continue
                supervisor_name = supervisor_name.title()
                areas = np.array([float(x) for x in student[f"areas_supervisor{j+1}"][2:-2].split(", ")])
                pubs = areas*int(student[f"num_pubs_supervisor{j+1}"])
                # to int value
                pubs = [int(x) for x in pubs]
                labeled_pubs = dict(zip(disciplines, pubs))
                labeled_pubs = {k: v for k, v in sorted(labeled_pubs.items(), key=lambda item: item[1], reverse=True)}
                # remove zero values
                labeled_pubs = {k: v for k, v in labeled_pubs.items() if v != 0}
                labeled_pubs = [f"{disc} ({pub})" for disc, pub in labeled_pubs.items()]
                disc_index = np.argmax(areas)
                main_disc = disciplines[disc_index]
                label = f"{supervisor_name} ({main_disc}) {labeled_pubs}"
                label2 = f"supervises {student_name}"
                coordinates = areas.dot(embedded)
                df_to_plot.loc[len(df_to_plot)] = {
                    "x": coordinates[0],
                    "y": coordinates[1],
                    "type": "supervisor",
                    "name": supervisor_name,
                    "color": disc_colors[disc_index],
                    "size": 20,
                    "text": supervisor_name,
                    "label": label+"<br>"+label2,
                    "marker_symbol": "square",
                    "text_position": "top right"
                }

    people_done = time.time()

    fig = go.Figure(go.Scattergl(
        x=df_to_plot["x"].tolist(),
        y=df_to_plot["y"].tolist(),
        mode='markers',
        marker=dict(
            color=df_to_plot["color"].tolist(),
            size=df_to_plot["size"].tolist(),
        )
        # text=df_to_plot["name"].tolist(),
        # hoverinfo='text',
        # hovertext=df_to_plot["label"].tolist(),
        # textposition=df_to_plot["text_position"].tolist()
    ))

    fig_done = time.time()
    with open("./results/times.txt", "a") as f:
        f.write(f"Discs : {discs_done-begin}\n"
                f"People : {people_done-discs_done}\n"
                f"Fig : {fig_done-people_done}\n"
                f"Total : {fig_done-begin}\n\n")

    x = df_to_plot["x"]
    y = df_to_plot["y"]
    colors = df_to_plot["color"]

    # Add arrows
    arrows = []
    # if len(x) > len(disciplines):
    #     for i in range(len(disciplines), len(x)):
    #         arrows.append(create_arrow(x[i], y[i], colors[i]))
    #
    # for arrow in arrows:
    #     fig.add_annotation(arrow)

    fig.update_layout(
    #     title="Plot with Lines and Vectors",
    #     xaxis_title="X Axis",
    #     yaxis_title="Y Axis",
    #     showlegend=False
        xaxis = dict(showticklabels=False),
        yaxis = dict(showticklabels=False)
    )

    fig.write_image(f"./results/fig{sample_size}.png")
    fig.write_html(f"./results/fig{sample_size}.html")

    # Save the data to a parquet file
    path = "../data"
    if Path(path).exists():
        df_to_plot.to_parquet(path + "/df_to_plot.parquet")

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
    if not data or "name" not in data or "issue" not in data or "email" not in data or "category" not in data:
        return jsonify({"message": "Données invalides"}), 400

    report = {
        "name": data["name"],
        "email": data["email"],
        "category": data["category"],
        "issue": data["issue"],
        "student name": data["phd_name"],
        "supervisor name": data["supervisor"],
        "publication": data["publication"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    save_report(report)

    return jsonify({"message": "Report enregistré avec succès", "report": report})



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
