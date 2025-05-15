# problems/forms.py

from django import forms
from .models import Problem

# Pour une saisie simple (parsing côté serveur)
class ManualProblemForm(forms.Form):
    nom = forms.CharField(label="Nom du problème", max_length=255)
    description = forms.CharField(label="Description", required=False, widget=forms.Textarea)
    objective_type = forms.ChoiceField(label="Type d'objectif", choices=Problem.OBJECTIVE_CHOICES)
    # Utiliser des champs texte pour entrer les données comme des listes séparées par des virgules ou JSON partiel
    
    num_variables = forms.IntegerField(label="Nombre de variables", min_value=1)
    objective_coefficients_str = forms.CharField(label="Coefficients de la fonction objectif (séparés par des virgules)", widget=forms.Textarea)
    # Un champ texte unique pour toutes les contraintes (une par ligne, format spécifique)
    constraints_str = forms.CharField(label="Contraintes (une par ligne, format: coef1,coef2,...;sens;rhs)", widget=forms.Textarea)