/**
 * js/dashboard.js - Logique interactive du Dashboard Capynutri
 */

async function deleteEntry(entryId) {
    const result = await Swal.fire({
        title: 'Supprimer ce repas ?',
        text: "Cette action mettra a jour vos macros.",
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
            Swal.fire('Erreur', 'Impossible de supprimer cette entree.', 'error');
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Erreur', 'Probleme de connexion.', 'error');
    }
}

document.addEventListener("DOMContentLoaded", function() {
    const toggleElement = document.getElementById('activeDayToggle');
    const exerciseRows = document.querySelectorAll('.dashboard-ex-row');

    if (exerciseRows.length > 0 && toggleElement) {
        toggleElement.checked = true;
        toggleElement.disabled = true;
    }

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
            prevContainer.className = 'mt-2 p-2 bg-light border rounded small d-flex gap-3 justify-content-center text-muted fw-bold flex-wrap';
            recipeSelect.parentNode.appendChild(prevContainer);
        }

        if (!rid) {
            prevContainer.style.display = 'none';
            return;
        }

        try {
            const res = await fetch(`/api/recipe/${rid}/nutrition?servings=${sv}`);
            if (!res.ok) throw new Error("Erreur reseau");
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

    const rpeSlider = document.getElementById('rpeSlider');
    const rpeDisplay = document.getElementById('rpeValueDisplay');

    if (rpeSlider && rpeDisplay) {
        const rpeLabels = {
            1: "Tres facile (Marche lente)",
            2: "Facile (Marche normale)",
            3: "Leger (Echauffement)",
            4: "Modere- (Leger essoufflement)",
            5: "Modere (Transpiration)",
            6: "Soutenu (Parole difficile)",
            7: "Vigoureux (Inconfortable)",
            8: "Tres difficile (Muscu lourde)",
            9: "Intense (Sprint, HIIT)",
            10: "Extreme (Effort maximal)"
        };

        rpeSlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value, 10);
            rpeDisplay.innerText = `RPE ${val} : ${rpeLabels[val]}`;
            rpeDisplay.className = 'badge text-dark ' +
                (val <= 4 ? 'bg-success text-white' :
                (val <= 7 ? 'bg-warning' : 'bg-danger text-white'));
        });
    }

    if (toggleElement) {
        toggleElement.addEventListener('change', async (e) => {
            const isActive = e.target.checked;
            const dataWrapper = document.getElementById('dashboard-data');

            if (!dataWrapper) return;

            const consumed = parseFloat(dataWrapper.dataset.consumed || 0);
            const burned = parseFloat(dataWrapper.dataset.burned || 0);
            const dateStr = dataWrapper.dataset.date;
            const goalDisplay = document.getElementById('goal-text-display');
            const svgRing = document.getElementById('svg-ring-progress');

            const baseline = parseFloat(dataWrapper.dataset.restGoal || 0);
            const trainGoal = parseFloat(dataWrapper.dataset.trainGoal || 0);
            const sportBonus = isActive ? (trainGoal - baseline) : 0;
            const effectiveBonus = Math.max(sportBonus, burned);
            const currentBudget = baseline + effectiveBonus;

            if (goalDisplay) goalDisplay.innerText = Math.round(currentBudget);

            if (svgRing) {
                let pct = (consumed / currentBudget) * 100;
                if (pct > 100) pct = 100;
                const dashArray = (pct * 3.14159).toFixed(2);
                svgRing.style.transition = 'stroke-dasharray 0.6s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.3s';
                svgRing.setAttribute('stroke-dasharray', `${dashArray} 314.159`);
                svgRing.setAttribute('stroke', consumed > currentBudget ? '#e53935' : '#ff6b3d');
            }

            const remainingText = document.getElementById('remaining-text');
            if (remainingText) {
                const remaining = currentBudget - consumed;
                if (remaining > 0) {
                    remainingText.className = 'mt-3 fw-bold text-success';
                    remainingText.innerText = `${Math.round(remaining)} kcal restantes`;
                } else {
                    remainingText.className = 'mt-3 fw-bold text-danger';
                    remainingText.innerText = `Depassement de ${Math.round(remaining * -1)} kcal`;
                }
            }

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

                if (textEl) textEl.innerText = Math.round(newMacroGoal);

                if (barEl) {
                    let pct = (m.val / newMacroGoal) * 100;
                    if (pct > 100) pct = 100;
                    barEl.style.width = `${pct}%`;
                    barEl.style.backgroundColor = m.val > newMacroGoal ? '#e53935' : m.color;
                }
            });

            try {
                await fetch('/api/day/toggle_active', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ date: dateStr, is_active: isActive })
                });

                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 1000,
                    icon: 'success',
                    title: isActive ? 'Mode Sport !' : 'Mode Repos !'
                });
            } catch (err) {
                e.target.checked = !isActive;
                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'error',
                    title: 'Erreur reseau',
                    showConfirmButton: false,
                    timer: 2000
                });
            }
        });
    }
});
