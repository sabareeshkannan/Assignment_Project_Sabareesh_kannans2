# mealprepped/views.py
import csv
from datetime import date, timedelta, datetime
import io
import json
from urllib.request import urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from collections import defaultdict
from typing import Optional, Tuple, List, Dict, Any
import re, requests

from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models import Count, F, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from django.utils.dateparse import parse_date

from .forms import RecipeCreateForm, RecipeSearchForm, RecipeIngredientForm
from .models import Ingredient, MealPlan, MealPlanEntry, Recipe, RecipeIngredient

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms_auth import PublicSignUpForm


# 1) Ingredient list
@login_required(login_url="mealprepped:login_urlpattern")
def ingredient_list(request):
    ingredients = Ingredient.objects.all().order_by("name")
    template = loader.get_template("mealprepped/ingredient_list.html")
    output = template.render({"ingredients": ingredients}, request)
    return HttpResponse(output)


class RecipeListView(LoginRequiredMixin, ListView):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"

    model = Recipe                          # <-- ensures ListView has a queryset
    template_name = "mealprepped/recipe_list.html"
    context_object_name = "recipes"
    queryset = Recipe.objects.order_by("title")  # optional but explicit

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        form = RecipeSearchForm(self.request.GET)
        ctx["form"] = form
        q = ""
        if form.is_valid():
            q = (form.cleaned_data.get("q") or "").strip()

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

    def render_to_response(self, context, **response_kwargs):
        if (self.request.GET.get("format") or "").lower() == "json":
            results_qs = context.get("search_results") or Recipe.objects.order_by("-created_at", "title")
            data = {
                "ok": True,
                "results": [{"id": r.pk, "title": r.title} for r in results_qs[:20]],
            }
            return JsonResponse(data)
        return super().render_to_response(context, **response_kwargs)


@login_required(login_url="mealprepped:login_urlpattern")
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
@login_required(login_url="mealprepped:login_urlpattern")
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


