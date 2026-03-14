let weeklyChart;
const canvasEl = document.getElementById('weeklyChart');

if (canvasEl) {
    const ctx = canvasEl.getContext('2d');
    weeklyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: CHART_DATA.labels, // 👈 Utilise l'objet du "pont"
            datasets: [{
                label: 'Calories consommées',
                data: CHART_DATA.kcal,   // 👈 Utilise l'objet du "pont"
                borderColor: '#FE8C68',
                backgroundColor: 'rgba(254, 140, 104, 0.15)',
                borderWidth: 3,
                tension: 0.4
            },
            {
                label: 'Objectif',
                data: Array(7).fill(CHART_DATA.goal), // 👈 Utilise l'objet du "pont"
                borderColor: '#e0e0e8',
                borderWidth: 2,
                borderDash: [5, 5],
                pointRadius: 0
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

// --- 2. FONCTIONS UTILITAIRES (Mise à jour UI) ---

// Met à jour un nombre dans le HTML (addition ou soustraction)
function updateText(elementId, addedValue) {
let el = document.getElementById(elementId);
if (el && addedValue !== undefined) {
    // 1. On récupère la valeur actuelle
    let current = parseFloat(el.innerText.replace(',', '.')) || 0;
    
    // 2. LE CALCUL PRÉCIS : 
    // On additionne, puis on utilise toPrecision(12) pour supprimer le bruit binaire 
    // sans perdre la moindre miette de nutriment.
    let rawValue = current + parseFloat(addedValue);
    let cleanValue = parseFloat(rawValue.toPrecision(12));

    // 3. SÉCURITÉ : On garde Math.max(0) juste pour éviter les bugs de DB
    // (On ne peut pas consommer des calories négatives)
    cleanValue = Math.max(0, cleanValue);

    // 4. AFFICHAGE
    if (elementId.includes('kcal')) {
        el.innerText = Math.round(cleanValue);
    } else {
        // .toFixed(1) pour l'affichage, mais parseFloat enlève les .0 inutiles
        // Ainsi : 0.000000000001 devient 0, mais 0.1 reste 0.1
        el.innerText = parseFloat(cleanValue.toFixed(1));
    }
}
}

// Met à jour une barre de progression
function updateBar(barId, textId, goalId) {
let barEl = document.getElementById(barId);
let textEl = document.getElementById(textId);
let goalEl = document.getElementById(goalId);
if (barEl && textEl && goalEl) {
    let current = parseFloat(textEl.innerText) || 0;
    let goal = parseFloat(goalEl.innerText) || 1;
    let percent = Math.min((current / goal) * 100, 100);
    barEl.style.width = percent + "%";
}
}

// Anime le cercle des calories
function animateKcalRing() {
let ringEl = document.getElementById('kcal-ring-fill');
let currentKcalEl = document.getElementById('total-kcal');
let goalKcalEl = document.getElementById('goal-kcal');
if (!ringEl || !currentKcalEl || !goalKcalEl) return;

let currentKcal = parseFloat(currentKcalEl.innerText) || 0;
let goalKcal = parseFloat(goalKcalEl.innerText.replace(/[^0-9.]/g, '')) || 2000;
let newPct = Math.min((currentKcal / goalKcal) * 100, 100);
ringEl.setAttribute('stroke-dasharray', `${newPct * 3.14159} 314.159`);

if (currentKcal > goalKcal) ringEl.classList.add('ring-over');
else ringEl.classList.remove('ring-over');
}

// FONCTION MAÎTRESSE : Met à jour tout le dashboard d'un coup
function updateDashboardUI(data, isAddition = true) {
const factor = isAddition ? 1 : -1;

// 1. MISE À JOUR AUTOMATIQUE DE TOUS LES NUTRIMENTS
// On boucle sur toutes les clés reçues (kcal, protein_g, fiber_g, vit_c_mg...)
Object.keys(data).forEach(key => {
    if (key.endsWith('_g') || key.endsWith('_mg') || key.endsWith('_mcg') || key === 'kcal') {
        // Mise à jour du texte
        updateText('total-' + key, data[key] * factor);
        // Mise à jour de la barre (si elle existe, macro ou micro)
        updateBar('bar-' + key, 'total-' + key, 'goal-' + key);
    }
});

// 2. MISE À JOUR SPÉCIFIQUE DU CERCLE ET DU GRAPH
animateKcalRing();
if (weeklyChart) {
    let idx = weeklyChart.data.datasets[0].data.length - 1;
    let val = weeklyChart.data.datasets[0].data[idx] || 0;
    weeklyChart.data.datasets[0].data[idx] = Math.max(0, val + (data.kcal * factor));
    weeklyChart.update();
}

// 3. MISE À JOUR DES CALORIES RESTANTES
updateRemainingKcalUI();
}

function updateRemainingKcalUI() {
const currentKcal = parseFloat(document.getElementById('total-kcal').innerText) || 0;
const goalKcal = parseFloat(document.getElementById('goal-kcal').innerText.replace(/[^0-9.]/g, '')) || 2000;

// On récupère les kcal brûlées depuis l'interface (si le badge existe)
const burnEl = document.querySelector('.burn-badge');
const burned = burnEl ? parseFloat(burnEl.innerText.replace(/[^0-9.]/g, '')) : 0;

const remaining = goalKcal - currentKcal + burned;
const displayEl = document.getElementById('remaining-val');

if (displayEl) {
    if (remaining > 0) {
        displayEl.style.color = "#4caf50";
        displayEl.innerText = Math.round(remaining) + " kcal restantes";
    } else {
        displayEl.style.color = "#e53935";
        displayEl.innerText = Math.round(Math.abs(remaining)) + " kcal de trop";
    }
}
}

// --- 3. ACTIONS UTILISATEUR (Ajout & Suppression) ---

// AJOUTER
const addFoodForm = document.getElementById('addFoodForm');
if (addFoodForm) {
addFoodForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    try {
    const response = await fetch(this.action, { method: 'POST', body: formData });
    const result = await response.json();
    if (result.ok) {
        this.reset();
        document.getElementById('addFoodPanel').classList.remove('show');
        
        // Créer la ligne dans le journal (simplifié pour le clean code)
        const newRow = document.createElement('div');
        newRow.className = 'log-entry';
        newRow.id = `log-row-${result.entry_id}`;
        newRow.innerHTML = `
        <div class="log-entry-name">${result.label} ${result.servings != 1 ? '×'+result.servings : ''}</div>
        <div class="d-flex align-items-center gap-2">
            <div class="log-entry-kcal">${Math.round(result.kcal)} kcal</div>
            <button class="btn btn-sm text-danger p-0 border-0" onclick="deleteEntry(${result.entry_id})"><i class="bi bi-x-circle-fill"></i></button>
        </div>`;
        document.getElementById('addFoodPanel').after(newRow);
        const emptyLog = document.querySelector('.empty-log');
        if (emptyLog) emptyLog.remove();

        updateDashboardUI(result, true); // MAGIE : Mise à jour globale
    }
    } catch (e) { console.error(e); }
});
}

// SUPPRIMER
async function deleteEntry(entryId) {
const confirm = await Swal.fire({
    title: 'Supprimer ?',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#FE8C68'
});
if (!confirm.isConfirmed) return;

try {
    const response = await fetch(`/api/log/delete/${entryId}`, { method: 'POST' });
    const result = await response.json();
    if (result.ok) {
    document.getElementById(`log-row-${entryId}`)?.remove();
    updateDashboardUI(result, false); // MAGIE : Soustraction globale
    if (document.querySelectorAll('.log-entry').length === 0) {
        const logPanel = document.querySelector('.col-lg-7 .panel'); // Le conteneur du journal
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'empty-log';
        emptyMsg.innerHTML = '<i class="bi bi-egg-fried"></i><p>Rien de loggé pour cette journée.</p>';
        logPanel.appendChild(emptyMsg);
    }
    Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Supprimé', showConfirmButton: false, timer: 1500 });
    }
} catch (e) { console.error(e); }
}

// --- 4. LOGIQUE DES ONGLETS & PREVIEWS ---
document.querySelectorAll('.add-tab').forEach(tab => {
tab.addEventListener('click', () => {
    document.querySelectorAll('.add-tab, .add-tab-content').forEach(el => el.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab === 'recipe' ? 'tabRecipe' : 'tabManual').classList.add('active');
});
});

const recipeSelect = document.getElementById('recipeSelect');
recipeSelect?.addEventListener('change', loadRecipeNutr);
document.querySelector('[name="servings"]')?.addEventListener('input', loadRecipeNutr);

async function loadRecipeNutr() {
const rid = recipeSelect.value;
const sv = parseFloat(document.querySelector('[name="servings"]').value) || 1;
if (!rid) return;
const res = await fetch(`/api/recipe/${rid}/nutrition?servings=${sv}`);
const d = await res.json();
const prev = document.getElementById('recipeNutrPreview');
prev.style.display = 'flex';
prev.innerHTML = `<span>${Math.round(d.kcal)} kcal</span> <span>P: ${d.protein.toFixed(1)}g</span>`;
}
