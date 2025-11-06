# mealprepped/views.py

from datetime import date, timedelta
import io
import json
from urllib.request import urlopen
import requests

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from django.contrib import messages
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from .forms import RecipeCreateForm, RecipeSearchForm, RecipeIngredientForm
from .models import Ingredient, MealPlan, MealPlanEntry, Recipe, RecipeIngredient


# 1) Ingredient list
def ingredient_list(request):
    ingredients = Ingredient.objects.all().order_by("name")
    template = loader.get_template("mealprepped/ingredient_list.html")
    output = template.render({"ingredients": ingredients}, request)
    return HttpResponse(output)


class RecipeListView(ListView):
    model = Recipe
    template_name = "mealprepped/recipe_list.html"
    context_object_name = "recipes"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        form = RecipeSearchForm(self.request.GET)
        ctx["form"] = form
        q = ""
        if form.is_valid():
            q = (form.cleaned_data.get("q")).strip()

        ctx["q"] = q
        ctx["search_results"] = (
            Recipe.objects
            .filter(Q(title__icontains=q) | Q(description__icontains=q))
            .order_by("title")
        ) if q else None
        ctx["results_count"] = ctx["search_results"].count() if ctx["search_results"] is not None else 0

        # stats
        ctx["total_recipes"] = Recipe.objects.count()
        ctx["top_used_recipes"] = (
            MealPlanEntry.objects.filter(recipe__isnull=False)
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


def total_time_chart(request):
    data = Recipe.objects.annotate(total=F("prep_minutes") + F("cook_minutes"))

    agg = data.aggregate(
        le15=Count("pk", filter=Q(total__lte=15)),
        m16_30=Count("pk", filter=Q(total__gt=15, total__lte=30)),
        m31_45=Count("pk", filter=Q(total__gt=30, total__lte=45)),
        m46_60=Count("pk", filter=Q(total__gt=45, total__lte=60)),
    )

    labels = ["≤15m", "16–30m", "31–45m", "46–60m"]
    counts = [
        agg.get("le15") or 0,
        agg.get("m16_30") or 0,
        agg.get("m31_45") or 0,
        agg.get("m46_60") or 0,
    ]

    def titles(lo, hi, limit=12):
        qs = (data.filter(total__gte=lo, total__lte=hi)
              .values_list("title", flat=True)
              .order_by("title"))
        shown = list(qs[:limit])
        more = max(0, qs.count() - len(shown))
        return "<br>".join(shown) + (f"<br>+{more} more" if more else "") if shown else "No recipes"

    hover_texts = [titles(0, 15), titles(16, 30), titles(31, 45), titles(46, 60)]

    fig = {
        "data": [{
            "type": "bar",
            "x": labels,
            "y": counts,
            "marker": {"color": "#0e67b6"},
            "customdata": hover_texts,
            "hovertemplate": "%{x}<br>%{y} recipe(s)<br><br>%{customdata}<extra></extra>",
        }],
        "layout": {
            "title": "Total time (prep + cook)",
            "yaxis": {"title": "Recipes", "gridcolor": "rgba(0,0,0,.1)"},
            "margin": {"l": 50, "r": 20, "t": 40, "b": 50},
            "height": 300,
            "template": "plotly_white",
        },
    }
    return JsonResponse(fig, safe=False)


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
    def get(self, request, pk):
        mealplan = get_object_or_404(MealPlan, pk=pk)
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = MealPlan.objects.annotate(n_entries=Count("entries"))
        total = qs.count()
        filled = qs.filter(n_entries__gt=0).count()
        unfilled = max(total - filled, 0)

        ctx["total_mealplans"] = total
        ctx["filled_mealplans"] = filled
        ctx["unfilled_mealplans"] = unfilled
        return ctx


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


# FBV
def recipe_create_fbv(request):
    if request.method == "POST":
        form = RecipeCreateForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Recipe '{obj.title}' created successfully.")
            return redirect("mealprepped:manage_recipe_ingredients", pk=obj.pk)
    else:
        form = RecipeCreateForm()
    return render(request, "mealprepped/recipe_form.html", {"form": form})


# CBV
class RecipeCreateView(CreateView):
    model = Recipe
    form_class = RecipeCreateForm
    template_name = "mealprepped/recipe_form.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Recipe '{self.object.title}' created successfully.")
        return resp

    def get_success_url(self):
        return reverse_lazy(
            "mealprepped:manage_recipe_ingredients",
            kwargs={"pk": self.object.pk},
        )


