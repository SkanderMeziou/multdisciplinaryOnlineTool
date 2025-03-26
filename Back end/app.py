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
from scipy import stats
import math

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
    "phd_students.h5",
    "df_to_plot.parquet"
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
df_to_plot = datasets["df_to_plot"]
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
    # Create a dataframe to plot
    disc_to_plot = pd.DataFrame(columns=["x", "y", "type", "name", "color", "size", "text", "label", "marker_symbol", "text_position", "nb_pubs"])
    # Add disciplines
    for i, disc in enumerate(disciplines):
        disc_to_plot.loc[len(disc_to_plot)] = {
            "x": embedded[i, 0],
            "y": embedded[i, 1],
            "type": "discipline",
            "name": disc,
            "color": disc_colors[i],
            "size": 30,
            "text": disc,
            "label": disc,
            "marker_symbol": "circle",
            "text_position": "middle center",
            "nb_pubs": 0
        }
    ####################################################################################################################
    # Disciplines
    ####################################################################################################################
    disc_trace = go.Scatter(
        name="Disciplines",
        x=disc_to_plot["x"].tolist(),
        y=disc_to_plot["y"].tolist(),
        mode='markers+text',
        marker=dict(
            color=disc_to_plot["color"].tolist(),
            size=disc_to_plot["size"].tolist(),
            symbol=disc_to_plot["marker_symbol"].tolist(),
            line=dict(width=0),
        ),
        text=disc_to_plot["text"].tolist(),
        textposition=disc_to_plot["text_position"].tolist(),
        hoverinfo='text',
        hovertext=disc_to_plot["label"].tolist(),
        opacity=1
    )
    print("disc_trace done")

    ####################################################################################################################
    # Plots
    ####################################################################################################################
    global df_to_plot
    df_to_plot = df_to_plot.sort_values(by=["name"], ascending=False)

    # Ignore the phd students with coordinates 0,0
    # disc_xs = list(disc_to_plot["x"])
    # disc_ys = list(disc_to_plot["y"])
    # df_to_plot = df_to_plot[(
    #         (df_to_plot["x"]!=0) | (df_to_plot["y"]!=0)
    # )]
    # Ignore the phd students with coordinates on discipline coordinates
    # df_to_plot = df_to_plot[(
    #         (~df_to_plot["x"].isin(disc_xs)) | (~df_to_plot["y"].isin(disc_ys))
    # )]

    # Remove students with no publications
    df_to_plot = df_to_plot[df_to_plot["nb_pubs"] > 0]

    # Sort the students by number of publications
    # phdStudents = main_df.sort_values(by=["num_pubs_student","id_scopus_student"], ascending=True)

    sample_size = len(main_df)
    # fig_student = go.Figure()

    ####################################################################################################################
    # Scatter plot of PhD students
    ####################################################################################################################
    phdStudents_go = go.Scattergl(
        name="PhD students",
        x=df_to_plot["x"].tolist(),
        y=df_to_plot["y"].tolist(),
        mode='markers',
        marker=dict(
            color=df_to_plot["color"].tolist(),
            size=df_to_plot["size"].tolist()
        ),
        opacity=1,
        hoverinfo='text',
        hovertext=df_to_plot["nb_pubs"].tolist(),
    )
    fig_student = go.Figure(phdStudents_go)
    fig_student.add_trace(disc_trace)
    fig_student.update_layout(
        showlegend=True,
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    print("phdStudents_go done")

    ####################################################################################################################
    # Heatmap of publications
    ####################################################################################################################
    hist, x_edges, y_edges, binnumber = stats.binned_statistic_2d(
        df_to_plot["x"].tolist(), df_to_plot["y"].tolist(), [math.exp(nb) for nb in df_to_plot["nb_pubs"].tolist()], statistic='mean', bins=[150,100]
    )
    # Convert 0 values to NaN for transparency
    hist = np.where(hist == 0, np.nan, hist)  # Set 0s to NaN
    pubs_heatmap = go.Heatmap(
        name="Publications heatmap",
        x = x_edges[:-1],
        y = y_edges[:-1],
        z = hist.T,
        colorscale="Plasma",
        hovertext=df_to_plot["nb_pubs"].tolist(),
        colorbar=dict(title='Number of publications'),
        showscale=True,
        showlegend=True
    )
    fig_pubs_heatmap = go.Figure(pubs_heatmap)
    fig_pubs_heatmap.add_trace(disc_trace)
    fig_pubs_heatmap.update_layout(
        title="Publications heatmap",
        showlegend=True,
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    print("pubs_heatmap done")

    ####################################################################################################################
    # Density heatmap
    ####################################################################################################################
    density_heatmap = go.Histogram2d(
        x=df_to_plot["x"],
        y=df_to_plot["y"],
        nbinsx=150,
        nbinsy=100,
        colorscale=["rgba(68, 1, 84,0)"]+px.colors.sequential.Viridis,
        colorbar=dict(title="Density"),
        name="Density heatmap",
        showscale=True,
        showlegend=True,
        histnorm="density"
    )
    fig_density_heatmap = go.Figure(density_heatmap)
    fig_density_heatmap.add_trace(disc_trace)
    fig_density_heatmap.update_layout(
        title="Density heatmap",
        showlegend=True,
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        # plot_bgcolor="rgb(0,0,0)",
    )

    print("density_heatmap done")

    ####################################################################################################################
    # Full figure
    ####################################################################################################################
    figure = go.Figure()
    figure.add_trace(pubs_heatmap)
    figure.add_trace(density_heatmap)
    figure.add_trace(disc_trace)
    figure.add_trace(phdStudents_go)
    figure.update_layout(
        title="Overlapping Figures",
        showlegend=True,
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    print("figures done")

    # fig_pubs_heatmap.write_image(f"./results/fig{sample_size}_productivity_heatmap.png")
    # fig_pubs_heatmap.write_html(f"./results/fig{sample_size}_productivity_heatmap.html")
    # fig_density_heatmap.write_image(f"./results/fig{sample_size}_density_heatmap_test.png")
    # fig_density_heatmap.write_html(f"./results/fig{sample_size}_density_heatmap_test.html")
    fig_student.write_image(f"./results/fig{sample_size}.png")
    fig_student.write_html(f"./results/fig{sample_size}.html")
    # figure.write_image(f"./results/fig{sample_size}_all.png")
    # figure.write_html(f"./results/fig{sample_size}_all.html")

    print("figures saved")

    print("sending fig_student")
    return {"graph": fig_student.to_json()}


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
