from django import forms
from django.contrib import admin

from .models import Category, Dish, DishRecipe, Ingredient


SUSPICIOUS_BATCH_SIZE_MESSAGE = (
    'Batch size looks wrong for a recipe with ingredients. '
    'Set the actual recipe batch size, for example 10 for a 10 KG recipe.'
)


class DishAdminForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        batch_size = cleaned_data.get('batch_size')
        has_existing_recipe = bool(
            self.instance
            and self.instance.pk
            and self.instance.recipe_lines.exists()
        )
        if has_existing_recipe and batch_size is not None and batch_size <= 1:
            raise forms.ValidationError({'batch_size': SUSPICIOUS_BATCH_SIZE_MESSAGE})
        return cleaned_data


class DishRecipeAdminForm(forms.ModelForm):
    class Meta:
        model = DishRecipe
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        dish = cleaned_data.get('dish')
        if dish and dish.batch_size is not None and dish.batch_size <= 1:
            raise forms.ValidationError({'dish': SUSPICIOUS_BATCH_SIZE_MESSAGE})
        return cleaned_data


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('sort_order', 'name')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'unit_of_measure', 'base_qty_ref', 'is_active')
    list_filter = ('category', 'is_active', 'unit_of_measure')
    search_fields = ('name',)
    ordering = ('category', 'name')


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    form = DishAdminForm
    list_display = ('name', 'category', 'serving_unit', 'has_recipe', 'is_active')
    list_filter = ('category', 'is_active', 'has_recipe')
    search_fields = ('name',)
    ordering = ('category', 'name')
    readonly_fields = ('has_recipe',)


@admin.register(DishRecipe)
class DishRecipeAdmin(admin.ModelAdmin):
    form = DishRecipeAdminForm
    list_display = ('dish', 'ingredient', 'qty_per_unit', 'unit')
    list_filter = ('dish__category',)
    search_fields = ('dish__name', 'ingredient__name')
    autocomplete_fields = ('ingredient',)
    ordering = ('dish__name', 'ingredient__name')
