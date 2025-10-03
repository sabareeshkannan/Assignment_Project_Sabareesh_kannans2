# mealprepped/urls.py
from django.urls import path
from .views import ingredient_list, recipe_list, week_entries, IngredientDetailView, MealPlanDetailView, MealPlanListView, RecipeDetailView

app_name = "mealprepped"

urlpatterns = [
    path("", recipe_list, name="home"),
    path("ingredients-list/", ingredient_list, name="ingredients_list"),
    path("recipes-list/", recipe_list, name="recipes_list"),
    path("plan/week/", week_entries, name="week_entries"),
    path("mealplan/<int:primary_key>/", MealPlanDetailView.as_view(), name="mealplan_detail"),
    path("mealplans-list/", MealPlanListView.as_view(), name="mealplans_list"),
    path("recipe/<int:pk>/", RecipeDetailView.as_view(), name="recipe_detail"),
    path("ingredient/<int:pk>/", IngredientDetailView.as_view(), name="ingredient_detail"),
]
