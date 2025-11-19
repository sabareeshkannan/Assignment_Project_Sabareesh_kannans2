# MealPrepped

A Django app to help with weekly meal planning, shopping lists, food expiry reminders, and an inventory dashboard.  
The app also includes a small machine learning recommender to suggest "what to cook next," guiding user decision making in terms of cost and preferences.

### ER Diagram
![ER Diagram](docs/notes/ERDiagram.png)

### Models
- *Ingredient*: catalog of items (`name`, `unit`).
- *Recipe*: A dish (`title`, `servings`, `prep_minutes`, `cook_minutes`).
- *RecipeIngredient*: Linking a ingredients with a `quantity` to one or many recipes.
- *MealPlan*: Date range (e.g., a week).
- *MealPlanEntry*: Date slot in a plan (`date`, `meal_type`) that may reference a `Recipe`.

### Views, Templates & Rendering

I added three views, *Ingredients* (HttpResponse), *Recipes*  and *This Week’s Entries*, available at:

- `/ingredients-list/`
- `/recipes-list/`
- `/plan/week/`

This demonstrates the full Django flow (request → view → template → response) and shows why `render()` is my default for normal pages, while `HttpResponse` is for simple outputs. I also added a `base.html` file to make use of the template inheritance property.

### Class-Based Views & Refactoring

Implemented four CBVs and refactored URLs for modularity.

- **Base CBVs** (`View`): `MealPlanDetailView`, `IngredientDetailView`
- **Generic CBVs**: `MealPlanListView` , `RecipeDetailView` 
- Refactored project `urls.py` to only `admin/` and `include('mealprepped.urls')`
- Namespaced app URLs (`app_name = "mealprepped"`)
- Templates use `base.html`, `{% for %} ... {% empty %}`, and show ingredient quantity with unit

**Routes to test**
- `/mealplans/` generic list
- `/mealplans/<id>/` base detail
- `/ingredients/<id>/` base detail
- `/recipes/<id>/` generic detail (with ingredients)

### Search & Aggregations

- **RecipeListView (ListView)**: Search over `title`/`description` with `{% for %}…{% empty %}` for the no-results case.  
- **Stats**: Total recipes, **Most-used recipes** , and **Recipes by ingredient count**   

### Static Files + Charts

- Custom CSS files were linked in `base.html` to apply a consistent site theme using Material Design for Bootstrap. 
- A Plotly chart that shows recipe counts by **total time (prep + cook)** in four fixed intervals (≤15, 16–30, 31–45, 46–60 minutes) was also added, to provide users with an overview of the relative meal preparation time.

### GET vs POST in this project

- The recipe search uses **GET**: the query can be found in the URL (`/?q=...`) and the results render on the same page. Creating a recipe uses **POST**: data is sent in the request body and is **CSRF**-protected.

### FBV vs CBV for forms

- I implemented “Add Recipe” two ways. The **FBV** explicitly checks `request.method`, validates, and redirects. The **CBV** uses Django’s `CreateView` with `form_class`, `template_name`, and `success_url` (via `reverse_lazy`), reducing boilerplate while performing the same behavior.

### APIs + JSON Endpoints

- Added JSON API at GET /api/mealplans/status/ returning overall totals and results for "complete" vs "unfilled". 
- The Meal Plans page now includes a Matplotlib pie chart, which fetches the API and returns a PNG image

### External APIs (Open API / Non-Keyed) 

- Added TheMealDB API: HTML at GET /recipes/import/?q=<term> (fields: idMeal, name, category, area, thumb, Total of 9 items for each page).
- Uses requests.get(..., params={"s": q}, timeout=5) with raise_for_status()
- Failures return {"ok": false, "error": "..."} (HTTP 502). The template displays cards or an empty page for no results. 

### CSV / JSON Export + Reports

- Added summary statistics for the meal plan list page and **CSV/JSON exports** functionality for meal plans.  
- The page shows totals and grouped summaries (complete, in progress, filled, empty), plus a quick breakdown by meal type.  
- Added seperate buttons to generate and download CSV files and pretty-printed JSON.

**URLs**
- Button location: `/mealplans-list/`
- Export CSV: `/exports/mealplans.csv`
- Export JSON: `/exports/mealplans.json`

> All the functionalities above require login. It will redirect to the login page if not done so.

### Authentication & Access Control

**Protected routes**
- `/reports/`, `/exports/mealplans.csv`, `/exports/mealplans.json`, and ALL chart/data views.
- Class-based views use `LoginRequiredMixin`& function views use `@login_required`.

**Public routes**
- `/login/`, `/logout/`, `/signup/`

**Redirects**
- Logged-out access to protected pages redirects to `/login/?next=<target>`.
- After login (or signup) the page redirects to the original target page.

**Grading credentials**
- Username: `mohitg2`
- Password: `graingerlibrary`

**Signup flow**
- Built with Django’s `UserCreationForm` in a `SignupView`
- Creates a normal user (`is_staff=False`, `is_superuser=False`) and logs in immediately, then redirects to `next` or the main page.

### Deployment 

This project is deployed on PythonAnywhere at:

- https://kannans2.pythonanywhere.com/  

#### Settings and environments

- The original `settings.py` was split into a settings package:
  - `main/settings/base.py` – shared configuration for all environments (apps, middleware, templates, DB, static).
  - `main/settings/development.py` – imports from `base.py`, used locally for `runserver` and development migrations.
  - `main/settings/production.py` – imports from `base.py`, used on PythonAnywhere.
- Locally I run Django with `DJANGO_SETTINGS_MODULE=main.settings.development`.  
- On PythonAnywhere the WSGI file sets:
  - `DJANGO_SETTINGS_MODULE = "main.settings.production"`  
  - Adds `/home/kannans2/Assignment_Project_Sabareesh_kannans2` to `sys.path`.

#### Deployment flow summary

1. Develop locally using `main.settings.development` (DB under `main/data/db.sqlite3`).
2. Commit and push code (excluding `db.sqlite3`) to GitHub.
3. On PythonAnywhere, clone the repo into `/home/kannans2/Assignment_Project_Sabareesh_kannans2`.
4. Create and activate virtualenv (`myenv-django` with Python 3.12) and run:
   - `pip install -r main/requirements.txt`
5. Apply migrations with production settings:
   - `python manage.py migrate --settings=main.settings.production`
6. Create the instructor superuser:
   - `python manage.py createsuperuser --settings=main.settings.production`
7. Collect static files:
   - `python manage.py collectstatic --settings=main.settings.production`
8. Configure the Web tab:
   - Virtualenv: `/home/kannans2/.virtualenvs/myenv-django`
   - Static: `/static/` → `/home/kannans2/Assignment_Project_Sabareesh_kannans2/main/staticfiles`
   - WSGI: `DJANGO_SETTINGS_MODULE = "main.settings.production"`
9. Reload the app on PythonAnywhere.
