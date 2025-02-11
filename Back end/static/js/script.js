let selectedPhDs = new Set();
let showSupervisors = false;

let debounceTimeout;

async function searchThese() {
    clearTimeout(debounceTimeout);

    debounceTimeout = setTimeout(async () => {
        let query = document.getElementById("search").value.trim();
        let resultsDiv = document.getElementById("results");
        resultsDiv.innerHTML = "";

        if (query.length === 0) return;

        let loader = document.createElement("div");
        loader.className = "loader";
        loader.innerHTML = `
            <div></div>
            <div></div>
            <div></div>
        `;
        resultsDiv.appendChild(loader);

        let url = `/search?dataset=theses&q=${query}&columns_search=auteur.nom,auteur.prenom`;
        console.log("📡 Envoi de la requête :", url);

        try {
            let response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            let data = await response.json();
            console.log("📩 Réponse reçue :", data);

            resultsDiv.innerHTML = "";

            if (data.error) {
                resultsDiv.innerHTML = `<p style="color: red;">⚠️ ${data.error}</p>`;
                return;
            }

            if (data.length === 0) {
                resultsDiv.innerHTML = `<p>Aucun résultat trouvé.</p>`;
                return;
            }

            data.forEach(row => {
                if (!isAlreadySelected(row)) {
                    let entry = document.createElement("div");
                    entry.innerHTML = `
                        <p>
                            <strong>${row["auteur.nom"]} ${row["auteur.prenom"]}</strong> 
                            <span style="color: gray;">(${row.discipline || "Discipline inconnue"})</span>
                        </p>
                    `;
                    entry.className = "resultatTheses";
                    entry.onclick = () => addPhD(row);
                    resultsDiv.appendChild(entry);
                }
            });
        } catch (error) {
            resultsDiv.innerHTML = `<p style="color: red;">🚨 Erreur lors de la recherche.</p>`;
            console.error("Erreur :", error);
        }
    }, 1000);
}

function isAlreadySelected(phd) {
    const fullName = `${phd["auteur.prenom"]} ${phd["auteur.nom"]}`;
    return Array.from(selectedPhDs).some(selected => 
        `${selected["auteur.prenom"]} ${selected["auteur.nom"]}` === fullName
    );
}

function addPhD(phdStudent) {
    selectedPhDs.add(phdStudent);
    updateSelectedList();
    updateGraphWithAllPhDs();
}

function removePhD(fullName) {
    // Trouve le PhD à supprimer basé sur son nom complet
    for (let phd of selectedPhDs) {
        if (`${phd["auteur.prenom"]} ${phd["auteur.nom"]}` === fullName) {
            selectedPhDs.delete(phd);
            break;
        }
    }
    updateSelectedList();
    updateGraphWithAllPhDs();
}

function updateSelectedList() {
    const container = document.getElementById("selectedPhDs");
    container.innerHTML = "";
    
    selectedPhDs.forEach(phd => {
        const fullName = `${phd["auteur.prenom"]} ${phd["auteur.nom"]}`;
        const item = document.createElement("div");
        item.className = "selected-item";
        item.innerHTML = `
            <span>${fullName}</span>
            <button class="remove-btn" data-name="${fullName}">✕</button>
        `;
        
        // Ajoute l'écouteur d'événement au bouton
        const removeBtn = item.querySelector('.remove-btn');
        removeBtn.addEventListener('click', function() {
            removePhD(this.dataset.name);
        });
        
        container.appendChild(item);
    });
}

function toggleSupervisors() {
    showSupervisors = document.getElementById("showSupervisors").checked;
    updateGraphWithAllPhDs();
}

async function updateGraphWithAllPhDs() {
    if (selectedPhDs.size === 0) {
        document.getElementById("graph").innerHTML = "";
        return;
    }

    let supervisorsParams = [];
    let phdParams = [];

    selectedPhDs.forEach(phd => {
        const phdName = `${phd["auteur.prenom"]} ${phd["auteur.nom"]}`;
        phdParams.push(phdName);

        if (showSupervisors) {
            for (let i = 0; i < 7; i++) {
                const supName = phd[`directeurs_these.${i}.nom`];
                if (supName) {
                    const supFullName = `${supName} ${phd[`directeurs_these.${i}.prenom`]}`;
                    supervisorsParams.push(supFullName);
                }
            }
        }
    });

    await updateGraph(supervisorsParams.join(','), phdParams.join(','));
}

window.updateGraph = async function updateGraph(supervisor_names, phdStudentNames) {
    console.log("📡 Envoi de la requête AJAX pour le graphique...");
    try {
        let response = await fetch(`/update_graph?sup=${supervisor_names}&phd=${phdStudentNames}`);
        let graphJSON = await response.json();
        console.log("📊 Graphique reçu, mise à jour...");
        const graphDiv = document.getElementById("graph");
        Plotly.newPlot(graphDiv, graphJSON.data, graphJSON.layout);
    } catch (error) {
        console.error("🚨 Erreur lors de la mise à jour du graphique :", error);
    }
};