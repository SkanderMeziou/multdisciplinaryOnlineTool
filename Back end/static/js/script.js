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
            <button class="remove-btn" data-name="${fullName}"><b>✕</b></button>
        `;

        // Ajoute l'écouteur d'événement au bouton
        const removeBtn = item.querySelector('.remove-btn');
        removeBtn.addEventListener('click', function() {
            removePhD(this.dataset.name);
        });

        // Ajoute les écouteurs d'événements pour le survol
        item.addEventListener('mouseenter', () => highlightPhD(fullName));
        item.addEventListener('mouseleave', () => unhighlightPhD(fullName));

        container.appendChild(item);
    });
}

function highlightPhD(fullName) {
    const graphDiv = document.getElementById("graph");
    if (!graphDiv.data || !graphDiv.data[0] || !graphDiv.data[0].marker) {
        console.warn("Le graphique n'est pas encore initialisé ou ne contient pas les données attendues");
        return;
    }

    // Obtenir les tailles actuelles
    const currentSizes = graphDiv.data[0].marker.size;
    const index = graphDiv.data[0].text.indexOf(fullName);

    if (index !== -1) {
        // Créer un nouveau tableau de tailles en préservant les tailles originales
        const newSizes = currentSizes.map((size, i) => {
            if (i === index) {
                // Augmenter la taille du point survolé
                return size * 3;
            }
            // Garder les tailles originales pour les autres points
            return size;
        });

        Plotly.restyle(graphDiv, {
            'marker.size': [newSizes]
        });
    }
}

function unhighlightPhD(fullName) {
    const graphDiv = document.getElementById("graph");
    if (!graphDiv.data || !graphDiv.data[0] || !graphDiv.data[0].marker) {
        console.warn("Le graphique n'est pas encore initialisé ou ne contient pas les données attendues");
        return;
    }

    const sizes = graphDiv.data[0].marker.size;
    const index = graphDiv.data[0].text.indexOf(fullName);

    if (index !== -1) {
        // Restaurer les tailles originales basées sur la couleur
        let newSizes = sizes
        newSizes[index] = sizes[index] / 3;

        Plotly.restyle(graphDiv, {
            'marker.size': [newSizes]
        });
    }
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

document.addEventListener('DOMContentLoaded', function() {
    const reportButton = document.getElementsByClassName('reportButton')[0];
    const reportModal = document.getElementById('reportModal');
    const closeButton = document.querySelector('.close');
    const reportForm = document.getElementById('reportForm');

    reportButton.addEventListener('click', function() {
        reportModal.style.display = 'block';
    });

    closeButton.addEventListener('click', function() {
        reportModal.style.display = 'none';
    });

    window.addEventListener('click', function(event) {
        if (event.target == reportModal) {
            reportModal.style.display = 'none';
        }
    });

    reportForm.addEventListener('submit', function(event) {
        event.preventDefault();
    
        // Récupérer les valeurs du formulaire
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const issue = document.getElementById('issue').value.trim();

        if (!name || !email || !issue) {
            alert("Tous les champs sont obligatoires !");
            return;
        }

        const reportData = { name, email, issue };

        console.log("📡 Données envoyées :", reportData); // 🔍 Debugging

        // Envoyer la requête POST au serveur Flask
        fetch("/report", {
            method: "POST",
            body: JSON.stringify(reportData),
            headers: { "Content-Type": "application/json" }
        })
        .then(response => response.text()) // Affiche la réponse brute pour voir si c'est un JSON valide
        .then(data => {
            console.log("📩 Réponse brute:", data);
            return JSON.parse(data);
        })
        .then(parsedData => {
            console.log("✅ Succès:", parsedData);
            alert(parsedData.message); // Afficher le message de succès
            reportModal.style.display = 'none';
            reportForm.reset(); // Vider le formulaire après envoi
        })
        .catch(error => console.error("🚨 Erreur de parsing JSON:", error));
    });
});

document.addEventListener('DOMContentLoaded', function() {
    document.querySelector(".tenRandom").addEventListener("click", selectRandomPhDs);
});

function selectRandomPhDs() {
    let resultsDiv = document.getElementById("results");
    let availablePhDs = Array.from(resultsDiv.getElementsByClassName("resultatTheses"));

    if (availablePhDs.length === 0) {
        alert("Aucun thésard disponible dans la liste !");
        return;
    }

    let count = Math.min(10, availablePhDs.length);
    let selected = getRandomElements(availablePhDs, count);

    let phdsToAdd = [];

    selected.forEach(entry => {
        // Récupérer les données du thésard sans déclencher un clic
        let fullName = entry.querySelector("strong").innerText;
        let discipline = entry.querySelector("span").innerText.replace(/[()]/g, "");
        
        phdsToAdd.push({
            "auteur.nom": fullName.split(" ")[1], 
            "auteur.prenom": fullName.split(" ")[0], 
            "discipline": discipline
        });
    });

    // Ajouter les 10 thésards en une seule fois
    addMultiplePhDs(phdsToAdd);
}


function getRandomElements(array, num) {
    let shuffled = array.slice().sort(() => 0.5 - Math.random());
    return shuffled.slice(0, num);
}

function addMultiplePhDs(phdsList) {
    let shouldUpdateGraph = false;

    phdsList.forEach(phd => {
        if (!isAlreadySelected(phd)) {
            selectedPhDs.add(phd);
            shouldUpdateGraph = true;
        }
    });

    updateSelectedList();
    
    if (shouldUpdateGraph) {
        updateGraphWithAllPhDs(); // Appel unique à la fin
    }
}

function deleteAll(){
    console.log("reset phd list")
    selectedPhDs.clear();
    updateSelectedList();
    updateGraphWithAllPhDs();
}