# mealprepped/views.py

from datetime import date, timedelta

from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView

from .models import Ingredient, Recipe, MealPlan, MealPlanEntry, RecipeIngredient


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
        MealPlanEntry.objects
        .filter(date__range=(start, end))
        .select_related("meal_plan", "recipe")
        .order_by("date", "meal_type")
    )
    return render(
        request,
        "mealprepped/entries_week.html",
        {"entries": entries, "start": start, "end": end},
    )

class MealPlanDetailView(View):
    def get(self, request, primary_key):
        mealplan = get_object_or_404(MealPlan, pk=primary_key)
        entries = (MealPlanEntry.objects
                   .select_related("recipe", "meal_plan")
                   .filter(meal_plan=mealplan)
                   .order_by("date", "meal_type"))
        return render(request, "mealprepped/mealplan_detail.html", {
            "mealplan": mealplan, "entries": entries, "total_entries": entries.count(),
        })


class MealPlanListView(ListView):
    model = MealPlan
    context_object_name = "mealplans"
    paginate_by = 10
    ordering = ["-created_at"]


class RecipeDetailView(DetailView):
    model = Recipe
    context_object_name = "recipe"
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ingredients"] = (
            RecipeIngredient.objects
            .select_related("ingredient")
            .filter(recipe=self.object)
            .order_by("pk")
        )
        return ctx


class IngredientDetailView(View):
    def get(self, request, primary_key):
        ingredient = get_object_or_404(Ingredient, pk=primary_key)
        recipes = (
            Recipe.objects
            .filter(recipeingredient__ingredient=ingredient)
        )
        total_recipes = recipes.count()
        return render(
            request,
            "mealprepped/ingredient_detail.html",
            {
                "ingredient": ingredient,
                "recipes": recipes,
                "total_recipes": total_recipes,
            },
        )