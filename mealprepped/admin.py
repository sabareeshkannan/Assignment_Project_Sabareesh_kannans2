from django.contrib import admin
from .models import Ingredient, Recipe, RecipeIngredient, MealPlan, MealPlanEntry

# Register your models here.
admin.site.register(Ingredient)
admin.site.register(Recipe)
admin.site.register(RecipeIngredient)
admin.site.register(MealPlan)
admin.site.register(MealPlanEntry)