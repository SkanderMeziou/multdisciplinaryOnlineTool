import numpy as np
from collections import defaultdict
from flask import Flask, request, render_template, jsonify
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go  # ✅ Ajoute cette ligne !
from plotly.subplots import make_subplots
from sklearn.manifold import TSNE
import plotly.express as px
from datetime import datetime
import json
import logging
import traceback
from unidecode import unidecode
import os
import matplotlib
import matplotlib.cm
from multiprocessing import Pool
import pickle

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

def get_weights(author_name):
    """
    Pour un chercheur, retourne :
      - ids : liste d'ISSN valides
      - w   : vecteur numpy des poids normalisés
    """
    row = df_pubs[df_pubs['author_name'] == author_name]
    if row.empty:
        raise KeyError(f"Auteur '{author_name}' non trouvé dans researchers_publications")
    journals = row.iloc[0]['journals']
    pairs = []
    for j in journals:
        sid  = str(j.get('journal_id'))
        cnt  = j.get('count', 1) or 1
        issn = mapping_src2issn.get(sid)
        if issn and issn in df_jaccard.index:
            pairs.append((issn, int(cnt)))
    if not pairs:
        raise ValueError(f"Aucun journal mappé pour '{author_name}'")
    ids, counts = zip(*pairs)
    w = np.array(counts, dtype=float)
    w /= w.sum()
    return list(ids), w
nombre = 0
def barycenter_distance(ids1, w1, ids2, w2):
    """
    Calcule la distance euclidienne entre deux barycentres pondérés
    définis par (ids1, w1) et (ids2, w2).
    """
    # liste unique d'ISSN
    combined = []
    for x in ids1 + ids2:
        if x not in combined:
            combined.append(x)
    M  = df_jaccard.loc[combined, combined].values.astype(float)
    D2 = M**2
    a_idx = [combined.index(i) for i in ids1]
    b_idx = [combined.index(i) for i in ids2]
    # sous-blocs
    D2_ab = D2[np.ix_(a_idx, b_idx)]
    D2_aa = D2[np.ix_(a_idx, a_idx)]
    D2_bb = D2[np.ix_(b_idx, b_idx)]
    # calcul bilinéaire
    t_ab = w1 @ D2_ab @ w2
    t_aa = w1 @ D2_aa @ w1
    t_bb = w2 @ D2_bb @ w2
    d2   = t_ab - 0.5*t_aa - 0.5*t_bb
    print("distance n°",nombre,":",float(np.sqrt(max(d2, 0.0))))
    return float(np.sqrt(max(d2, 0.0)))

def _distance_worker(args):
    """
    args = (ids0, w0, other_author_name)
    Retourne (other_author_name, distance) ou None si erreur
    """
    ids0, w0, other = args
    try:
        ids1, w1 = get_weights(other)
        d = barycenter_distance(ids0, w0, ids1, w1)
        return (other, d)
    except Exception:
        return None
#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------chargement des donées---------------------------------------------------------
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
# Chargement des chercheurs (fichier généré en .parquet)
researchers_file = input_dir / "researchers_publications.parquet"
if researchers_file.exists():
    researchers_df = pd.read_parquet(researchers_file)
    datasets["researchers"] = researchers_df
    print("✅ Fichier des chercheurs chargé :", researchers_df.shape)
else:
    print("⚠️ Fichier des chercheurs manquant :", researchers_file)
# chargement jorunaux 
journal_positions_file = input_dir / "umap_positions_with_source_id.parquet"
if journal_positions_file.exists():
    journal_positions_df = pd.read_parquet(journal_positions_file)
    datasets["journal_positions"] = journal_positions_df
    print("✅ Fichier des positions UMAP des journaux chargé :", journal_positions_df.shape)
else:
    print("⚠️ Fichier umap_positions.parquet manquant :", journal_positions_file)

