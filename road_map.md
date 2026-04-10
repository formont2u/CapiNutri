# CapyNutri Roadmap

## Done

### Foundations
- [x] Flask app structure with routes, services, templates, and SQLite storage
- [x] Authentication and protected app flow
- [x] Recipe CRUD with nutrition-aware ingredients
- [x] Daily dashboard, food log, exercise log, and weekly stats
- [x] Weekly meal planning, pantry, shopping list, and pricing database
- [x] Ingredient library with USDA / Open Food Facts integration

### Product Improvements
- [x] Codebase cleanup and dead-code removal
- [x] Shared helpers for dates and repeated form parsing
- [x] Smart ingredient unit system backed by `ingredient_units`
- [x] Library-linked recipe ingredients via `library_id`
- [x] Custom unit-aware pricing conversion
- [x] Inline smart-unit creation from the recipe form
- [x] Tag-first recipe classification UX
- [x] Automatic cleanup of unused custom tags
- [x] Tag management screen with usage count, rename, and delete
- [x] Smarter planner suggestions using:
  - meal-slot tags
  - pantry coverage
  - recent-plan repetition penalty
- [x] UX polish for ingredient search dropdown and smart-unit actions

## In Progress

### Beta Readiness
- [ ] Tighten pantry / shopping / pricing coherence around smart conversions
- [ ] Improve recipe-to-library matching to reduce duplicates and fuzzy ingredient states
- [ ] Make planner suggestions visible and explainable directly in the UI cards
- [ ] Add more default smart-unit shortcuts and conversion seeds
- [ ] Pass tab by tab through the product to identify friction, weak spots, and missing actions
- [ ] Rethink current features to decide what should be simplified, extended, or connected better
- [ ] Improve feature interactivity so recipes, planner, pantry, shopping, pricing, tags, and tracking work more as one system
- [ ] Start a full UI refresh / polish pass across recipe form, planner, shopping, pantry, library, and dashboard

## Next

### Must Have Before Private Beta
- [ ] Complete a structured UI / UX improvement pass
  - clearer actions
  - better hierarchy
  - more consistent components
  - better empty states and feedback
- [ ] Better pantry matching across compatible units, not only exact same-unit comparisons
- [ ] Better shopping-list grouping and clearer "already in stock" logic
- [ ] Safer duplicate handling in ingredient library and recipe linking
- [ ] A small pack of default household conversions:
  - tomato
  - onion
  - egg
  - garlic clove
  - zucchini
  - salmon fillet
  - apple
  - banana
- [ ] End-to-end feature-coherence pass for tags, smart units, planner feedback, library flow, and tracking flow
- [ ] Build a real mobile-first / responsive pass
  - recipe form
  - planner
  - shopping list
  - pantry
  - dashboard

### Nice To Have
- [ ] Recipe notes / private chef notes
- [ ] Recipe rating or "works well / to improve" feedback loop
- [ ] Macro-aware recipe suggestions based on remaining daily goals
- [ ] Extend interactions between features
  - planner suggestions influenced by pantry + goals + prices
  - shopping list influenced by pantry confidence and pricing intelligence
  - recipe suggestions influenced by body goals, active/rest day, and saved habits
- [ ] Revisit each tab again after beta feedback to expand the most valuable workflows

## Later

### Production-Oriented Work
- [ ] Set up production configuration
  - environment variables and secrets handling
  - safer Flask config
  - production server setup
  - database and file-path configuration
- [ ] Automated tests
- [ ] Backup / migration strategy for SQLite data
- [ ] Deployment config and environment hardening
- [ ] Error monitoring and logs
- [ ] Security review and secret handling cleanup

## Recommended Order

1. Product review tab by tab
   - identify weak UX
   - identify missing links between features
   - decide what to simplify vs extend
2. Core feature coherence
   - pantry / shopping / pricing / smart-unit consistency
   - recipe / library linking cleanup
   - planner feedback and reliability
3. UI refresh
   - desktop polish
   - clearer interactions
   - better states and navigation
4. Mobile pass
   - make the key workflows really usable on phone
5. Private beta
   - validate real-world usage
   - collect friction and feature feedback
6. Production setup
   - only once the product flow feels stable enough
