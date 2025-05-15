from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
import json # Pour parser les strings JSON
from .forms import ManualProblemForm
from .models import Problem


@login_required # S'assure que seul un utilisateur connecté peut accéder à cette page
def create_manual_problem(request):
    if request.method == 'POST':
        form = ManualProblemForm(request.POST)
        if form.is_valid():
            # ---- Logique de Parsing des Strings en Structures Python ----
            # Cette partie est cruciale et doit gérer les erreurs de format !
            nom = form.cleaned_data['nom']
            description = form.cleaned_data['description']
            objective_type = form.cleaned_data['objective_type']
            num_variables = form.cleaned_data['num_variables']
            obj_coeffs_str = form.cleaned_data['objective_coefficients_str']
            constraints_str = form.cleaned_data['constraints_str']

            try:
                # Parsing des coefficients objectifs (ex: "3, 5, 0") -> [3.0, 5.0, 0.0]
                # On suppose que les coefficients sont séparés par des virgules
                objective_coefficients = [float(coef.strip()) for coef in obj_coeffs_str.split(',') if coef.strip()]
                if len(objective_coefficients) != num_variables:
                     raise ValueError("Nombre de coefficients objectif incorrect.")

                # Parsing des contraintes (ex: "1,1;<=;10\n2,0;>=;5")
                # On suppose une contrainte par ligne, coefficients séparés par virgule, séparés du sens et du rhs par un point-virgule
                parsed_constraints = []
                for line in constraints_str.splitlines():
                    line = line.strip()
                    if not line: continue # Sauter les lignes vides

                    parts = line.split(';')
                    if len(parts) != 3:
                        raise ValueError(f"Format de contrainte incorrect : '{line}'. Attendu : coefs;sens;rhs")

                    coefs_str, sense, rhs_str = parts
                    constraint_coefficients = [float(coef.strip()) for coef in coefs_str.split(',') if coef.strip()]
                    rhs = float(rhs_str.strip())
                    sense = sense.strip() # '<=', '>=', '='

                    # Validation simple du sens
                    if sense not in ['<=', '>=', '=']:
                        raise ValueError(f"Sens de contrainte invalide : '{sense}'. Attendu : <=, >= ou =")

                    if len(constraint_coefficients) != num_variables:
                         raise ValueError(f"Nombre de coefficients dans la contrainte '{line}' incorrect.")

                    parsed_constraints.append({
                        "coefficients": constraint_coefficients,
                        "sense": sense,
                        "rhs": rhs
                    })

                # ---- Sauvegarde du Problème ----
                problem = Problem.objects.create(
                    user=request.user, # L'utilisateur connecté
                    nom=nom,
                    description=description,
                    objective_type=objective_type,
                    num_variables=num_variables,
                    objective_coefficients=objective_coefficients, # JSONField gère l'enregistrement de la liste
                    constraints=parsed_constraints, # JSONField gère l'enregistrement de la liste de dicts
                )

                messages.success(request, 'Le problème a été sauvegardé avec succès !')
                # TODO: Rediriger vers la page de détail du problème
                return redirect('home') # Redirigeons vers l'accueil pour l'instant

            except ValueError as e:
                messages.error(request, f"Erreur lors du parsing des données : {e}")
            except Exception as e:
                 # Gérer d'autres erreurs potentielles
                 messages.error(request, f"Une erreur inattendue est survenue : {e}")


    else: # Méthode GET: Afficher le formulaire
        form = ManualProblemForm()

    # Afficher le formulaire (vide pour GET, avec erreurs pour POST invalide)
    return render(request, 'problems/create_manual.html', {'form': form})