# chargement chercheurs position  
searchers_positions_file = input_dir / "researchers_barycentres.parquet"
if searchers_positions_file.exists():
    searchers_positions_df = pd.read_parquet(searchers_positions_file)
    datasets["searchers_positions"] = searchers_positions_df
    print("✅ Fichier des positions UMAP des journaux chargé :", searchers_positions_df.shape)
else:
    print("⚠️ Fichier umap_positions.parquet manquant :", searchers_positions_file)

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
jaccard_file = input_dir / "jaccard_overall.parquet"
if jaccard_file.exists():
    df_j = pd.read_parquet(jaccard_file)
    # indexation sur ISSN/EISSN
    if 'issn' in df_j.columns:
        df_j.set_index('issn', inplace=True)
    elif 'index' in df_j.columns:
        df_j.set_index('index', inplace=True)
    df_j.index = df_j.index.astype(str)
    df_j.columns = df_j.columns.astype(str)
    datasets["jaccard"] = df_j
else:
    raise FileNotFoundError(f"{jaccard_file} introuvable")

# Récupération rapide
df_jaccard    = datasets["jaccard"]
df_pubs       = datasets["researchers"]
df_umap       = datasets["journal_positions"]

#faiss
import faiss

# Initialisation
faiss_index = None
barycenters = None
author_names = None

def load_faiss_index():
    global faiss_index, barycenters, author_names
    faiss_pkl = input_dir / "faiss_barycenters.pkl"
    with open(faiss_pkl, "rb") as f:
        data = pickle.load(f)
        barycenters = np.array(data["barycenters"]).astype("float32")
        author_names = data["author_names"]
    print(f"[FAISS] Barycentres chargés : {len(author_names)} chercheurs")
    d = barycenters.shape[1]
    faiss_index = faiss.IndexFlatL2(d)
    faiss_index.add(barycenters)
    print(f"[FAISS] Index FAISS construit avec {len(author_names)} vecteurs.")

# Charger l’index FAISS au démarrage
load_faiss_index()
# mapping source-id → ISSN/EISSN
mapping_src2issn = df_umap.set_index('source-id')['id'].astype(str).to_dict()
print("Datasets chargés avec succès :", list(datasets.keys()))

# --- Mapping source-id -> issn
journal_mapping_file = input_dir / "journal_mapping.parquet"
if journal_mapping_file.exists():
    journal_mapping_df = pd.read_parquet(journal_mapping_file)
    sourceid_to_issn = dict(zip(journal_mapping_df['source-id'].astype(str), journal_mapping_df['issn'].astype(str)))
else:
    sourceid_to_issn = {}

# --- Embeddings de journaux
journals_emb_file = input_dir / "journalsEmb.parquet"
if journals_emb_file.exists():
    journals_df = pd.read_parquet(journals_emb_file)
    journal_embs = journals_df.set_index('ID').dropna().astype(float)
    journal_embs.index = journal_embs.index.astype(str)
else:
    journal_embs = pd.DataFrame()

# Mapping des disciplines vers leurs coordonnées
coord_cols = [c for c in coordinates_df.columns]
disc_to_coord = {
    row["disc"]: row[coord_cols].to_numpy()
    for _, row in datasets["coordinates"].iterrows()
}
# === Chargement author_publications pour la trajectoire disciplinaire ===
author_publications_file = input_dir / "author_publications.parquet"
if author_publications_file.exists():
    df_pub = pd.read_parquet(author_publications_file)
    print("✅ Fichier author_publications chargé :", df_pub.shape)
else:
    print("⚠️ Fichier author_publications.parquet manquant :", author_publications_file)
    df_pub = pd.DataFrame()

