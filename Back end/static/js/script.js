let selectedPhDs = new Set();
let showSupervisors = false;
const nb_sups = 2;

async function filter_supervisors(discs) {
    console.log("ca fait des trucs");
    let url = `/filter_supervisors?discs=` + discs;
    console.log("📡 Envoi de la requête :", url);
    try {
        await fetch(url, { method: "GET" }); // No need to handle response
        console.log("Request sent successfully.");
    } catch (error) {
        console.error("Error sending request:", error);
    }
}

async function filter_students() {
    let multidisciplinarity_value = document.getElementById("multidisciplinarity_input").value;
    let nb_pubs_value = document.getElementById("nb_pubs_input").value;
    let url = `/filter?multidisciplinarity=`+ multidisciplinarity_value+`&nb_pubs=`+nb_pubs_value;
    console.log("📡 Envoi de la requête :", url);
    let loader = document.createElement("div");
        loader.className = "loader";
        loader.innerHTML = `
            <div></div>
            <div></div>
            <div></div>
        `;
        let filtersDiv = document.getElementById("filter_container");
        filtersDiv.appendChild(loader);
    try {
        await fetch(url, { method: "GET" }); // No need to handle response
        console.log("Request sent successfully.");
    } catch (error) {
        console.error("Error sending request:", error);
    }
    // launch search again
    filtersDiv.removeChild(loader);
    await searchThese();
}

function clearResults() {
    document.getElementById("results").innerHTML = "";
    document.getElementById("search").value = "";
}


document.addEventListener('DOMContentLoaded', function() {
    let disciplines = ['AGRI', 'ARTS', 'BIOC', 'BUSI', 'CENG', 'CHEM', 'COMP', 'DECI', 'DENT', 'EART',
               'ECON', 'ENER', 'ENGI', 'ENVI', 'HEAL', 'IMMU', 'MATE', 'MATH', 'MEDI', 'MULT',
               'NEUR', 'NURS', 'PHAR', 'PHYS', 'PSYC', 'SOCI', 'VETE'];
    let container = document.getElementById("supervisor_disc_filter");
    container.appendChild(document.createElement("br"));

    for (let i = 0; i < nb_sups; i++) {
        let select = document.createElement("select");
        select.name = `discipline${i + 1}`;
        select.className = "discipline_filter";

        // Add an empty option as default
        let defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Toutes";
        select.appendChild(defaultOption);

        // Populate the dropdown with discipline options
        disciplines.forEach(discipline => {
            let option = document.createElement("option");
            option.value = discipline;
            option.textContent = discipline;
            select.appendChild(option);
        });

        // Add an event listener to each dropdown
        select.addEventListener("change", async () => {
            // retrieve both filter dropdowns
            let filters = Array.from(container.getElementsByClassName("discipline_filter"));
            let selected_discs = filters.map(filter => filter.value).filter(disc => (disc !== "Any" && disc !== "")).join(",");
            console.log("Selected disciplines:", selected_discs);
            await filter_supervisors(selected_discs);
        });

        // Append dropdown to the container
        container.appendChild(select);
    }
});

