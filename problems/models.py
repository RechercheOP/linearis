from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json
from django.contrib.auth.models import User

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
    objective_coefficients = models.JSONField(null=True, blank=True)

    # Stocke les contraintes sous forme de liste de dictionnaires JSON.
    # Ex: [{"coefficients": [1, 1], "sense": "<=", "rhs": 10}, {"coefficients": [2, 0], "sense": ">=", "rhs": 5}]
    constraints = models.JSONField(blank=True, null=True)

    # Noms des variables, utile pour l'affichage (ex: ['x1', 'x2'])
    variable_names = models.JSONField(default=list, blank=True)

    # Nombre de variables, peut être déduit mais utile à stocker
    num_variables = models.IntegerField(null=True, blank=True)
    # --- Fin des champs PL ---


    # --- Champs pour la résolution ---
    solution_variables = models.JSONField(blank=True, null=True) # Ex: [4.0, 4.0]
    optimal_value = models.FloatField(blank=True, null=True)     # Ex: 32.0
    status = models.CharField(max_length=50, blank=True, null=True) # Ex: 'optimal', 'infeasible', 'unbounded', 'error', 'unsupported'
    # Stocke tous les tableaux d'itérations, pour affichage pas à pas.
    # Chaque élément de la liste est un tableau NumPy converti en liste de listes Python.
    tableaus_history = models.JSONField(blank=True, null=True)
    # --- Fin des champs pour la résolution ---

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom

    def clean(self):
        # Vérifier que les listes de coefficients ont la bonne taille
        if self.num_variables is not None:
            if self.objective_coefficients and len(self.objective_coefficients) != self.num_variables:
                 raise ValidationError(_('The number of objective coefficients must match the number of variables.'))
            if self.constraints:
                for i, constraint in enumerate(self.constraints):
                    if 'coefficients' not in constraint or \
                       not isinstance(constraint['coefficients'], list) or \
                       len(constraint['coefficients']) != self.num_variables: # Dépend de num_variables
                        raise ValidationError(_(f'Constraint {i+1} has an invalid number of coefficients.'))
                    if 'sense' not in constraint or constraint['sense'] not in ['<=', '>=', '=']:
                        raise ValidationError(_(f'Constraint {i+1} has an invalid sense.'))
                    if 'rhs' not in constraint or not isinstance(constraint['rhs'], (int, float)):
                        raise ValidationError(_(f'Constraint {i+1} has an invalid right-hand side value.'))
        else:
            # num_variables est None, les champs comme objective_coefficients (None)
            # et variable_names ([]) sont maintenant autorisés à être "blank"
            # donc full_clean ne devrait plus poser de problème pour eux à ce stade.
            pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_created'] # Pour lister les problèmes les plus récents en premier
        verbose_name = "Problème"
        verbose_name_plural = "Problèmes"

class ImportedProblem(Problem):
    """
    Représente un problème de Programmation Linéaire importé depuis un fichier.
    Hérite de la classe Problem et ajoute des fonctionnalités spécifiques à l'importation.
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué')
    ]

    file = models.FileField(
        upload_to='imported_problems/',
        help_text='Fichier PDF ou image contenant le problème'
    )
    statusForImport = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text='Message d\'erreur en cas d\'échec du traitement'
    )
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )
    processing_completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.nom} (Importé)"

    def clean(self):
        super().clean()
        # Vérification du type de fichier
        if self.file:
            file_extension = self.file.name.split('.')[-1].lower()
            if file_extension not in ['pdf', 'png', 'jpg', 'jpeg']:
                raise ValidationError(_('Format de fichier non supporté. Formats acceptés : PDF, PNG, JPG, JPEG'))

    class Meta:
        verbose_name = "Problème importé"
        verbose_name_plural = "Problèmes importés"