def get_author_publications_fast(author_name):
    author_name_norm = unidecode(author_name.strip().lower())
    if not author_name_norm:
        return {}
    first_letter = author_name_norm.split()[0][0].upper()
    split_dir = input_dir / "author_publications_dir"
    split_file = split_dir / f"{first_letter}.parquet"
    print("Recherche pour:", author_name_norm, "dans", split_file)
    if not split_file.exists():
        print("Fichier inexistant !")
        return {}

    df_letter = pd.read_parquet(split_file)
    print("Colonnes:", df_letter.columns)
    # attention à la colonne : "author" ou "author_name" ?
    col = "author"
    if "author" not in df_letter.columns and "author_name" in df_letter.columns:
        col = "author_name"
    df_letter["author_norm"] = df_letter[col].apply(lambda s: unidecode(s.strip().lower()))
    print("Noms dans le fichier :", df_letter["author_norm"].unique()[:10])
    df_filtered = df_letter[df_letter["author_norm"] == author_name_norm]
    print("Lignes trouvées :", len(df_filtered))
    pub_dict = defaultdict(lambda: defaultdict(int))
    for _, row in df_filtered.iterrows():
        discipline = row["discipline"]
        year = row["year"]
        if pd.notnull(year) and pd.notnull(discipline):
            pub_dict[int(year)][discipline] += 1
    return pub_dict
#-----------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------application et routes---------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------

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
    disc_to_plot = pd.DataFrame(columns=["x", "y", "type", "name", "color", "size", "text", "label","marker_symbol", "text_position"])
    df_to_plot = pd.DataFrame(columns=["x", "y", "type", "name", "color", "size", "text", "label", "marker_symbol", "text_position"])
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
    phdStudents = main_df[main_df["id_scopus_student"].isin(phdIds)]

    for i, student in phdStudents.iterrows():
        print("Processing student : ",student["name_student"])
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
            label = f"{student_name} ({main_disc}) n'a pas de publications"
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
            "marker_symbol": "triangle-up",
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
                label2 = f"supervise {student_name}"
                coordinates = areas.dot(embedded)
                df_to_plot.loc[len(df_to_plot)] = {
                    "x": coordinates[0],
                    "y": coordinates[1],
                    "type": "superviseur",
                    "name": supervisor_name,
                    "color": disc_colors[disc_index],
                    "size": 10,
                    "text": supervisor_name,
                    "label": label+"<br>"+label2,
                    "marker_symbol": "square",
                    "text_position": "top right"
                }

    # Create the figure
    phdStudents_go = go.Scatter(
        name = "Doctorants",
        x=df_to_plot["x"].tolist(),
        y=df_to_plot["y"].tolist(),
        mode='markers+text',
        marker=dict(
            color=df_to_plot["color"].tolist(),
            size=df_to_plot["size"].tolist(),
            symbol=df_to_plot["marker_symbol"].tolist()
        ),
        text=df_to_plot["name"].tolist(),
        hoverinfo='text',
        hovertext=df_to_plot["label"].tolist(),
        textposition=df_to_plot["text_position"].tolist()
    )

    fig_student = go.Figure()
    fig_student.add_trace(phdStudents_go)

    x = df_to_plot["x"]
    y = df_to_plot["y"]
    colors = df_to_plot["color"]
    # Add arrows
    arrows = []
    if len(x) > len(disciplines):
        for i in range(len(disciplines), len(x)):
            arrows.append(create_arrow(x[i], y[i], colors[i]))

    for arrow in arrows:
        fig_student.add_annotation(arrow)

    fig_student.update_layout(
        title="Doctorants et Superviseurs",
        xaxis = dict(showticklabels=False),
        yaxis = dict(showticklabels=False)
    )

    # fig.write_image("fig1.png")

    fig_stats = make_subplots(rows = 2, cols = 1, subplot_titles=["Nombre d'étudiants par nombre de publications", "Nombres par discipline"]
)

    # Additional statistical plots on shown students
    if phdStudents.shape[0] > 0:
        # Number of students per number of publications, hover bubble has list of all student names
        # dict grouped by number of publications
        grouped_dict = phdStudents.groupby("num_pubs_student")["name_student"].apply(list).to_dict()
        fig_stats.add_trace(
            go.Bar(
                name="Nombre d'étudiants par nombre de publication",
                x=list(grouped_dict.keys()),
                y=[len(v) for v in grouped_dict.values()],
                hoverinfo="y+text",
                text = "étudiants",
                marker=dict(color="blue"),
                legendgroup='1',
            ),
            row=1, col=1
        )
        # Number of publications per discipline
        # dict grouped by discipline
        grouped_dict = phdStudents.groupby("discipline_student_scopus")["num_pubs_student"].sum().to_dict()
        fig_stats.add_trace(
            go.Bar(
                name="Publications",
                x=list(grouped_dict.keys()),
                y=list(grouped_dict.values()),
                hoverinfo="y+text",
                text = "publications",
                marker=dict(color="red"),
                legendgroup='2',
            ),
            row=2, col=1
        )
        # Mean number of publication per student per discipline
        # dict grouped by discipline
        grouped_dict = phdStudents.groupby("discipline_student_scopus")["num_pubs_student"].mean().to_dict()
        fig_stats.add_trace(
            go.Bar(
                name="Publications moyennes",
                x=list(grouped_dict.keys()),
                y=list(grouped_dict.values()),
                hoverinfo="y+text",
                text = "publications",
                marker=dict(color="orange"),
                legendgroup='2',
            ),
            row=2, col=1
        )
        # Number of students per discipline
        # dict grouped by discipline
        grouped_dict = phdStudents.groupby("discipline_student_scopus")["name_student"].apply(list).to_dict()
        fig_stats.add_trace(
            go.Bar(
                name="Étudiants",
                x=list(grouped_dict.keys()),
                y=[len(v) for v in grouped_dict.values()],
                hoverinfo="y+text",
                text = "étudiants",
                marker=dict(color="green"),
                legendgroup='2',
            ),
            row=2, col=1
    )
    fig_stats.update_layout(
        title="Statistiques sur la population choisie",
        xaxis1_title="Nombre de publications",
        yaxis1_title="Nombre d'étudiants",
        height=1000,
        legend_tracegroupgap=500,
        yaxis2_title = "Nombres par discipline",
        xaxis2_title = "Disciplines"
    )

    return {"graph" : fig_student.to_json(),
            "stats" : fig_stats.to_json()}

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