class MealPlanDetailView(LoginRequiredMixin, View):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
    template_name = "mealprepped/mealplan_detail.html"
    def _calendar(self, mp, entries):
        days = []
        if mp.start_date and mp.end_date and mp.end_date >= mp.start_date:
            span = (mp.end_date - mp.start_date).days + 1
            days = [mp.start_date + timedelta(days=i) for i in range(span)]
        by_date = defaultdict(list)
        for e in entries:
            if e.date:
                by_date[e.date].append(e)
        covered = sum(1 for d in days if by_date.get(d))
        pct = int(round(100 * covered / len(days))) if days else 0
        weeks = [{
            "start": days[i],
            "end": days[min(i + 6, len(days) - 1)],
            "days": [{"date": d, "entries": by_date.get(d, [])} for d in days[i:i + 7]],
        } for i in range(0, len(days), 7)]
        return weeks, covered, len(days), pct

    def get(self, request, pk):
        mp = get_object_or_404(MealPlan, pk=pk)
        entries = (MealPlanEntry.objects
                   .select_related("recipe")
                   .filter(meal_plan=mp)
                   .order_by("date", "meal_type", "pk"))

        weeks, covered, total_days, pct = self._calendar(mp, entries)

        top_recipes = (MealPlanEntry.objects
        .filter(meal_plan=mp, recipe__isnull=False)
        .values("recipe__pk", "recipe__title")
        .annotate(n=Count("pk"))
        .order_by("-n", "recipe__title")[:5])
        prev_plan = MealPlan.objects.filter(pk__lt=mp.pk).order_by("-pk").first()
        next_plan = MealPlan.objects.filter(pk__gt=mp.pk).order_by("pk").first()

        recipe_results = None
        if request.GET.get("add"):
            q = (request.GET.get("q") or "").strip()
            if q:
                recipe_results = (Recipe.objects
                .filter(Q(title__icontains=q) | Q(description__icontains=q))
                .order_by("title")[:25])
            else:
                recipe_results = (Recipe.objects
                .order_by("-created_at", "title")[:25])

        prefill_date = request.GET.get("date")
        if not prefill_date and mp.start_date:
            prefill_date = mp.start_date.strftime("%Y-%m-%d")

        ctx = {
            "mealplan": mp,
            "entries": entries,
            "total_entries": entries.count(),
            "weeks": weeks,
            "covered_days": covered,
            "total_days": total_days,
            "coverage_pct": pct,
            "unique_recipes_count": entries.exclude(recipe=None).values("recipe_id").distinct().count(),
            "top_recipes": top_recipes,
            "prev_plan": prev_plan,
            "next_plan": next_plan,
            "meal_type_choices": MealPlanEntry._meta.get_field("meal_type").choices,
            "recipe_search_results": recipe_results,
            "prefill_date": prefill_date,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        mp = get_object_or_404(MealPlan, pk=pk)
        detail_url = reverse("mealprepped:mealplan_detail", args=[mp.pk])

        d = parse_date((request.POST.get("date") or "").strip())
        meal_type = (request.POST.get("meal_type") or "").strip()
        rid = request.POST.get("recipe_id")

        if not d:
            messages.error(request, "Please choose a valid date.")
            return redirect(f"{detail_url}?add=1#add-panel")

        if (mp.start_date and d < mp.start_date) or (mp.end_date and d > mp.end_date):
            messages.error(request, "Date is outside this plan.")
            return redirect(f"{detail_url}#d-{d.isoformat()}")

        try:
            recipe = Recipe.objects.get(pk=int(rid))
        except Exception:
            messages.error(request, "Please select a recipe.")
            return redirect(f"{detail_url}?add=1#add-panel")

        if not meal_type:
            messages.error(request, "Please pick a meal type.")
            return redirect(f"{detail_url}?add=1#add-panel")

        try:
            with transaction.atomic():
                obj, created = MealPlanEntry.objects.update_or_create(
                    meal_plan=mp,
                    date=d,
                    meal_type=meal_type,
                    defaults={"recipe": recipe},
                )
        except IntegrityError:
            obj = MealPlanEntry.objects.get(
                meal_plan=mp, date=d, meal_type=meal_type
            )
            obj.recipe = recipe
            obj.save()
            created = False

        meal_label = getattr(obj, "get_meal_type_display", lambda: meal_type)().lower()
        key = f"ADD:{mp.pk}:{d.isoformat()}:{meal_type}:{recipe.pk}"
        if request.session.get("last_add_key") != key:
            if created:
                messages.success(
                    request, f'Added “{recipe.title}” on {d:%b %d} ({meal_label}).'
                )
            else:
                messages.info(
                    request, f'Updated to “{recipe.title}” on {d:%b %d} ({meal_label}).'
                )
            request.session["last_add_key"] = key
        return redirect(f"{detail_url}#d-{d.isoformat()}")


class MealPlanListView(LoginRequiredMixin, ListView):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
    model = MealPlan
    context_object_name = "mealplans"
    paginate_by = 10
    def get_queryset(self):
        qs = (
            MealPlan.objects
            .annotate(
                n_entries=Count("entries"),
                covered_days=Count(
                    "entries__date",
                    distinct=True,
                    filter=Q(
                        entries__date__gte=F("start_date"),
                        entries__date__lte=F("end_date"),
                    ),
                ),
            )
        )

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)

        status = (self.request.GET.get("status") or "").strip()
        if status == "empty":
            qs = qs.filter(n_entries=0)
        elif status == "filled":
            qs = qs.filter(n_entries__gt=0)
        elif status == "complete":
            qs = qs.filter(covered_days=7)
        elif status == "inprogress":
            qs = qs.filter(n_entries__gt=0, covered_days__lt=7)

        # Sorting
        sort = (self.request.GET.get("sort") or "new").strip()
        if sort == "name":
            qs = qs.order_by("name", "-mealplan_id")
        elif sort == "old":
            qs = qs.order_by("created_at", "mealplan_id")
        else:  # "new"
            qs = qs.order_by("-created_at", "-mealplan_id")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = MealPlan.objects.annotate(
            n=Count("entries"),
            covered_days=Count(
                "entries__date",
                distinct=True,
                filter=Q(
                    entries__date__gte=F("start_date"),
                    entries__date__lte=F("end_date"),
                ),
            ),
        ).values("start_date", "end_date", "n", "covered_days")

        total = base.count()
        complete = 0
        for row in base:
            sd, ed = row["start_date"], row["end_date"]
            if sd and ed:
                total_days = (ed - sd).days + 1  # inclusive
                if total_days == 7 and row["covered_days"] == 7:
                    complete += 1

        filled_any = sum(1 for row in base if row["n"] > 0)
        inprogress = max(filled_any - complete, 0)
        unfilled = max(total - filled_any, 0)

        ctx.update({
            "total_mealplans": total,
            "complete_mealplans": complete,
            "inprogress_mealplans": inprogress,
            "filled_mealplans": filled_any,
            "unfilled_mealplans": unfilled,
        })

        for mp in ctx["mealplans"]:
            if mp.start_date and mp.end_date:
                total_days = (mp.end_date - mp.start_date).days + 1
            else:
                total_days = 0
            mp.total_days = total_days

            covered = getattr(mp, "covered_days", 0) or 0
            mp.coverage_pct = int(round(100 * covered / total_days)) if total_days else 0

            if total_days == 7 and covered == 7:
                mp.status_label = "Complete"
                mp.status_css = "success"
            elif mp.n_entries > 0:
                mp.status_label = "In progress"
                mp.status_css = "info"
            else:
                mp.status_label = "Empty"
                mp.status_css = "secondary"

        # Preserve controls (unchanged)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["status"] = (self.request.GET.get("status") or "").strip()
        ctx["sort"] = (self.request.GET.get("sort") or "new").strip()
        return ctx


