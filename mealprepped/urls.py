# mealprepped/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.recipe_list, name="home"),
    path("ingredients-list/", views.ingredient_list, name="ingredients_list"),
    path("recipes-list/",     views.recipe_list,    name="recipes_list"),
    path("plan/week/",        views.week_entries,   name="week_entries"),
]
