package com.capynutri.app

import android.app.Application
import com.capynutri.app.data.local.CapyDatabase
import com.capynutri.app.data.repository.CapyRepository

class CapyNutriApplication : Application() {
    val database: CapyDatabase by lazy { CapyDatabase.create(this) }
    val repository: CapyRepository by lazy { CapyRepository(database) }
}
