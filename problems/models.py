from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json

class Problem(models.Model):
    """
    Représente un problème de Programmation Linéaire.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='problems')
    nom = models.CharField(max_length=255)

    # --- Champs pour le problème de PL ---
    OBJECTIVE_CHOICES = [
        ('max', 'Maximisation'),
        ('min', 'Minimisation'),
    ]
    objective_type = models.CharField(
        max_length=3,
        choices=OBJECTIVE_CHOICES,
        default='max'
    )
    # Champs pour stocker les équations brutes (nouvellement ajoutés)
    objective_equation_str = models.CharField(max_length=500, blank=True, null=True)
    constraints_equation_str = models.TextField(blank=True, null=True)
    
    # Stocke les coefficients de la fonction objectif sous forme de liste JSON. Ex: [3, 5] pour 3x1 + 5x2
    objective_coefficients = models.JSONField()

    # Stocke les contraintes sous forme de liste de dictionnaires JSON.
    # Ex: [{"coefficients": [1, 1], "sense": "<=", "rhs": 10}, {"coefficients": [2, 0], "sense": ">=", "rhs": 5}]
    constraints = models.JSONField()

    # Noms des variables, utile pour l'affichage (ex: ['x1', 'x2'])
    variable_names = models.JSONField(default=list)

    # Nombre de variables, peut être déduit mais utile à stocker
    num_variables = models.IntegerField()
    # --- Fin des champs PL ---

    # Champs liés à l'import (verrons plus tard)
    import_file = models.FileField(upload_to='problem_imports/', blank=True, null=True)
    raw_text = models.TextField(blank=True, null=True) # Texte extrait par OCR/IA

    # --- Nouveaux champs pour la résolution ---
    solution_variables = models.JSONField(blank=True, null=True) # Ex: [4.0, 4.0]
    optimal_value = models.FloatField(blank=True, null=True)     # Ex: 32.0
    status = models.CharField(max_length=50, blank=True, null=True) # Ex: 'optimal', 'infeasible', 'unbounded', 'error', 'unsupported'
    # Stocke tous les tableaux d'itérations, pour affichage pas à pas.
    # Chaque élément de la liste est un tableau NumPy converti en liste de listes Python.
    tableaus_history = models.JSONField(blank=True, null=True)
    # --- Fin des nouveaux champs ---

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom

    def clean(self):
        # Vérifier que les listes de coefficients ont la bonne taille
        if self.objective_coefficients and len(self.objective_coefficients) != self.num_variables:
             raise ValidationError(_('The number of objective coefficients must match the number of variables.'))
        if self.constraints:
            for i, constraint in enumerate(self.constraints):
                if 'coefficients' not in constraint or \
                   not isinstance(constraint['coefficients'], list) or \
                   len(constraint['coefficients']) != self.num_variables:
                    raise ValidationError(_(f'Constraint {i+1} has an invalid number of coefficients.'))
                if 'sense' not in constraint or constraint['sense'] not in ['<=', '>=', '=']:
                    raise ValidationError(_(f'Constraint {i+1} has an invalid sense.'))
                if 'rhs' not in constraint or not isinstance(constraint['rhs'], (int, float)):
                    raise ValidationError(_(f'Constraint {i+1} has an invalid right-hand side value.'))

    def save(self, *args, **kwargs):
        self.full_clean() # Appelle la méthode clean() avant la sauvegarde
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_created'] # Pour lister les problèmes les plus récents en premier
        verbose_name = "Problème"
        verbose_name_plural = "Problèmes"