let debounceTimeout;
async function searchWithQuery(query, resultsDiv) {
    let url = `/search?q=${query}&columns_search=name_student&columns_show=name_student,discipline_student_scopus,id_scopus_student,num_pubs_student`;
    console.log("📡 Envoi de la requête :", url);
    resultsDiv.innerHTML="";
    let loader = document.createElement("div");
    loader.className = "loader";
    loader.innerHTML = `
        <div></div>
        <div></div>
        <div></div>
    `;
    resultsDiv.appendChild(loader);
    try {
        let response = await fetch(url);
        if (!response.ok) {
            alert(`HTTP error! status: ${response.status}`);
        }
        let data = await response.json();
        console.log("📩 Réponse reçue :", data);
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
                        <strong>${row["name_student"]}</strong> 
                        <span style="color: gray;">(${row.discipline_student_scopus || "Discipline inconnue"})</span>
                    </p>
                `;
                entry.className = "resultatTheses";
                entry.id_scopus = row["id_scopus_student"];
                entry.nb_pubs = row["num_pubs_student"];
                entry.onclick = () => addPhD(row);
                resultsDiv.appendChild(entry);
            }
        });
    } catch (error) {
        resultsDiv.innerHTML = `<p style="color: red;">🚨 Erreur lors de la recherche.</p>`;
        console.error("Erreur :", error);
    }
    resultsDiv.removeChild(loader);
}
async function searchThese() {
    clearTimeout(debounceTimeout);

    debounceTimeout = setTimeout(async () => {
        let query = document.getElementById("search").value.trim();

        if (query.length === 0) return;

        let resultsDiv = document.getElementById("results");

        await searchWithQuery(query, resultsDiv);
    }, 1000);
}

function isAlreadySelected(phd) {
    const id = `${phd["id_scopus_student"]}`;
    return Array.from(selectedPhDs).some(selected => 
        `${selected["id_scopus_student"]}` === id
    );
}

function addPhD(phdStudent) {
    selectedPhDs.add(phdStudent);
    updateSelectedList();
    updateGraphWithAllPhDs().then(() => console.log("Graphique mis à jour"));
}

function removePhD(id) {
    // Trouve le PhD à supprimer basé sur son nom complet
    for (let phd of selectedPhDs) {
        if (`${phd["id_scopus_student"]}` === id) {
            selectedPhDs.delete(phd);
            break;
        }
    }
    updateSelectedList();
    updateGraphWithAllPhDs().then(() => console.log("Graphique mis à jour"));
}

function updateSelectedList() {
    const container = document.getElementById("selectedPhDs");
    container.innerHTML = "";

    selectedPhDs.forEach(phd => {
        const fullName = `${phd["name_student"]}`;
        const nb_publications = `${phd["num_pubs_student"]}`;
        const id = `${phd["id_scopus_student"]}`;
        const item = document.createElement("div");
        item.className = "selected-item";
        item.innerHTML = `
            <span>${fullName} (${nb_publications} publications)</span>
            <button class="remove-btn" data-name="${fullName}"><b>✕</b></button>
        `;

        // Ajoute l'écouteur d'événement au bouton
        const removeBtn = item.querySelector('.remove-btn');
        removeBtn.addEventListener('click', function() {
            removePhD(id);
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
    updateGraphWithAllPhDs().then(() => console.log("Graphique mis à jour"));
}

async function updateGraphWithAllPhDs() {
    if (selectedPhDs.size === 0) {
        document.getElementById("graph").innerHTML = "";
        return;
    }
    let phdParams = [];
    console.log(selectedPhDs)
    selectedPhDs.forEach(phd => {
        const phdId = `${phd["id_scopus_student"]}`;
        phdParams.push(phdId);
    });
    if (showSupervisors) {
        await updateGraph(1, phdParams.join(','),);
    }
    else {
        await updateGraph(0, phdParams.join(','));
    }
}

window.updateGraph = async function updateGraph(isShowSups, phdIds) {
    console.log("📡 Envoi de la requête AJAX pour le graphique...");
    try {
        let response = await fetch(`/update_graph?isShowSup=${isShowSups}&phd=${phdIds}`);
        let graphJSON = await response.json();
        console.log("📊 Graphique reçu, mise à jour...");
        const graphDiv = document.getElementById("graph");
        Plotly.newPlot(graphDiv, graphJSON.data, graphJSON.layout);
    } catch (error) {
        console.error("🚨 Erreur lors de la mise à jour du graphique :", error);
    }
};

document.getElementById("category").addEventListener("change", function() {
    // Reset optional inputs
    let supervisor = document.getElementsByClassName('supervisor_name_input');
    for (let i = 0; i < supervisor.length; i++) {
        supervisor[i].style.display = 'none';
    }
    let missingPublications = document.getElementsByClassName('publication_title');
    for (let i = 0; i < missingPublications.length; i++) {
        missingPublications[i].style.display = 'none';
    }
    let supervisor_input = document.getElementById('supervisor_name_input');
    supervisor_input.required = false;
    let missingPublicationsInput = document.getElementById('publication_title');
    missingPublicationsInput.required = false;
    let phd_name_input = document.getElementById('phd_name_input');
    phd_name_input.required = false;

    const chosen = this.value;
    if (chosen === "Other") {
        return;
    }
    document.getElementById("phd_name_input").required = true;
    if(chosen === 'Missing Publication(s)'){
        let missingPublications = document.getElementsByClassName('publication_title');
        for (let i = 0; i < missingPublications.length; i++) {
            missingPublications[i].style.display = 'block';
        }
        let missingPublicationsInput = document.getElementById('publication_title');
        missingPublicationsInput.required = true;
    }
    else if (chosen !== 'Name Typo') {
        let supervisor = document.getElementsByClassName('supervisor_name_input');
        for (let i = 0; i < supervisor.length; i++) {
            supervisor[i].style.display = 'block';
        }
        let supervisor_input = document.getElementById('supervisor_name_input');
        supervisor_input.required = true;
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const reportButton = document.getElementsByClassName('reportButton')[0];
    const reportModal = document.getElementById('reportModal');
    const closeButton = document.querySelector('.close');
    const reportForm = document.getElementById('reportForm');

    reportButton.addEventListener('click', function() {
        reportModal.style.display = 'flex';
    });

    closeButton.addEventListener('click', function() {
        reportModal.style.display = 'none';
    });

    window.addEventListener('click', function(event) {
        if (event.target === reportModal) {
            reportModal.style.display = 'none';
        }
    });

    reportForm.addEventListener('submit', function(event) {
        event.preventDefault();
    
        // Récupérer les valeurs du formulaire
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const category = document.getElementById("category").value;
        const issue = document.getElementById('issue').value.trim();
        const supervisor = document.getElementById('supervisor_name_input').value.trim();
        const publication = document.getElementById('publication_title').value.trim();
        const phd_name = document.getElementById('phd_name_input').value.trim();

        if (!name || !email || !category || !issue) {
            alert("Tous les champs sont obligatoires !");
            return;
        }

        const reportData = { name, email, category, issue, phd_name, supervisor, publication };

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

async function selectRandomPhDs() {
    let resultsDiv = document.getElementById("results");
    let availablePhDs = Array.from(resultsDiv.getElementsByClassName("resultatTheses"));

    if (availablePhDs.length === 0) {
        await searchWithQuery("", resultsDiv);
        return selectRandomPhDs();
    }

    let count = Math.min(10, availablePhDs.length);
    let selected = getRandomElements(availablePhDs, count);

    let phdsToAdd = [];

    selected.forEach(entry => {
        // Récupérer les données du thésard sans déclencher un clic
        let fullName = entry.querySelector("strong").innerText;
        let discipline = entry.querySelector("span").innerText.replace(/[()]/g, "");

        phdsToAdd.push({
            "name_student": fullName,
            "discipline_student_scopus": discipline,
            "id_scopus_student": entry.id_scopus,
            "num_pubs_student": entry.nb_pubs
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
            console.log("Thésard ajouté :", phd);
        }
    });

    updateSelectedList();
    
    if (shouldUpdateGraph === true) {
        updateGraphWithAllPhDs().then(() => console.log("Graphique mis à jour"));
    }
}

function deleteAll(){
    console.log("reset phd list")
    selectedPhDs.clear();
    updateSelectedList();
    updateGraphWithAllPhDs().then(() => console.log("Graphique mis à jour"));
}