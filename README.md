# CapyNutri

CapyNutri is a Flask-based personal nutrition and meal-planning app.

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
- Flask-Login
- SQLite
- Bootstrap
- Vanilla JavaScript

## Project Structure

- [app.py](/D:/Capynutri/app.py): Flask app entrypoint
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

## Deploy To Render

CapyNutri now includes a basic Render config in [render.yaml](/D:/Capynutri/render.yaml).

Recommended setup on Render:
- create a new Web Service from the GitHub repo
- let Render detect `render.yaml`
- keep the generated `FLASK_SECRET_KEY`
- add `USDA_API_KEY` as an environment variable if you want USDA search in production

Start command used by Render:

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

Important limitation for now:
- the app still uses local SQLite files
- this is acceptable for short testing
- it is not a durable production database strategy on Render
- for a more reliable hosted version, the next step will be moving app data to Postgres

## Notes

- The app expects a local `usda_key.txt` file for USDA API usage.
- The checked-in `venv` is likely machine-specific and should not be treated as the source of truth.
- `recipes.db` and `pricing.db` are local SQLite files used by the app.

## Current Product Status

CapyNutri is not at public production stage yet.

The strongest areas today are:
- recipe flow
- nutrition library flow
- smart ingredient units
- tags and planner suggestions

The main next step before a private beta is tightening coherence between:
- pantry
- shopping list
- pricing
- unit conversions

For the current implementation plan, see [road_map.md](/D:/Capynutri/road_map.md).