class RecipeDetailView(LoginRequiredMixin, DetailView):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
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


class IngredientDetailView(LoginRequiredMixin, View):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
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
@login_required(login_url="mealprepped:login_urlpattern")
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
class RecipeCreateView(LoginRequiredMixin, CreateView):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
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


@login_required(login_url="mealprepped:login_urlpattern")
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


@login_required(login_url="mealprepped:login_urlpattern")
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


@login_required(login_url="mealprepped:login_urlpattern")
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


@login_required(login_url="mealprepped:login_urlpattern")
def mealplans_fill_text(request):
    qs = MealPlan.objects.annotate(n=Count("entries"))
    total = qs.count()
    filled = qs.filter(n__gt=0).count()
    unfilled = max(total - filled, 0)
    return HttpResponse(f"total={total}, filled={filled}, unfilled={unfilled}", content_type="text/plain")


@login_required(login_url="mealprepped:login_urlpattern")
def mealplans_fill_json(request):
    qs = MealPlan.objects.annotate(n=Count("entries"))
    total = qs.count()
    filled = qs.filter(n__gt=0).count()
    unfilled = max(total - filled, 0)
    return JsonResponse({"total": total, "filled": filled, "unfilled": unfilled})


def _parse_measure(s: str) -> Tuple[Optional[float], str]:
    s = (s or "").strip()
    if not s:
        return None, ""
    m = re.match(r"^\s*(\d+)\s+(\d+/\d+)\s*(.*)$", s)  # 1 1/2 cup
    if m:
        whole = float(m.group(1));
        a, b = m.group(2).split("/")
        return whole + float(a) / float(b), m.group(3).strip()
    m = re.match(r"^\s*(\d+/\d+)\s*(.*)$", s)  # 3/4 tsp
    if m:
        a, b = m.group(1).split("/")
        return float(a) / float(b), m.group(2).strip()
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", s)  # 2.5 tbsp, 2 cloves
    if m:
        return float(m.group(1)), m.group(2).strip()
    return None, s

MEALDB_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"

