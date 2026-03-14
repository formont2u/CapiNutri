import sqlite3

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# On cherche TOUTES les soupes, peu importe la table
print("--- VÉRIFICATION DANS LE JOURNAL (food_log) ---")
cursor.execute("SELECT id, label, log_date, kcal FROM food_log WHERE label LIKE '%Pea%'")
print(cursor.fetchall())

print("\n--- VÉRIFICATION DANS LE PLANNING (meal_plan) ---")
# Ici on vérifie si par hasard ça a atterri là
cursor.execute("SELECT id, label, plan_date FROM meal_plan WHERE label LIKE '%Pea%'")
print(cursor.fetchall())

conn.close()