@app.route("/chercheur")
def chercheur_page():
    researchers = datasets.get("researchers")
    if researchers is None:
        return "Aucune donnée sur les chercheurs chargée"
    
    # Liste alphabétique des auteurs
    author_list = sorted(researchers["author_name"].unique())
    return render_template("chercheur.html", authors=author_list)

@app.route("/trajectory")
def trajectory_page():
    researchers = datasets.get("researchers")
    if researchers is None:
        return "Aucune donnée sur les chercheurs chargée"
    
    author_list = sorted(researchers["author_name"].unique())
    return render_template("trajectoire.html", authors=author_list)

@app.route("/barycentre_auteur")
def barycentre_auteur():
    try:
        author = request.args.get("name", "")
        if not author:
            return jsonify({"error": "Paramètre name requis"}), 400

        researchers = datasets.get("researchers")
        coords      = datasets.get("journal_positions")
        if researchers is None or coords is None:
            return jsonify({"error": "Données manquantes"}), 500

        # 1) Normalisation légère du nom d'auteur
        norm = lambda s: unidecode(s).casefold().strip()
        row  = researchers[researchers["author_name"].apply(norm) == norm(author)]
        if row.empty:
            return jsonify({"error": "Auteur non trouvé"}), 404

        # 2) Extraction et conversion en liste Python
        journals_raw = row.iloc[0]["journals"]
        if isinstance(journals_raw, np.ndarray):
            journals_list = journals_raw.tolist()
        elif isinstance(journals_raw, list):
            journals_list = journals_raw
        else:
            journals_list = []

        # 3) Nettoyage et extraction du journal_id + count
        clean = []
        for it in journals_list:
            if not isinstance(it, dict):
                continue
            sid = it.get("journal_id")
            if not sid:
                continue
            try:
                cnt = int(it.get("count", 1))
            except (ValueError, TypeError):
                cnt = 1
            clean.append({"source-id": str(sid), "count": max(cnt, 1)})

        if not clean:
            return jsonify({"error": "Aucun source‑id exploitable"}), 404

        # 4) Préparation du DataFrame UMAP des journaux, avec leur nom
        coord_df = coords.copy()
        # si la colonne s'appelle "id" et pas "source-id"
        if "id" in coord_df.columns and "source-id" not in coord_df.columns:
            coord_df = coord_df.rename(columns={"id": "source-id"})
        coord_df["source-id"] = coord_df["source-id"].astype(str)
        # on garde aussi le nom du journal
        coord_df = coord_df[["source-id", "name", "UMAP-1", "UMAP-2", "discipline"]]

        # 5) Jointure pour retrouver les coordonnées de chaque journal
        merged = pd.merge(pd.DataFrame(clean), coord_df, on="source-id")
        if merged.empty:
            return jsonify({"error": "Aucune coordonnée trouvée"}), 404

        # 6) Calcul du barycentre pondéré
        w = merged["count"].to_numpy()
        v = merged[["UMAP-1", "UMAP-2"]].to_numpy()
        bar = (w[:, None] * v).sum(axis=0) / w.sum()

        # 7) Construire la liste des journaux à renvoyer
        journals = []
        for _, jr in merged.iterrows():
            journals.append({
                "name":  jr["name"],
                "x":     float(jr["UMAP-1"]),
                "y":     float(jr["UMAP-2"]),
                "count":      int(jr["count"]),
                "discipline": jr.get("discipline", "UNKNOWN"),
                "source_id":  jr["source-id"] 
            })

        # 8) Réponse JSON enrichie
        return jsonify({
            "x":                   float(bar[0]),
            "y":                   float(bar[1]),
            "dominant_discipline": row.iloc[0].get("dominant_discipline", "UNKNOWN"),
            "journals":            journals
        })

    except Exception as e:
        logging.error("Erreur barycentre_auteur : %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "Erreur serveur"}), 500

@app.route("/search_researcher")
def search_researcher():
    query = request.args.get("q", "").strip().lower()
    if "researchers" not in datasets:
        return jsonify([])

    df = datasets["researchers"]
    df["search_name"] = df["author_name"].str.lower().fillna("")
    df = df[df["search_name"].str.contains(query)]

    results = df["author_name"].drop_duplicates().head(20).tolist()
    return jsonify(results)

@app.route("/closer_researchers")
def get_closer_researchers():
    # 1) Récupérer et valider les paramètres
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Paramètre 'name' requis"}), 400

    try:
        k = int(request.args.get("k", 5))
    except ValueError:
        return jsonify({"error": "Le paramètre 'k' doit être un entier"}), 400

    # 2) On récupère le DataFrame des positions UMAP des chercheurs
    df_searchers = datasets.get("searchers_positions")
    if df_searchers is None:
        return jsonify({"error": "Données chercheurs manquantes"}), 500

    # 3) Normalisation simple pour la recherche de nom
    norm = unidecode(name).casefold().strip()
    if "norm_name" not in df_searchers.columns:
        df_searchers["norm_name"] = (
            df_searchers["author_name"]
            .fillna("")
            .map(lambda s: unidecode(s).casefold().strip())
        )

    # 4) On trouve la ligne du chercheur cible
    mask = df_searchers["norm_name"] == norm
    if not mask.any():
        return jsonify({"error": f"Chercheur '{name}' non trouvé"}), 404

    target = df_searchers[mask].iloc[0]
    x0, y0 = target["x"], target["y"]

    # 5) Calcul des distances euclidiennes à tous les autres
    others = df_searchers.loc[df_searchers.index != target.name].copy()
    others["distance"] = np.hypot(others["x"] - x0, others["y"] - y0)

    # 6) Sélection des k plus proches
    nearest = others.nsmallest(k, "distance")

    # 7) Préparation de la réponse
    result = (
        nearest[["author_name", "x", "y", "distance"]]
        .rename(columns={"author_name": "name"})
        .to_dict(orient="records")
    )
    return jsonify(result)

@app.route("/researcher_info")
def researcher_info():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Paramètre name requis"}), 400

    # on cherche dans ton DataFrame researchers_df
    row = researchers_df[researchers_df["author_name"] == name]
    if row.empty:
        return jsonify({"error": "Chercheur non trouvé"}), 404

    row = row.iloc[0]
    # extrait les journaux et trie par count décroissant
    pubs = sorted(row["journals"], key=lambda j: j["count"], reverse=True)[:10]
    top10 = [
        {"journal_id": j["journal_id"], "count": j["count"]}
        for j in pubs
    ]

    return jsonify({
        "author_name": name,
        "dominant_discipline": row.get("dominant_discipline","UNKNOWN"),
        "top10_journals": top10,
        # tu peux ajouter d'autres champs ici…
    })

@app.route("/closer_researchers_jaccard")
def get_closer_researchers_jaccard():
    import time
    t0 = time.time()
    name = request.args.get("name", "").strip()
    print("[JACCARD] 0. Début endpoint")
    if not name:
        return jsonify({"error": "Paramètre 'name' requis"}), 400

    try:
        k = int(request.args.get("k", 5))
    except ValueError:
        return jsonify({"error": "Le paramètre 'k' doit être un entier"}), 400

    df_journals = datasets.get("researchers")
    df_positions = datasets.get("searchers_positions")
    print(f"[JACCARD] 1. Récupéré les datasets en {time.time() - t0:.3f}s")
    if df_journals is None or df_positions is None:
        return jsonify({"error": "Données chercheurs manquantes"}), 500

    norm = unidecode(name).casefold().strip()
    for df in (df_journals, df_positions):
        if "norm_name" not in df.columns:
            df["norm_name"] = (
                df["author_name"]
                .fillna("")
                .map(lambda s: unidecode(s).casefold().strip())
            )
    print(f"[JACCARD] 2. Normalisation faite en {time.time() - t0:.3f}s")

    row_journals = df_journals[df_journals["norm_name"] == norm]
    row_position = df_positions[df_positions["norm_name"] == norm]
    if row_journals.empty or row_position.empty:
        print("[JACCARD] 3. Chercheur non trouvé")
        return jsonify({"error": f"Chercheur '{name}' non trouvé"}), 404
    row_journals = row_journals.iloc[0]
    row_position = row_position.iloc[0]
    x0, y0 = row_position["x"], row_position["y"]
    print(f"[JACCARD] 3. Récupéré chercheur cible en {time.time() - t0:.3f}s")

    positions_others = df_positions.loc[df_positions["norm_name"] != norm].copy()
    positions_others["distance"] = np.hypot(positions_others["x"] - x0, positions_others["y"] - y0)
    print(f"[JACCARD] 4. Distances UMAP calculées en {time.time() - t0:.3f}s")

    close_names = set(positions_others[positions_others["distance"] <= 0.5]["norm_name"])
    print(f"[JACCARD] 5. Gardé {len(close_names)} voisins à <0.5 en {time.time() - t0:.3f}s")

    filtered_journals = df_journals[df_journals["norm_name"].isin(close_names)]
    print(f"[JACCARD] 6. Filtrage DF : {filtered_journals.shape[0]} chercheurs proches")

    def get_journal_vector(row):
        v = {}
        for j in row["journals"]:
            v[j["journal_id"]] = v.get(j["journal_id"], 0) + j["count"]
        return v

    v0 = get_journal_vector(row_journals)
    print(f"[JACCARD] 7. Vecteur du chercheur cible prêt en {time.time() - t0:.3f}s")
    results = []

    def jaccard_weighted(v1, v2):
        keys = set(v1) | set(v2)
        min_sum = sum(min(v1.get(k, 0), v2.get(k, 0)) for k in keys)
        max_sum = sum(max(v1.get(k, 0), v2.get(k, 0)) for k in keys)
        if max_sum == 0:
            return 0.0
        return min_sum / max_sum

        # On prépare un dict rapide pour retrouver les positions UMAP (accès instantané)
    positions_dict = {
        row["norm_name"]: (row["x"], row["y"])
        for _, row in df_positions.iterrows()
    }

    t_loop = time.time()
    print(f"[JACCARD]", end="")
    numberI = 0
    for idx, row in filtered_journals.iterrows():
        numberI += 1
        if numberI % 1000 == 0:
            print(numberI, " ", end="")

        v = get_journal_vector(row)
        score = jaccard_weighted(v0, v)
        x, y = positions_dict.get(row["norm_name"], (None, None))
        results.append({
            "name": row["author_name"],
            "similarity": score,
            "x": x,
            "y": y,
        })
    print("fin")
    print(f"[JACCARD] 8. Boucle des similarités de Jaccard sur {filtered_journals.shape[0]} chercheurs en {time.time() - t_loop:.3f}s")

    results = sorted(results, key=lambda r: -r["similarity"])[:k]
    print(f"[JACCARD] 9. Tri et retour final en {time.time() - t0:.3f}s")
    return jsonify(results)

@app.route("/closer_researchers_faiss")
def closer_researchers_faiss():
    global faiss_index, barycenters, author_names

    name = request.args.get("name", "").strip()
    k = int(request.args.get("k", 10))

    if not name:
        return jsonify({"error": "Paramètre 'name' requis"}), 400

    # Chercheur FAISS
    try:
        idx = author_names.index(name)
    except ValueError:
        return jsonify({"error": f"Chercheur '{name}' non trouvé"}), 404

    # Lookup FAISS
    query_bary = barycenters[idx].reshape(1, -1).astype('float32')
    D, I = faiss_index.search(query_bary, k+1)
    nearest_idx = I[0][1:k+1]
    nearest_authors = [author_names[i] for i in nearest_idx]
    nearest_dists = [float(d) for d in D[0][1:k+1]]

    # Lookup coordonnées UMAP (DataFrame chargé UNE FOIS, pas à chaque appel)
    df_positions = datasets["searchers_positions"]
    # Normalisation au chargement ! (jamais dans la route)
    if "norm_name" not in df_positions.columns:
        df_positions["norm_name"] = (
            df_positions["author_name"].fillna("").map(lambda s: unidecode(s).casefold().strip())
        )
    df_unique = df_positions.drop_duplicates("norm_name", keep="first")
    pos_dict = df_unique.set_index("norm_name")[["x", "y"]].to_dict(orient="index")

    # Formatage résultat
    def norm_name(nom):
        return unidecode(nom).casefold().strip()

    results = []
    for n, d in zip(nearest_authors, nearest_dists):
        coords = pos_dict.get(norm_name(n), {"x": None, "y": None})
        results.append({
            "name": n,
            "distance": d,
            "x": coords["x"],
            "y": coords["y"]
        })

    return jsonify(results)

@app.route("/journal_stats")
def journal_stats():
    # params: journal_id (source-id), authors=[list json]
    journal_id = request.args.get("journal_id", "")
    authors = request.args.get("authors", "[]")
    try:
        authors = json.loads(authors)
    except Exception:
        return jsonify({"error": "Invalid authors param"}), 400
    stats = []
    for a in authors:
        row = researchers_df[researchers_df["author_name"] == a]
        count = 0
        if not row.empty:
            for j in row.iloc[0]["journals"]:
                if str(j["journal_id"]) == str(journal_id):
                    count += j.get("count", 1)
        stats.append({"author": a, "count": count})
    return jsonify({"stats": stats})



@app.route("/journal_closest_authors")
def journal_closest_authors():
    journal_id = request.args.get("journal_id", "")
    k = int(request.args.get("k", 5))
    # Utilise ton mapping source-id → issn puis issn → emb
    issn = sourceid_to_issn.get(str(journal_id))
    if not issn or issn not in journal_embs.index:
        return jsonify([])  # Pas trouvé
    emb = journal_embs.loc[issn].values.astype("float32").reshape(1, -1)
    # On suppose que tu as déjà faiss_index, barycenters, author_names chargés (cf ton script)
    D, I = faiss_index.search(emb, k)
    out = []
    for i, d in zip(I[0], D[0]):
        out.append({"author": author_names[i], "distance": float(d)})
    return jsonify(out)

@app.route("/trajectory_plot")
def trajectory_plot():
    author = request.args.get("name", "")
    window_size = request.args.get("window", default=None, type=int)
    if window_size == 0:
        window_size = None

    try:
        # --- Utilise exactement ta logique locale ---
        pub_data = get_author_publications_fast(author)
        if not pub_data:
            return jsonify({"error": f"Aucune publication trouvée pour {author}"}), 404

        trajectory = []
        all_years = sorted(pub_data)

        for idx, year in enumerate(all_years):
            if window_size is None:
                selected_years = all_years[:idx + 1]
            else:
                selected_years = [y for y in all_years if year - window_size < y <= year]
            if not selected_years:
                continue

            aggregated = defaultdict(int)
            for y in selected_years:
                for disc, count in pub_data[y].items():
                    aggregated[disc] += count

            total = sum(aggregated.values())
            coords = np.array([
                disc_to_coord[disc] * weight / total
                for disc, weight in aggregated.items()
                if disc in disc_to_coord
            ])
            if len(coords) == 0:
                continue
            bary = np.sum(coords, axis=0)
            trajectory.append((year, bary))

        fig = go.Figure()

        for disc, coord in disc_to_coord.items():
            fig.add_trace(go.Scatter(
                x=[coord[0]],
                y=[coord[1]],
                mode='markers+text',
                marker=dict(size=8, color='lightgray'),
                text=[disc],
                textposition='top center',
                showlegend=False
            ))

        n_seg = len(trajectory) - 1
        if n_seg > 0:
            cmap = matplotlib.cm.get_cmap('viridis', n_seg + 1)
            for i in range(n_seg):
                x0, y0 = np.array(trajectory[i][1]).flatten()[:2]
                x1, y1 = np.array(trajectory[i+1][1]).flatten()[:2]
                color = matplotlib.colors.rgb2hex(cmap(i))
                year_label = str(trajectory[i+1][0])[-2:]

                fig.add_trace(go.Scatter(
                    x=[x0, x1],
                    y=[y0, y1],
                    mode="lines+markers+text",
                    line=dict(color=color, width=4),
                    marker=dict(size=12, color=color),
                    text=[None, year_label],
                    textposition='bottom right',
                    showlegend=False,
                    hoverinfo="text",
                ))
        else:
            # Si un seul point, on affiche quand même
            x0, y0 = np.array(trajectory[0][1]).flatten()[:2]
            fig.add_trace(go.Scatter(
                x=[x0],
                y=[y0],
                mode="markers+text",
                marker=dict(size=12, color='blue'),
                text=[str(trajectory[0][0])[-2:]],
                textposition='bottom right',
                showlegend=False,
            ))

        for i in range(len(trajectory) - 1):
            fig.add_annotation(
                ax=trajectory[i][1][0],
                ay=trajectory[i][1][1],
                x=trajectory[i+1][1][0],
                y=trajectory[i+1][1][1],
                showarrow=True,
                arrowhead=3,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="blue"
            )

        mode_label = f" (fenêtre {window_size} ans)" if window_size else " (cumulatif)"
        fig.update_layout(
            title=f"Trajectoire disciplinaire de {author.title()}{mode_label}",
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False),
            legend=dict(x=0.02, y=0.98)
        )
        # --- NE PAS FAIRE .show() EN FLASK ---
        return fig.to_json()

    except Exception as e:
        import traceback
        return jsonify({"error": f"{str(e)}\n{traceback.format_exc()}"}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)