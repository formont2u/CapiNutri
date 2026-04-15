# CapyNutri

CapyNutri is a Flask-based personal nutrition and meal-planning app.

The project is now local-first:
- no remote infrastructure required
- no account or login flow
- one local dataset per device
- designed to run on a PC and be reachable from a phone on the same network

It combines:
- recipe management
- ingredient nutrition lookup
- daily food and exercise tracking
- weekly meal planning
- pantry and shopping list workflows
- supermarket pricing
- smart ingredient units such as `1 tomate = 90 g` or `1 pavé = 140 g`

## Current Scope

Main user flows already available:
- create, edit, duplicate, and view recipes
- search ingredient nutrition from USDA and Open Food Facts
- save ingredients to a local library
- define smart per-ingredient units in the library or directly from the recipe form
- track meals, exercise, weight, and body-fat trends
- plan meals across the week
- generate a shopping list from the weekly plan
- compare ingredient prices by shop
- tag recipes for planner-friendly filtering and suggestions

## Tech Stack

- Python
- Flask
- SQLite
- Bootstrap
- Vanilla JavaScript

## Project Structure

- [app.py](/D:/Capynutri/app.py): Flask app entrypoint
- [android-app](/D:/Capynutri/android-app): native Android prototype with Kotlin, Compose, Room, and SQLite
- [routes](/D:/Capynutri/routes): route handlers / controllers
- [services](/D:/Capynutri/services): business logic
- [crud.py](/D:/Capynutri/crud.py): SQLite data-access layer
- [db.py](/D:/Capynutri/db.py): schema and migrations
- [pricing_db.py](/D:/Capynutri/pricing_db.py): pricing database
- [templates](/D:/Capynutri/templates): Jinja templates
- [static](/D:/Capynutri/static): CSS, JS, images, fonts

## Run Locally

From `D:\Capynutri`:

```powershell
py -3 -m pip install -r requirements.txt
py -3 app.py
```

Then open [http://localhost:5000](http://localhost:5000).

The app opens directly in local mode. To test from a phone on the same Wi-Fi:
- run the app on your PC
- find your PC local IP with `ipconfig`
- open `http://YOUR_PC_IP:5000` on the phone

## Android Prototype

A first native Android prototype now lives in [android-app](/D:/Capynutri/android-app).

Current Android prototype scope:
- Room database stored locally on the device
- Kotlin + Jetpack Compose foundation
- recipe catalogue screen
- planning screen
- pantry screen
- demo seed data

Open [android-app](/D:/Capynutri/android-app) in Android Studio to sync and run it.

## Notes

- The app can read a local `usda_key.txt` file for USDA API usage.
- The checked-in `venv` is likely machine-specific and should not be treated as the source of truth.
- `recipes.db` and `pricing.db` are local SQLite files used by the app.

## Current Product Status

CapyNutri is not aiming at public production right now.

The strongest areas today are:
- recipe flow
- nutrition library flow
- smart ingredient units
- tags and planner suggestions

The main next step is tightening coherence between:
- pantry
- shopping list
- pricing
- unit conversions

For the current implementation plan, see [road_map.md](/D:/Capynutri/road_map.md).
