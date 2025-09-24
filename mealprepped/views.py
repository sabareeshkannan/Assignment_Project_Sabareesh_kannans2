from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render
from .models import Ingredient, Recipe, MealPlanEntry
from datetime import date, timedelta


# 1) Ingredient list
def ingredient_list(request):
    ingredients = Ingredient.objects.all().order_by("name")
    template = loader.get_template("mealprepped/ingredient_list.html")
    output = template.render({"ingredients": ingredients}, request)
    return HttpResponse(output)


# 2) Recipes
def recipe_list(request):
    recipes = Recipe.objects.all().order_by("title")
    return render(
        request,
        "mealprepped/recipe_list.html",
        {"recipes": recipes},
    )

# 3) This week's MealPlan entries
def week_entries(request):
    start = date.today()
    end = start + timedelta(days=6)
    entries = (
        MealPlanEntry.objects.all()
        .filter(date__range=(start, end))
        .select_related("meal_plan", "recipe")
        .order_by("date", "meal_type")
    )
    return render(request,"mealprepped/entries_week.html",{"entries": entries, "start": start, "end": end},
    )