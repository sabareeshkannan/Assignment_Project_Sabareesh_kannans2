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

### 
APIs + JSON Endpoints (External Search)

- Added TheMealDB API: HTML at GET /recipes/import/?q=<term> (fields: idMeal, name, category, area, thumb, Total of 9 items for each page).
- Uses requests.get(..., params={"s": q}, timeout=5) with raise_for_status()
- Failures return {"ok": false, "error": "..."} (HTTP 502). The template displays cards or an empty page for no results. 