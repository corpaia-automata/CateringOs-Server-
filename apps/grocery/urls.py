from django.urls import path

from . import views

urlpatterns = [
    path('', views.grocery_list, name='grocery-list'),
    path('export/excel/', views.export_excel, name='grocery-export-excel'),
]