class ExternalMealSearchView(LoginRequiredMixin, ListView):
    login_url = "mealprepped:login_urlpattern"
    redirect_field_name = "next"
    template_name = "mealprepped/external_import.html"
    context_object_name = "results"
    paginate_by = 9

    q: str = ""
    error: Optional[str] = None

    def get_queryset(self) -> List[Dict[str, Any]]:
        self.q = (self.request.GET.get("q") or "").strip()
        self.error = None
        if not self.q:
            return []
        try:
            r = requests.get(MEALDB_SEARCH_URL, params={"s": self.q}, timeout=5)
            r.raise_for_status()
            meals = (r.json() or {}).get("meals") or []
        except (requests.exceptions.RequestException, ValueError) as e:
            self.error = str(e)
            return []

        return [{
            "idMeal": m.get("idMeal"),
            "name": (m.get("strMeal") or "").strip(),
            "category": (m.get("strCategory") or "").strip(),
            "area": (m.get("strArea") or "").strip(),
            "thumb": (m.get("strMealThumb") or "").strip(),
        } for m in meals]

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        paginator = ctx.get("paginator")
        page_obj = ctx.get("page_obj")
        ctx.update({
            "query": self.q,
            "searched": bool(self.q),
            "error": self.error,
        })
        if paginator and page_obj:
            ctx.update({
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "pages": list(paginator.page_range),
                "has_prev": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
                "prev_page": page_obj.previous_page_number() if page_obj.has_previous() else 1,
                "next_page": page_obj.next_page_number() if page_obj.has_next() else paginator.num_pages,
            })
        else:
            ctx.update({
                "page": 1, "num_pages": 0, "pages": [],
                "has_prev": False, "has_next": False,
                "prev_page": 1, "next_page": 1,
            })
        return ctx

    def post(self, request: HttpRequest) -> HttpResponse:
        id_meal = (request.POST.get("idMeal") or "").strip()
        q = (request.POST.get("q") or "").strip()
        page = request.POST.get("page") or "1"
        if not (id_meal and q):
            messages.error(request, "Try again.")
            return redirect(f"{request.path}?q={q}&page={page}")

        try:
            r = requests.get(MEALDB_SEARCH_URL, params={"s": q}, timeout=5)
            r.raise_for_status()
            meals = (r.json() or {}).get("meals") or []
            m = next((x for x in meals if x.get("idMeal") == id_meal), None)
            if not m:
                messages.error(request, "Recipe not found.")
                return redirect(f"{request.path}?q={q}&page={page}")

            title = (m.get("strMeal") or "").strip()
            desc = (m.get("strInstructions") or "").strip()

            with transaction.atomic():
                recipe, _ = Recipe.objects.get_or_create(title=title, defaults={"description": desc})
                if hasattr(recipe, "description") and not recipe.description and desc:
                    recipe.description = desc
                    recipe.save()

                item_mgr = getattr(recipe, "items", None)
                if item_mgr:
                    link_model = item_mgr.model
                    for i in range(1, 21):
                        name = (m.get(f"strIngredient{i}") or "").strip()
                        meas = (m.get(f"strMeasure{i}") or "").strip()
                        if not name:
                            continue
                        qty, unit = _parse_measure(meas)
                        ing = Ingredient.objects.filter(name__iexact=name).first() or Ingredient(name=name)
                        if hasattr(ing, "unit") and unit and not getattr(ing, "unit"):
                            ing.unit = unit
                        ing.save()

                        kwargs = {"ingredient": ing}
                        defaults = {}
                        if hasattr(link_model, "quantity"):
                            defaults["quantity"] = qty if qty is not None else 1
                        if hasattr(link_model, "unit") and unit:
                            defaults["unit"] = unit
                        obj, created = item_mgr.get_or_create(**kwargs, defaults=defaults)
                        if not created and hasattr(obj, "quantity") and qty is not None:
                            obj.quantity = qty
                            if hasattr(obj, "unit") and unit:
                                obj.unit = unit
                            obj.save()

            name_for_msg = getattr(recipe, "title", None) or title
            messages.success(request, f'Added “{name_for_msg}”')
        except (requests.exceptions.RequestException, ValueError) as e:
            messages.error(request, f"Import failed: {e}")

        return redirect(f"{request.path}?q={q}&page={page}")


@login_required(login_url="mealprepped:login_urlpattern")
def export_mealplans_csv(request):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"mealplans_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)

    writer.writerow(["mealplan_id", "name", "start_date", "end_date", "n_entries", "n_days"])

    qs = (MealPlan.objects
          .annotate(
              n_entries=Count("entries"),
              n_days=Count("entries__date", distinct=True),
          )
          .order_by("start_date", "mealplan_id"))

    for mp in qs.values_list("mealplan_id", "name", "start_date", "end_date", "n_entries", "n_days"):
        writer.writerow(mp)

    return response


@login_required(login_url="mealprepped:login_urlpattern")
def export_mealplans_json(request):
    qs = (MealPlan.objects
          .annotate(
              n_entries=Count("entries"),
              n_days=Count("entries__date", distinct=True),
          )
          .order_by("start_date", "mealplan_id"))

    data = list(qs.values("mealplan_id", "name", "start_date", "end_date", "n_entries", "n_days"))

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(data),
        "mealplans": data,
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"mealplans_{timestamp}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def signup_view(request):
    if request.method == "POST":
        form = PublicSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_staff or user.is_superuser:
                user.is_staff = False
                user.is_superuser = False
                user.save(update_fields=["is_staff", "is_superuser"])
            login(request, user)
            return redirect("mealprepped:mealplans_list")
    else:
        form = PublicSignUpForm()
    return render(request, "mealprepped/signup.html", {"form": form})

