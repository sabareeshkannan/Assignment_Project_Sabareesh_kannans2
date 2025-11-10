# mealprepped/urls.py
from django.urls import path
from . import views
from django.contrib.auth.views import LoginView,LogoutView

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
    path("api/mealplans/status/", views.api_mealplans_complete, name="api-mealplans-complete"),
    path("charts/mealplans/fill.png", views.mealplans_pie_png, name="mealplans-pie-png"),
    path("demo/mealplans/fill.txt", views.mealplans_fill_text, name="mealplans-fill-text"),
    path("demo/mealplans/fill.json", views.mealplans_fill_json, name="mealplans-fill-json"),
    path("recipes/import/", views.ExternalMealSearchView.as_view(), name="external-import"),
    path("export/mealplans.csv", views.export_mealplans_csv, name="export_mealplans_csv"),
    path("export/mealplans.json", views.export_mealplans_json, name="export_mealplans_json"),
    path("login/", LoginView.as_view(template_name="mealprepped/login.html"), name="login_urlpattern"),
    path("logout/", LogoutView.as_view(),
         name="logout_urlpattern"),
    path("signup/", views.signup_view, name="signup_urlpattern"),
]
