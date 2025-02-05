
let debounceTimeout; // Variable pour gérer le délai

async function searchThese() {
    clearTimeout(debounceTimeout); // Annule le dernier timeout si une nouvelle frappe arrive

    debounceTimeout = setTimeout(async () => {
        let query = document.getElementById("search").value.trim();
        let resultsDiv = document.getElementById("results");
        resultsDiv.innerHTML = "";

        if (query.length === 0) return;

        // Ajouter un loader avant d'envoyer la requête
        let loader = document.createElement("div");
        loader.className = "loader";
        loader.innerHTML = `
            <div></div>
            <div></div>
            <div></div>
        `;
        resultsDiv.appendChild(loader);

        let url = `/search?dataset=theses&q=${query}&columns=auteur.nom,auteur.prenom,discipline`;
        console.log("📡 Envoi de la requête :", url);

        try {
            let response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            let data = await response.json();
            console.log("📩 Réponse reçue :", data);

            resultsDiv.innerHTML = ""; // Supprimer le loader

            if (data.error) {
                resultsDiv.innerHTML = `<p style="color: red;">⚠️ ${data.error}</p>`;
                return;
            }

            if (data.length === 0) {
                resultsDiv.innerHTML = `<p>Aucun résultat trouvé.</p>`;
                return;
            }

            data.forEach(row => {
                let entry = document.createElement("div");
                entry.innerHTML = `
                    <p>
                        <strong>${row["auteur.prenom"]} ${row["auteur.nom"]}</strong> 
                        <span style="color: gray;">(${row.discipline || "Discipline inconnue"})</span>
                    </p>
                `;
                entry.className = "resultatTheses";
                resultsDiv.appendChild(entry);
            });
        } catch (error) {
            resultsDiv.innerHTML = `<p style="color: red;">🚨 Erreur lors de la recherche.</p>`;
            console.error("Erreur :", error);
        }
    }, 300); // Délai de 300 ms avant d'exécuter la requête
}


window.updateGraph = async function updateGraph() {
    console.log("📡 Envoi de la requête AJAX pour le graphique...");
    
    try {
        let response = await fetch("/update_graph");
        let graphJSON = await response.json();
        console.log("📊 Graphique reçu, mise à jour...");
        
        const graphDiv = document.getElementById("graph");
        
        // Utilisez directement graphJSON, qui contient déjà data et layout
        Plotly.newPlot(graphDiv, graphJSON.data, graphJSON.layout);
        
    } catch (error) {
        console.error("🚨 Erreur lors de la mise à jour du graphique :", error);
    }
};