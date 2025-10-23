# mealprepped/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from .models import Recipe, RecipeIngredient


class RecipeCreateForm(forms.ModelForm):
    prep_minutes = forms.IntegerField(min_value=0, validators=[MinValueValidator(0)])
    cook_minutes = forms.IntegerField(min_value=0, validators=[MinValueValidator(0)])

    class Meta:
        model = Recipe
        fields = ["title", "description", "servings", "prep_minutes", "cook_minutes"]

    def clean_title(self):
        v = self.cleaned_data.get("title", "").strip()
        if len(v) < 5:
            raise ValidationError("Title must be at least 5 characters.")
        return v


class RecipeSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(attrs={
            "id": "q",
            "type": "search",
            "class": "form-control",
            "placeholder": " ",
            "aria-label": "Search recipes",
            "autocomplete": "off",
        })
    )


class RecipeIngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ["ingredient", "quantity"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }
