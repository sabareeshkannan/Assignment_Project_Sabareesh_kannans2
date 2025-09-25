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
