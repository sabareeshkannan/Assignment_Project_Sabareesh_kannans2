# mealprepped/views.py

from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
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
