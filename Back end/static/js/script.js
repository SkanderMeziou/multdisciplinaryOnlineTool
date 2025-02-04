let debounceTimeout; // Variable pour gérer le délai

async function searchThese() {
    clearTimeout(debounceTimeout); // Annule le dernier timeout si une nouvelle frappe arrive

    debounceTimeout = setTimeout(async () => {
        let query = document.getElementById("search").value.trim();
        let resultsDiv = document.getElementById("results");
        resultsDiv.innerHTML = "";

        if (query.length === 0) return;

        let url = `/search?dataset=theses&q=${query}&columns=auteur.nom,auteur.prenom,discipline`;
        console.log("📡 Envoi de la requête :", url);

        try {
            let response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
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
            resultsDiv.innerHTML = "";

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
