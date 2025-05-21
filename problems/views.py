# problems/views.py (Extrait de la fonction create_manual_problem)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
import json
import re # Importer le module re pour les expressions régulières

from .forms import ManualProblemForm
from .models import Problem

@login_required
def create_manual_problem(request):
    if request.method == 'POST':
        form = ManualProblemForm(request.POST)
        if form.is_valid():
            nom = form.cleaned_data['nom']
            description = form.cleaned_data['description']
            objective_type = form.cleaned_data['objective_type']
            # Récupérer les chaînes d'équations des nouveaux champs
            objective_equation_str = form.cleaned_data['objective_equation_str']
            constraints_equation_str = form.cleaned_data['constraints_equation_str']

            objective_coefficients = []
            parsed_constraints = []
            variable_names = [] # Liste pour stocker les noms de variables détectés (ex: ['x1', 'x2', 'y'])
            num_variables = 0 # Sera déduit

            try:
                # --- Étape de Parsing ---

                # 1. Première passe pour identifier TOUS les noms de variables uniques
                all_variable_names_set = set()

                # Regex pour trouver les noms de variables dans les expressions (ex: x1, y, Z3)
                # Ce regex peut nécessiter des ajustements selon les noms autorisés.
                # Ici, il cherche une lettre suivie de zéro ou plusieurs chiffres.
                variable_name_regex = r'[a-zA-Z]\d*'

                # Parser l'équation objective pour trouver les variables
                # On ignore le "Max" ou "Min" au début pour l'analyse des variables
                obj_expr_part = re.sub(r'^\s*(max|min)\s+', '', objective_equation_str, flags=re.IGNORECASE)
                # On ignore aussi potentiellement un signe égal et un nom (ex: Max Z = ...)
                obj_expr_part = re.sub(r'^\s*[a-zA-Z]\d*\s*=\s*', '', obj_expr_part, flags=re.IGNORECASE)

                var_matches_obj = re.findall(variable_name_regex, obj_expr_part)
                all_variable_names_set.update(var_matches_obj)

                # Parser chaque contrainte pour trouver les variables
                for line in constraints_equation_str.splitlines():
                    line = line.strip()
                    if not line: continue # Ignorer les lignes vides

                    # Diviser la ligne en partie gauche et partie droite par l'opérateur
                    operator_match = re.search(r'(<=|=|>=)', line)
                    if not operator_match:
                        raise ValueError(f"Opérateur de contrainte manquant ou incorrect dans : '{line}'")

                    # Split par l'opérateur trouvé
                    parts = re.split(r'(<=|=|>=)', line, 1) # Split en 3 parties maximum
                    if len(parts) != 3:
                         raise ValueError(f"Format de contrainte incorrect : '{line}'. Attendu : Partie_Gauche Opérateur Partie_Droite")

                    lhs_expr = parts[0].strip()
                    rhs_str = parts[2].strip()

                    # Trouver les variables dans la partie gauche (LHS)
                    var_matches_lhs = re.findall(variable_name_regex, lhs_expr)
                    all_variable_names_set.update(var_matches_lhs)

                    # Trouver les variables dans la partie droite (RHS) - devrait être rare mais possible
                    var_matches_rhs = re.findall(variable_name_regex, rhs_str)
                    if var_matches_rhs:
                         # Si des variables sont trouvées dans le RHS, c'est un format non standard
                         raise ValueError(f"Les variables ne sont pas autorisées dans la partie droite (RHS) des contraintes : '{line}'")


                # Déterminer les noms de variables finaux et leur nombre
                # Tri alphabétique pour un ordre consistant
                variable_names = sorted(list(all_variable_names_set))
                num_variables = len(variable_names)

                if num_variables == 0:
                     raise ValueError("Aucune variable valide détectée dans la fonction objectif ou les contraintes.")

                # --- Fonctions de Parsing d'Expression (simplifiées) ---
                # Ces fonctions prendront une expression (partie gauche de l'objectif ou d'une contrainte)
                # et retourneront la liste des coefficients correspondant à l'ordre de variable_names.

                def parse_expression_to_coefficients(expression_str, var_names):
                    """
                    Parse une expression comme "3x1 + 5x2 - y" et retourne une liste de coefficients
                    dans l'ordre spécifié par var_names (ex: si var_names=['x1', 'x2', 'y'], retourne [3.0, 5.0, -1.0]).
                    Gère les coefficients implicites (x -> 1x, -y -> -1y).
                    """
                    coeffs = [0.0] * len(var_names) # Initialiser tous les coefficients à 0
                    # Remplacer les signes pour faciliter le split et ajouter un signe + implicite au début si besoin
                    expression_str = expression_str.replace('-', '+-').replace(' ', '')
                    if not expression_str.startswith('+'):
                         expression_str = '+' + expression_str

                    # Split par les signes '+'
                    terms = expression_str.split('+')

                    for term in terms:
                         if not term: continue # Ignorer les chaînes vides résultant du split

                         # Chaque terme est maintenant quelque chose comme "3x1", "-5x2", "x1", "-y", "5".
                         # Gérer les termes qui sont juste des nombres si besoin (pas standard dans un LHS/objectif pur, mais sécurité)
                         if re.fullmatch(r'[+-]?\d*\.?\d+', term):
                              # C'est un terme constant, devrait être dans le RHS. Ignorons ici pour l'objectif/LHS.
                              # Une implémentation plus complète pourrait signaler une erreur ou l'ajouter au RHS.
                              continue

                         # Extraire le coefficient et le nom de la variable
                         match = re.match(r'([+-]?\s*\d*\.?\d*)([a-zA-Z]\d*)', term)
                         if not match:
                              # Peut-être un terme comme 'x1' ou '-y' sans coefficient explicite
                              match = re.match(r'([+-]?)([a-zA-Z]\d*)', term)
                              if match:
                                   sign_str, var_name = match.groups()
                                   coef = 1.0 if sign_str == '+' or not sign_str else -1.0 # Coefficient est +1 ou -1
                              else:
                                   # Terme non reconnu
                                   raise ValueError(f"Terme non reconnu dans l'expression : '{term}'")
                         else:
                              # Terme avec coefficient explicite
                              coef_str, var_name = match.groups()
                              # Convertir le coefficient, gérer le cas vide si c'était juste '+' ou '-' suivi de la variable
                              if not coef_str or coef_str in ['+', '-']: # Cas comme +x1 ou -x2
                                   coef = 1.0 if coef_str == '+' else -1.0
                              else:
                                   coef = float(coef_str)

                         try:
                             # Trouver l'indice de cette variable dans notre liste ordonnée
                             var_index = var_names.index(var_name)
                             # Ajouter le coefficient (utile si une variable apparaît plusieurs fois comme x1 + 2x1)
                             coeffs[var_index] += coef
                         except ValueError:
                             # Cette variable n'a pas été trouvée lors de la première passe. Incohérence interne.
                             raise ValueError(f"Variable '{var_name}' trouvée lors du parsing mais pas dans la liste globale des variables.")

                    return coeffs

                # --- Fin Fonctions de Parsing d'Expression ---


                # 2. Parser les coefficients de l'objectif en utilisant la liste ordonnée des variables
                # On utilise objective_expr qui a déjà été nettoyé du Max/Min et du Z=
                objective_coefficients = parse_expression_to_coefficients(obj_expr_part, variable_names)


                # 3. Parser chaque contrainte pour obtenir coefficients et RHS
                final_constraints_list = []
                for line in constraints_equation_str.splitlines():
                    line = line.strip()
                    if not line: continue

                    # Retrouver l'opérateur et les parties LHS/RHS
                    operator_match = re.search(r'(<=|=|>=)', line)
                    if not operator_match: # Déjà vérifié, mais double sécurité
                         raise ValueError(f"Opérateur de contrainte manquant ou incorrect dans : '{line}'")

                    sense = operator_match.group(1)
                    parts = re.split(r'(<=|=|>=)', line, 1)

                    lhs_expr = parts[0].strip()
                    rhs_str = parts[2].strip()

                    # Parser la partie gauche (LHS) en coefficients
                    constraint_coefficients = parse_expression_to_coefficients(lhs_expr, variable_names)

                    # Parser la partie droite (RHS) en nombre
                    try:
                        rhs = float(rhs_str)
                    except ValueError:
                         raise ValueError(f"Valeur du second membre (RHS) incorrecte : '{rhs_str}' dans la contrainte '{line}'")


                    final_constraints_list.append({
                        "coefficients": constraint_coefficients,
                        "sense": sense,
                        "rhs": rhs
                    })

                # --- Fin Étape de Parsing ---


                # --- Sauvegarde du Problème ---
                # Utiliser les données parsées, y compris num_variables déduit

                problem = Problem.objects.create(
                    user=request.user,
                    nom=nom,
                    description=description,
                    objective_type=objective_type, # Utilise toujours le type du champ radio
                    num_variables=num_variables, # Utilise le nombre de variables déduit
                    objective_coefficients=objective_coefficients,
                    constraints=final_constraints_list,
                )

                messages.success(request, 'Le problème a été sauvegardé avec succès !')
                # TODO: Rediriger vers la page de détail du problème (ou ailleurs)
                return redirect('home')
            
            except ValueError as e:
                # Capturer les erreurs spécifiques levées pendant le parsing
                messages.error(request, f"Erreur de format des données saisies : {e}")
            except Exception as e:
                 # Gérer d'autres erreurs inattendues pendant le processus
                 messages.error(request, f"Une erreur inattendue est survenue lors du traitement : {e}")
                 # Optionnel: log l'erreur pour le débogage interne
                 # import traceback
                 # print(f"Erreur inattendue : {e}\n{traceback.format_exc()}")


        else: # Méthode GET: Afficher le formulaire vide
            # Vous aurez besoin de créer ou adapter le formulaire pour les nouveaux champs
            form = ManualProblemForm()

        # Afficher le formulaire (vide pour GET, pré-rempli avec erreurs pour POST invalide/parsing échoué)
        # Le template devra utiliser les nouveaux noms de champs si vous les avez changés dans forms.py
        return render(request, 'problems/create_manual.html', {'form': form})
    else:
        # Cas GET : afficher le formulaire vide
        form = ManualProblemForm()
        return render(request, 'problems/create_manual.html', {'form': form})