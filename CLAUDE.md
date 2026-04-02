# CateringOS — Django Backend

## Stack
- Python 3.12 · Django 5.0.3 · Django REST Framework 3.15.1
- PostgreSQL 16 · JWT via djangorestframework-simplejwt
- WeasyPrint (PDF) · openpyxl (Excel) · django-filter

## Project Structure
- config/ → Django project package (settings/, urls.py, wsgi.py)
- apps/ → All Django apps (authentication, inquiries, events, menu, master, engine, grocery, quotations, reports)
- shared/ → Cross-app utilities (mixins.py, pagination.py, permissions.py, exports/)

## Rules
- ALL models must inherit from shared.mixins.BaseMixin (UUID PK + timestamps + soft delete)
- NEVER hard delete — always use soft_delete()
- ALL APIs use DRF ViewSets + Serializers (no raw responses)
- Business logic lives in services.py — views are thin
- JWT auth on every endpoint (except auth/register and auth/login)
- Use decimal.Decimal for all quantity calculations (never float)

## Auth
- Custom User model at apps.authentication.User
- AUTH_USER_MODEL = 'authentication.User' (set before first migration)
- Login uses email not username

## Apps & Responsibilities
- authentication: Custom User model, JWT login/register/logout
- inquiries: Lead capture, convert to event
- events: Event lifecycle + state machine
- master: Dish + Ingredient + DishRecipe master data
- menu: EventMenuItem with recipe snapshot freeze
- engine: CalculationEngine (reads snapshots, writes EventIngredient)
- grocery: Reads EventIngredient, exports PDF/Excel
- quotations: Auto-generate quotes, PDF export
- reports: Read-only dashboard selectors

## Critical Rules
- Set AUTH_USER_MODEL BEFORE any migration
- Migrate authentication app FIRST, then everything else
- engine app is NEVER manually edited — only written by CalculationEngine
- Menu save signal always triggers CalculationEngine.run()

