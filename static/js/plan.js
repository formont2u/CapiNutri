// static/js/plan.js

// --- Helpers de Toast ---
function notify(msg, type='info') {
    Swal.fire({
        toast: true,
        position: 'top-end',
        icon: type,
        title: msg,
        showConfirmButton: false,
        timer: 3000
    });
}

function formatSuggestionReason(recipe) {
    const parts = [];
    if (recipe.reason) parts.push(recipe.reason);
    if (typeof recipe.pantry_ratio === 'number' && recipe.pantry_ratio > 0) {
        parts.push(`stock ${(recipe.pantry_ratio * 100).toFixed(0)}%`);
    }
    if (recipe.tags?.length) {
        parts.push(recipe.tags.slice(0, 2).join(', '));
    }
    return parts.join(' · ');
}

// --- Suggestion ---
document.querySelectorAll('.btn-suggest').forEach(btn => {
    btn.addEventListener('click', async () => {
        const slot = btn.dataset.slot;
        const originalContent = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        
        try {
            const r = await fetch(`/api/plan/suggest?meal_type=${slot}&date=${window.PLAN_DATE}`);
            if (r.status === 404) {
                notify('Aucune recette disponible !', 'warning');
                btn.innerHTML = originalContent;
                btn.disabled = false;
                return;
            }
            const recipe = await r.json();
            const reason = formatSuggestionReason(recipe);
            notify(reason ? `${recipe.name} · ${reason}` : `${recipe.name} sélectionnée`, 'success');
            await setPlan(slot, recipe.id);
            setTimeout(() => location.reload(), 450);
        } catch(e) {
            notify('Erreur réseau', 'error');
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    });
});

// --- Choix manuel ---
document.querySelectorAll('.plan-recipe-picker').forEach(sel => {
    sel.addEventListener('change', async () => {
        const id = sel.value;
        if (!id) return;
        sel.disabled = true;
        await setPlan(sel.dataset.slot, parseInt(id));
        location.reload();
    });
});

// --- Consommer (Log) ---
document.querySelectorAll('.btn-log-meal').forEach(btn => {
    btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        try {
            const r = await fetch('/api/plan/log', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    plan_id:   parseInt(btn.dataset.planId),
                    recipe_id: parseInt(btn.dataset.recipeId),
                    meal_type: btn.dataset.mealType,
                    date:      btn.dataset.date,
                })
            });
            const res = await r.json();
            if (res.ok) {
                notify('Repas journalisé !', 'success');
                setTimeout(() => location.reload(), 800);
            }
        } catch(e) { 
            notify('Erreur', 'error'); 
            btn.disabled = false; 
        }
    });
});

// --- Retirer ---
document.querySelectorAll('.btn-clear-slot').forEach(btn => {
    btn.addEventListener('click', async () => {
        btn.disabled = true;
        const r = await fetch('/api/plan/clear', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({plan_id: parseInt(btn.dataset.planId)})
        });
        if ((await r.json()).ok) location.reload();
    });
});

async function setPlan(slot, recipeId) {
    await fetch('/api/plan/set', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({date: window.PLAN_DATE, meal_type: slot, recipe_id: recipeId})
    });
}

// --- TOGGLE JOUR ACTIF / REPOS ---
document.getElementById('activeDayToggle')?.addEventListener('change', async (e) => {
    const isActive = e.target.checked;
    const label = document.getElementById('activeDayLabel');
    
    // Mise à jour visuelle instantanée
    label.innerHTML = isActive 
        ? '<i class="bi bi-lightning-charge-fill text-warning"></i> Actif' 
        : '<i class="bi bi-cup-hot-fill text-muted"></i> Repos';

    try {
        const r = await fetch('/api/day/toggle_active', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ date: window.PLAN_DATE, is_active: isActive })
        });
        
        if ((await r.json()).ok) {
            notify(isActive ? 'Mode Entraînement activé ⚡' : 'Mode Repos activé 🛋️', 'success');
        }
    } catch(err) {
        e.target.checked = !isActive;
        notify('Erreur lors de la sauvegarde', 'error');
    }
});
