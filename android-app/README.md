# CapyNutri Android Prototype

This folder contains the first native Android prototype for CapyNutri.

Current stack:
- Kotlin
- Jetpack Compose
- Room
- SQLite local on device

Current prototype scope:
- local-first embedded database
- recipe catalogue screen
- daily planning screen
- pantry screen
- demo seed data for quick bootstrapping

## Open In Android Studio

1. Open the `android-app` folder in Android Studio.
2. Let Android Studio sync the Gradle project.
3. Run the `app` configuration on an emulator or Android phone.

## Notes

- The database file is `capynutri-local.db`.
- This prototype is intentionally local-only.
- It is a foundation for the future Android rewrite, not yet a full parity port of the Flask app.
