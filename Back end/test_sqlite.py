import pandas as pd
from pathlib import Path
import sqlite3

input_dir = Path(__file__).resolve().parent.parent / "data"

# Chargement sécurisé des fichiers CSV
datasets = {}
for filename in [
    "theses.csv"
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

# Connect to an SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('example.db')

# Create a cursor object using the cursor() method
cursor = conn.cursor()

# Create a table in the SQLite database use idref as primary key
cursor.executescript('''
DROP TABLE IF EXISTS researchers;
DROP TABLE IF EXISTS join_phd_sup;
CREATE TABLE researchers (
    idref TEXT PRIMARY KEY,
    nom TEXT,
    prenom TEXT,
    date_soutenance TEXT,
    discipline TEXT
);
CREATE TABLE join_phd_sup (
    idref_phd TEXT,
    date_soutenance TEXT,
    idref_sup TEXT,
    FOREIGN KEY (idref_phd) REFERENCES researchers(idref),
    FOREIGN KEY (idref_sup) REFERENCES researchers(idref),
    PRIMARY KEY (idref_phd, idref_sup, date_soutenance)
);
-- Efficiently look up all phds before a certain date
DROP INDEX IF EXISTS idx_phd_date;
CREATE INDEX idx_phd_date ON join_phd_sup (date_soutenance);
-- Efficiently look up all phd students for a supervisor
DROP INDEX IF EXISTS idx_sup_phd;
CREATE INDEX idx_sup_phd ON join_phd_sup (idref_sup);
''')

og_dict = {"COMP": ["000", "004"],
     "PSYC": ["020", "060", "070", "090", "100", "110", "120", "130", "140", "150", "160", "170", "180", "190", "200",
              "210", "220", "230", "240", "250", "260", "270", "280", "290"],
     "SOCI": ["300", "350", "360", "370", "380", "390"],
     "ECON": ["310", "320", "330", "340"],
     "ARTS": ["400", "410", "420", "430", "440", "450", "460", "470", "480", "490", "700", "710", "720", "730", "740",
              "750", "760", "770", "780", "790", "800", "810", "820", "830", "840", "850", "860", "870", "880", "890",
              "900", "910", "920", "930", "940", "944", "950", "960", "970", "980", "990"],
     "MATH": ["500", "510"],
     "PHYS": ["520", "530"],
     "CHEM": ["540"],
     "EART": ["550", "560"],
     "BIOC": ["570", "580", "590"],
     "ENGI": ["600", "620", "670", "680", "690"],
     "MEDI": ["610", "796"],
     "VETE": ["630"],
     "DECI": ["640"],
     "BUSI": ["650"],
     "CENGI": ["660"]
     }

d = {}
for word, values in og_dict.items():
    for value in values:
        d[value] = word

theses = datasets["theses"]

nb_directeurs = 6
director_ids = [f"directeurs_these.{i}.idref" for i in range(0, nb_directeurs + 1)]

# Students with no idref are assigned value of -1 * index
theses.loc[theses["auteur.idref"].isna(), "auteur.idref"] = ("P" + pd.Series(theses.index[theses["auteur.idref"].isna()]).astype(str)).values
# Directors with no idref are assigned of -1 * (own index + 1 + index of the student)
for i in range(0, nb_directeurs + 1):
    mask = theses[f"directeurs_these.{i}.idref"].isna() & (
        theses[f"directeurs_these.{i}.nom"].notna() | theses[f"directeurs_these.{i}.prenom"].notna()
    )
    theses.loc[mask, f"directeurs_these.{i}.idref"] = "D" + pd.Series(i + 1 + theses.index[mask]).astype(str)

students = theses[["auteur.idref","auteur.nom","auteur.prenom","date_soutenance","oai_set_specs"]]
students.columns = ["idref","nom","prenom","date_soutenance","discipline"]
# Clean the discipline column by removing the prefix "ddc:" and assigning the corresponding discipline based on the mapping
students["discipline"] = students["discipline"].str.replace("ddc:", "")
# If discipline contains "||", assign "MULT", otherwise map to the corresponding discipline or None
students["discipline"] = students["discipline"].apply(lambda x: "MULT" if type(x) is str and "||" in x else d.get(x, None))

join_phd_sup = theses[["auteur.idref"] + director_ids + ["date_soutenance"]]
join_phd_sup = join_phd_sup.melt(id_vars=["auteur.idref", "date_soutenance"], value_vars=director_ids, var_name="directeur", value_name="idref_sup")
join_phd_sup.drop(["directeur"], axis=1, inplace=True)
join_phd_sup.columns = ["idref_phd", "date_soutenance", "idref_sup"]
join_phd_sup.dropna(inplace=True)

# Show duplicates in the join_phd_sup table
duplicates = join_phd_sup[join_phd_sup.duplicated(subset=["idref_phd", "date_soutenance", "idref_sup"], keep=False)]
if not duplicates.empty:
    print("Duplicates found in join_phd_sup:")
    print(duplicates)
# Drop duplicates
join_phd_sup.drop_duplicates(subset=["idref_phd", "date_soutenance", "idref_sup"], inplace=True)

supervisors = pd.DataFrame(columns=["idref","nom","prenom"])
for i in range(0, nb_directeurs + 1):
    columns = [f"directeurs_these.{i}.idref",
               f"directeurs_these.{i}.nom",
               f"directeurs_these.{i}.prenom"]
    temp_df = theses[columns]
    temp_df.columns = ["idref","nom","prenom"]
    supervisors = pd.concat([supervisors, temp_df], ignore_index=True)

supervisors.dropna(inplace=True)
supervisors["date_soutenance"] = None
supervisors["discipline"] = None

researchers = pd.concat([students, supervisors], ignore_index=True)
researchers.drop_duplicates(subset="idref", inplace=True)

# Append data to tables
researchers.to_sql("researchers", conn, if_exists="append", index=False)
join_phd_sup.to_sql("join_phd_sup", conn, if_exists="append", index=False)

# Commit the changes
conn.commit()
# Close the connection
conn.close()