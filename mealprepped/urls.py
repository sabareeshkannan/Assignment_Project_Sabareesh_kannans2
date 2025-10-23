# mealprepped/urls.py
from django.urls import path
from . import views

app_name = "mealprepped"

urlpatterns = [
    path("", views.RecipeListView.as_view(), name="home"),
    path("recipes-list/", views.RecipeListView.as_view(), name="recipes_list"),
    path("ingredients-list/", views.ingredient_list, name="ingredients_list"),
    path("mealplans-list/", views.MealPlanListView.as_view(), name="mealplans_list"),
    path("recipe/<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("ingredient/<int:pk>/", views.IngredientDetailView.as_view(), name="ingredient_detail"),
    path("mealplan/<int:pk>/", views.MealPlanDetailView.as_view(), name="mealplan_detail"),
    path("plan/week/", views.week_entries, name="week_entries"),
    path("charts/total-time.json", views.total_time_chart, name="total_time_chart"),
    path("recipes/add-fbv/", views.recipe_create_fbv, name="recipe_create_fbv"),
    path("recipes/add-cbv/", views.RecipeCreateView.as_view(), name="recipe_create_cbv"),
    path("recipe/<int:pk>/ingredients/", views.manage_recipe_ingredients, name="manage_recipe_ingredients"),
]
