/**
 * js/dashboard.js — Logique interactive du Dashboard Capynutri
 */

// Au chargement, si on a des exercices, on s'assure que le toggle visuel est cohérent
const exerciseExists = document.querySelectorAll('.list-group-item').length > 0;
if (exerciseExists && toggleElement) {
    toggleElement.checked = true;
    toggleElement.disabled = true;
}

// ── 1. FONCTIONS GLOBALES (Appelées depuis le HTML) ──

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
            window.location.reload();
        } else {
            Swal.fire('Erreur', 'Impossible de supprimer cette entrée.', 'error');
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Erreur', 'Problème de connexion.', 'error');
    }
}


document.addEventListener("DOMContentLoaded", function() {

    // --- PREVIEW NUTRITIONNEL EN DIRECT (Ajout Recette) ---
    const recipeSelect = document.getElementById('recipeSelect');
    const servingsInput = document.querySelector('input[name="servings"]');
    
    if (recipeSelect && servingsInput) {
        recipeSelect.addEventListener('change', loadRecipeNutr);
        servingsInput.addEventListener('input', loadRecipeNutr);
    }

    async function loadRecipeNutr() {
        const rid = recipeSelect.value;
        const sv = parseFloat(servingsInput.value) || 1;
        
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


    // --- NOUVEAU : SLIDER RPE (Exercice) INDÉPENDANT ---
    const rpeSlider = document.getElementById('rpeSlider');
    const rpeDisplay = document.getElementById('rpeValueDisplay');
    
    if (rpeSlider && rpeDisplay) {
        const rpeLabels = {
            1: "Très facile (Marche lente)",
            2: "Facile (Marche normale)",
            3: "Léger (Échauffement)",
            4: "Modéré- (Léger essoufflement)",
            5: "Modéré (Transpiration)",
            6: "Soutenu (Parole difficile)",
            7: "Vigoureux (Inconfortable)",
            8: "Très difficile (Muscu lourde)",
            9: "Intense (Sprint, HIIT)",
            10: "Extrême (Effort maximal)"
        };

        rpeSlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            rpeDisplay.innerText = `RPE ${val} : ${rpeLabels[val]}`;
            
            // Changement de couleur selon l'intensité
            rpeDisplay.className = 'badge text-dark ' + 
                (val <= 4 ? 'bg-success text-white' : 
                (val <= 7 ? 'bg-warning' : 'bg-danger text-white'));
        });
    }


    // --- TOGGLE CARB CYCLING DASHBOARD (ANIMATION FLUIDE) ---
    const toggleElement = document.getElementById('activeDayToggle');
    if (toggleElement) {
        toggleElement.addEventListener('change', async (e) => {
            const isActive = e.target.checked;
            const dataWrapper = document.getElementById('dashboard-data');
            
            if (dataWrapper) {
                // Lecture instantanée des données HTML
                const consumed = parseFloat(dataWrapper.dataset.consumed || 0);
                const burned = parseFloat(dataWrapper.dataset.burned || 0);
                const newGoal = parseFloat(isActive ? dataWrapper.dataset.trainGoal : dataWrapper.dataset.restGoal);
                const dateStr = dataWrapper.dataset.date;

                // 1. MAJ DU TEXTE CENTRAL (Objectif Calories)
                const goalDisplay = document.getElementById('goal-text-display');
                if (goalDisplay) goalDisplay.innerText = Math.round(newGoal);

                // 2. MAJ DU CERCLE SVG (Animation instantanée)
                const svgRing = document.getElementById('svg-ring-progress');
                if (svgRing) {
                    let pct = (consumed / newGoal) * 100;
                    if (pct > 100) pct = 100;
                    
                    const dashArray = (pct * 3.14159).toFixed(2);
                    svgRing.style.transition = 'stroke-dasharray 0.6s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.3s';
                    svgRing.setAttribute('stroke-dasharray', `${dashArray} 314.159`);
                    svgRing.setAttribute('stroke', consumed > newGoal ? '#e53935' : '#ff6b3d');
                }

                // 3. MAJ DU TEXTE RESTANT
                // --- LOGIQUE ANTI-DOUBLE DIPPING ---
                const baseline = parseFloat(dataWrapper.dataset.restGoal);
                const sportBonus = isActive ? (parseFloat(dataWrapper.dataset.trainGoal) - baseline) : 0;
                
                // Le budget total est la baseline + le plus grand entre le bonus Sport et le réel brûlé
                const effectiveBonus = Math.max(sportBonus, burned);
                const currentBudget = baseline + effectiveBonus;

                // MAJ de l'objectif affiché au centre du cercle
                if (goalDisplay) goalDisplay.innerText = Math.round(currentBudget);

                // MAJ du cercle SVG
                if (svgRing) {
                    let pct = (consumed / currentBudget) * 100;
                    if (pct > 100) pct = 100;
                    const dashArray = (pct * 3.14159).toFixed(2);
                    svgRing.setAttribute('stroke-dasharray', `${dashArray} 314.159`);
                    svgRing.setAttribute('stroke', consumed > currentBudget ? '#e53935' : '#ff6b3d');
                }

                // MAJ du texte restant
                const remainingText = document.getElementById('remaining-text');
                if (remainingText) {
                    const remaining = currentBudget - consumed;
                    if (remaining > 0) {
                        remainingText.className = 'mt-3 fw-bold text-success';
                        remainingText.innerText = `${Math.round(remaining)} kcal restantes`;
                    } else {
                        remainingText.className = 'mt-3 fw-bold text-danger';
                        remainingText.innerText = `Dépassement de ${Math.round(remaining * -1)} kcal`;
                    }
                }
                // --- ANIMATION DES 3 MACRONUTRIMENTS ET DES FIBRES ---
                const macrosList = [
                    { field: 'protein_g', val: parseFloat(dataWrapper.dataset.valP), rest: parseFloat(dataWrapper.dataset.restP), train: parseFloat(dataWrapper.dataset.trainP), color: '#4a90e2' },
                    { field: 'carbs_g', val: parseFloat(dataWrapper.dataset.valC), rest: parseFloat(dataWrapper.dataset.restC), train: parseFloat(dataWrapper.dataset.trainC), color: '#f5a623' },
                    { field: 'fat_g', val: parseFloat(dataWrapper.dataset.valF), rest: parseFloat(dataWrapper.dataset.restF), train: parseFloat(dataWrapper.dataset.trainF), color: '#e8571a' },
                    { field: 'fiber_g', val: parseFloat(dataWrapper.dataset.valFiber), rest: parseFloat(dataWrapper.dataset.restFiber), train: parseFloat(dataWrapper.dataset.trainFiber), color: '#95a5a6' }
                ];

                macrosList.forEach(m => {
                    const newMacroGoal = isActive ? m.train : m.rest;
                    const textEl = document.getElementById(`text-goal-${m.field}`);
                    const barEl = document.getElementById(`bar-${m.field}`);

                    // 1. Maj du texte
                    if (textEl) textEl.innerText = Math.round(newMacroGoal);

                    // 2. Maj de la barre
                    if (barEl) {
                        let pct = (m.val / newMacroGoal) * 100;
                        if (pct > 100) pct = 100;
                        barEl.style.width = `${pct}%`;
                        
                        // Si dépassement, la barre devient rouge
                        barEl.style.backgroundColor = m.val > newMacroGoal ? '#e53935' : m.color;
                    }
                });

                // 4. SAUVEGARDE SILENCIEUSE
                try {
                    await fetch('/api/day/toggle_active', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ date: dateStr, is_active: isActive })
                    });
                    
                    Swal.fire({
                        toast: true, position: 'top-end', showConfirmButton: false, timer: 1000,
                        icon: 'success', title: isActive ? 'Mode Sport ! ⚡' : 'Mode Repos ! 🛋️'
                    });
                } catch(err) {
                    // Rollback UI en cas d'erreur
                    e.target.checked = !isActive;
                    Swal.fire({ toast: true, position: 'top-end', icon: 'error', title: 'Erreur réseau', showConfirmButton: false, timer: 2000 });
                }
            }
        });
    }

});