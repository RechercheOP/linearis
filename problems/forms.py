from django import forms
from .models import Problem

class ManualProblemForm(forms.ModelForm):
    # Renommer le champ de l'objectif pour refléter qu'il s'agit d'une équation
    # Utiliser un CharField ou TextField pour stocker la chaîne de l'équation
    objective_equation_str = forms.CharField(
        label="Fonction Objectif (Ex: 3x1 + 5x2)",
        max_length=500, # Ajustez la longueur maximale si nécessaire
        help_text="Entrez l'équation de la fonction objectif."
    )

    # Renommer le champ des contraintes pour refléter qu'il s'agit d'équations multilignes
    constraints_equation_str = forms.CharField(
        label="Contraintes (une par ligne)",
        widget=forms.Textarea, # Utiliser un Textarea pour la saisie multiligne
        help_text="Entrez chaque contrainte sur une nouvelle ligne (Ex: x1 + x2 <= 10)."
    )

    # Configuration du champ objective_type
    objective_type = forms.ChoiceField(
        label="Type d'objectif",
        choices=[
            ('max', 'Maximisation'),
            ('min', 'Minimisation')
        ],
        widget=forms.RadioSelect,
        initial='max',  # Valeur par défaut
        required=True,  # Champ obligatoire
    )


    class Meta:
        model = Problem
        # Listez les champs du formulaire. Excluez num_variables.
        fields = ['nom', 'description', 'objective_type', 'objective_equation_str', 'constraints_equation_str']
        # Vous devrez peut-être définir des widgets ou d'autres options ici si nécessaire
        widgets = {
            'objective_type': forms.RadioSelect(
                attrs={'class': 'focus:ring-primary-500 h-4 w-4 text-primary-600 border-gray-300'},
                choices=Problem.OBJECTIVE_CHOICES
            ),
        }

    def clean_objective_type(self):
        objective_type = self.cleaned_data.get('objective_type')
        if not objective_type:
            raise forms.ValidationError("Veuillez sélectionner un type d'objectif.")
        return objective_type
