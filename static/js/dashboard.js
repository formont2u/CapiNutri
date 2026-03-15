/**
 * js/dashboard.js — Logique interactive du Dashboard Capynutri
 */

document.addEventListener("DOMContentLoaded", function() {

    // ── 1. INITIALISATION DU GRAPHIQUE (Chart.js) ──
    const canvasEl = document.getElementById('weeklyChart');
    if (canvasEl && typeof CHART_DATA !== 'undefined') {
        const ctx = canvasEl.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: CHART_DATA.labels,
                datasets: [{
                    label: 'Calories consommées',
                    data: CHART_DATA.kcal,
                    borderColor: '#ff6b3d', // Couleur de ta marque
                    backgroundColor: 'rgba(255, 107, 61, 0.15)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Objectif',
                    data: Array(7).fill(CHART_DATA.goal),
                    borderColor: '#95a5a6',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // ── 2. PREVIEW NUTRITIONNEL EN DIRECT (Ajout Recette) ──
    const recipeSelect = document.getElementById('recipeSelect');
    const servingsInput = document.querySelector('input[name="servings"]');
    
    // On écoute les changements sur la liste déroulante et le champ portion
    if (recipeSelect && servingsInput) {
        recipeSelect.addEventListener('change', loadRecipeNutr);
        servingsInput.addEventListener('input', loadRecipeNutr);
    }

    async function loadRecipeNutr() {
        const rid = recipeSelect.value;
        const sv = parseFloat(servingsInput.value) || 1;
        
        // S'il n'y a pas de panneau de preview dans le nouveau HTML, on le crée
        let prevContainer = document.getElementById('recipeNutrPreview');
        if (!prevContainer) {
            prevContainer = document.createElement('div');
            prevContainer.id = 'recipeNutrPreview';
            prevContainer.className = 'mt-2 p-2 bg-light border rounded small d-flex gap-3 justify-content-center text-muted fw-bold';
            recipeSelect.parentNode.appendChild(prevContainer);
        }

        if (!rid) {
            prevContainer.style.display = 'none';
            return;
        }

        try {
            const res = await fetch(`/api/recipe/${rid}/nutrition?servings=${sv}`);
            if (!res.ok) throw new Error("Erreur réseau");
            const d = await res.json();
            
            prevContainer.style.display = 'flex';
            prevContainer.innerHTML = `
                <span class="text-accent"><i class="bi bi-fire"></i> ${Math.round(d.kcal)} kcal</span>
                <span>P: ${d.protein.toFixed(1)}g</span>
                <span>G: ${d.carbs.toFixed(1)}g</span>
                <span>L: ${d.fat.toFixed(1)}g</span>
            `;
        } catch (e) {
            console.error("Impossible de charger la preview :", e);
            prevContainer.style.display = 'none';
        }
    }
});

// ── 3. SUPPRESSION D'UNE ENTRÉE DU JOURNAL (AJAX + SweetAlert) ──
// Cette fonction doit rester dans le scope global car elle est appelée par le HTML (onclick="deleteEntry(id)")
async function deleteEntry(entryId) {
    const result = await Swal.fire({
        title: 'Supprimer ce repas ?',
        text: "Cette action mettra à jour vos macros.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#e53935',
        cancelButtonColor: '#95a5a6',
        confirmButtonText: 'Oui, supprimer',
        cancelButtonText: 'Annuler'
    });

    if (!result.isConfirmed) return;

    try {
        const response = await fetch(`/api/log/delete/${entryId}`, { method: 'POST' });
        const data = await response.json();
        
        if (data.ok) {
            // UX : On recharge la page pour que le serveur recalcule toutes les barres de nutriments 
            // et garantisse 100% de précision sans désynchronisation.
            window.location.reload();
        } else {
            Swal.fire('Erreur', 'Impossible de supprimer cette entrée.', 'error');
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Erreur', 'Problème de connexion.', 'error');
    }
}