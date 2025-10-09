# mealprepped/views.py

from datetime import date, timedelta

from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView

from .models import Ingredient, Recipe, MealPlan, MealPlanEntry, RecipeIngredient
from django.db.models import Count, Q


# 1) Ingredient list
def ingredient_list(request):
    ingredients = Ingredient.objects.all().order_by("name")
    template = loader.get_template("mealprepped/ingredient_list.html")
    output = template.render({"ingredients": ingredients}, request)
    return HttpResponse(output)


# 2) Recipes
# def recipe_list(request):
#     recipes = Recipe.objects.all().order_by("title")
#     return render(
#         request,
#         "mealprepped/recipe_list.html",
#         {"recipes": recipes},
#     )

class RecipeListView(ListView):
    model = Recipe
    template_name = "mealprepped/recipe_list.html"
    context_object_name = "recipes"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        q = (self.request.GET.get("q") or "").strip()
        ctx["q"] = q
        ctx["search_results"] = (
            Recipe.objects
            .filter(Q(title__icontains=q) | Q(description__icontains=q))
            .order_by("title")
            if q else None
        )
        ctx["results_count"] = ctx["search_results"].count() if ctx["search_results"] is not None else 0

        # Totals
        ctx["total_recipes"] = Recipe.objects.count()

        ctx["top_used_recipes"] = (
            MealPlanEntry.objects
            .values("recipe__pk", "recipe__title")
            .annotate(n_uses=Count("pk"))
            .order_by("-n_uses", "recipe__title")
        )

        ctx["recipes_by_ingredient_count"] = (
            RecipeIngredient.objects
            .values("recipe__pk", "recipe__title")
            .annotate(n_ings=Count("ingredient", distinct=True))
            .order_by("-n_ings", "recipe__title")
        )

        return ctx


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