def manage_recipe_ingredients(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    items = (RecipeIngredient.objects
             .filter(recipe=recipe)
             .select_related("ingredient")
             .order_by("ingredient__name"))

    if request.method == "POST":
        form = RecipeIngredientForm(request.POST)
        if form.is_valid():
            ing = form.cleaned_data["ingredient"]
            qty = form.cleaned_data["quantity"]
            RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, quantity=qty)
            messages.success(
                request,
                f"Added {qty} {ing.get_unit_display()} of {ing.name} to “{recipe.title}”."
            )
            return redirect("mealprepped:manage_recipe_ingredients", pk=recipe.pk)
    else:
        form = RecipeIngredientForm()

    return render(request, "mealprepped/manage_recipe_ingredients.html", {
        "recipe": recipe,
        "items": items,
        "form": form,
    })


def api_mealplans_complete(request):
    qs = (MealPlan.objects.annotate(
        covered=Count("entries__date",
                      distinct=True,
                      filter=Q(
                          entries__date__gte=F("start_date"),
                          entries__date__lte=F("end_date"),
                      ),
                      )
    ).values("mealplan_id", "covered"))

    total = 0
    complete = 0
    for row in qs:
        total += 1
        if row["covered"] >= 7:
            complete += 1

    unfilled = max(total - complete, 0)

    return JsonResponse({
        "total": total,
        "complete": complete,
        "unfilled": unfilled,
        "results": [
            {"status": "complete", "n": complete},
            {"status": "unfilled", "n": unfilled},
        ],
    })


def mealplans_pie_png(request):
    api_url = request.build_absolute_uri(reverse("mealprepped:api-mealplans-complete"))
    with urlopen(api_url) as resp:
        payload = json.load(resp)

    complete = next((r["n"] for r in payload.get("results", []) if r["status"] == "complete"), 0)
    unfilled = next((r["n"] for r in payload.get("results", []) if r["status"] == "unfilled"), 0)
    total = complete + unfilled

    fig, ax = plt.subplots()

    if total == 0:
        ax.pie([1], labels=["No plans"], colors=["#e5e7eb"], startangle=90)
    else:
        ax.pie(
            [complete, unfilled],
            labels=["Complete", "Unfilled"],
            colors=["#0F766E", "#DC2626"],
            startangle=90,
            autopct=lambda p: f"{int(round(p * total / 100.0))}",
        )

    ax.set_aspect("equal")
    ax.set_title("Meal Plans: Filled vs Unfilled")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return HttpResponse(buf.getvalue(), content_type="image/png")


def mealplans_fill_text(request):
    qs = MealPlan.objects.annotate(n=Count("entries"))
    total = qs.count()
    filled = qs.filter(n__gt=0).count()
    unfilled = max(total - filled, 0)
    return HttpResponse(f"total={total}, filled={filled}, unfilled={unfilled}", content_type="text/plain")


def mealplans_fill_json(request):
    qs = MealPlan.objects.annotate(n=Count("entries"))
    total = qs.count()
    filled = qs.filter(n__gt=0).count()
    unfilled = max(total - filled, 0)
    return JsonResponse({"total": total, "filled": filled, "unfilled": unfilled})


class ExternalMealSearchView(View):
    template_name = "mealprepped/external_import.html"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        json_output = request.GET.get("format") == "json"

        searched = bool(q)
        results = []
        error: str | None = None

        if searched:
            try:
                resp = requests.get("https://www.themealdb.com/api/json/v1/1/search.php",
                    params={"s": q},
                    timeout=5, )

                resp.raise_for_status()
                data = resp.json() or {}
                meals = data.get("meals")

                trimmed = []
                for m in meals[:9]:
                    trimmed.append({
                        "idMeal": m.get("idMeal"),
                        "name": (m.get("strMeal") or "").strip(),
                        "category": (m.get("strCategory") or "").strip(),
                        "area": (m.get("strArea") or "").strip(),
                        "thumb": (m.get("strMealThumb") or "").strip(),
                    })
                results = trimmed

            except requests.exceptions.RequestException as e:
                error = str(e)

        if json_output:
            if error:
                return JsonResponse({"ok": False, "error": error}, status=502)
            return JsonResponse({"ok": True, "query": q, "count": len(results), "results": results})

        ctx = {"query": q, "searched": searched, "results": results, "error": error}
        return render(request, self.template_name, ctx)
