from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


# ---------- Shared timestamps ----------
class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# ---------- Ingredient list ----------
class Ingredient(Timestamped):
    ingredient_id = models.AutoField(primary_key=True)

    # May need changes (additional units), keep it simple for now
    units = [
        ("g", "grams"),
        ("kg", "kilograms"),
        ("ml", "millilitres"),
        ("l", "litres"),
        ("pcs", "pieces"),
    ]

    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=10, choices=units, default="g")

    # Ordered by name, may change it to ordered by importance and amount left
    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.unit})"


# ---------- Recipe (parent) ----------
class Recipe(Timestamped):
    recipe_id = models.AutoField(primary_key=True)

    title = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    servings = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    prep_minutes = models.IntegerField(default=0)
    cook_minutes = models.IntegerField(default=0)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


# ---------- RecipeIngredient (association with payload) ----------
class RecipeIngredient(Timestamped):
    # PK for the join rows
    recipe_item_id = models.AutoField(primary_key=True)

    # Many items belong to one recipe
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,     # deleting a recipe removes its line items
        related_name="items",
    )

    # Each item points to one ingredient
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,     # protect against deleting an in-use ingredient
        related_name="used_in",
    )

    quantity = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    class Meta:
        # Do not allow the same ingredient twice in the same recipe
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_ingredient_per_recipe",
            )
        ]

        ordering = ["recipe__title", "ingredient__name"]

    def __str__(self):
        return f"{self.quantity} {self.ingredient.unit} {self.ingredient.name} for {self.recipe.title}"


# ---------- MealPlan (parent) ----------
class MealPlan(Timestamped):
    mealplan_id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        # Same plan name can repeat across weeks, but not with the same start
        constraints = [
            models.UniqueConstraint(
                fields=["name", "start_date"],
                name="unique_mealplan_start",
            )
        ]
        # Newest first is more useful
        ordering = ["-start_date", "name"]

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")


# ---------- MealPlanEntry (child of MealPlan) ----------
class MealPlanEntry(Timestamped):
    entry_id = models.AutoField(primary_key=True)

    MEAL_TYPES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
        ("snack", "Snack"),
    ]

    # Many entries belong to one plan
    meal_plan = models.ForeignKey(
        MealPlan,
        on_delete=models.CASCADE,     # deleting a plan removes its entries
        related_name="entries",
    )

    date = models.DateField()
    meal_type = models.CharField(max_length=12, choices=MEAL_TYPES)

    # Keep the slot even if the recipe is deleted (indicates TBD after deletion)
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_in",
    )

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        # Only one slot per (plan, date, meal_type)
        constraints = [
            models.UniqueConstraint(
                fields=["meal_plan", "date", "meal_type"],
                name="uniq_meal_slot",
            )
        ]
        ordering = ["date", "meal_type"]

        indexes = [
            models.Index(fields=["meal_plan", "date"]),
        ]

    def __str__(self):
        return f"{self.date} {self.meal_type}: {self.recipe or 'TBD'}"