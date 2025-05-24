# problems/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
import json
import re
from django.http import JsonResponse
from .services import GeminiService
from django.utils import timezone

from .forms import ManualProblemForm
from .models import Problem, ImportedProblem
from problems.simplex import SimplexSolver, STATUS_UNSUPPORTED

@login_required
def create_manual_problem(request):
    if request.method == 'POST':
        form = ManualProblemForm(request.POST)
        if form.is_valid():
            try:
                # Parse les équations
                parsed_data = parse_problem_equations(
                    form.cleaned_data['objective_equation_str'],
                    form.cleaned_data['constraints_equation_str']
                )
                
                # Crée le problème avec les données parsées
                problem = Problem.objects.create(
                    user=request.user,
                    nom=form.cleaned_data['nom'],
                    objective_type=form.cleaned_data['objective_type'],
                    objective_equation_str=form.cleaned_data['objective_equation_str'],
                    constraints_equation_str=form.cleaned_data['constraints_equation_str'],
                    num_variables=parsed_data['num_variables'],
                    variable_names=parsed_data['variable_names'],
                    objective_coefficients=parsed_data['objective_coefficients'],
                    constraints=parsed_data['constraints']
                )
                
                print("\n")
                print(problem.constraints_equation_str)
                print("\n")
                
                messages.success(request, 'Problème créé avec succès!')
                return redirect('problem_detail', pk=problem.pk)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")
                print(f"Erreur détaillée : {str(e)}")  # Log pour débogage
        else:
            messages.error(request, "Le formulaire contient des erreurs")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans {field}: {error}")
            print("Erreurs du formulaire:", form.errors)
    else:
        form = ManualProblemForm()

    return render(request, 'problems/create_manual.html', {'form': form})

def parse_problem_equations(objective_str, constraints_str):
    # Extraction des variables et coefficients
    variables = set()
    objective_terms = []
    constraints_list = []
    
    # 1. Parse la fonction objectif
    objective_terms = re.findall(r'([+-]?\s*\d*\.?\d*)\s*([a-zA-Z_][a-zA-Z0-9_]*)', objective_str)
    objective_coefficients = []
    
    for coeff_str, var_name in objective_terms:
        # Gestion des coefficients
        coeff_str = coeff_str.strip()
        if not coeff_str or coeff_str == '+':
            coeff = 1.0
        elif coeff_str == '-':
            coeff = -1.0
        else:
            coeff = float(coeff_str.replace(' ', ''))
        
        variables.add(var_name)
        objective_coefficients.append(coeff)
    
    # 2. Parse les contraintes
    constraints = []
    for line in constraints_str.split('\n'):
        line = line.strip()
        if line:
            # Sépare le côté gauche et droit
            match = re.match(r'^(.*?)\s*([<>=]=?)\s*([+-]?\s*\d*\.?\d+)$', line)
            if not match:
                raise ValueError(f"Format de contrainte invalide : {line}")
            
            lhs, sense, rhs = match.groups()
            rhs = float(rhs.replace(' ', ''))
            
            # Parse les termes du côté gauche
            terms = re.findall(r'([+-]?\s*\d*\.?\d*)\s*([a-zA-Z_][a-zA-Z0-9_]*)', lhs)
            constraint_coeffs = []
            
            for coeff_str, var_name in terms:
                coeff_str = coeff_str.strip()
                if not coeff_str or coeff_str == '+':
                    coeff = 1.0
                elif coeff_str == '-':
                    coeff = -1.0
                else:
                    coeff = float(coeff_str.replace(' ', ''))
                
                variables.add(var_name)
                constraint_coeffs.append(coeff)
            
            constraints.append({
                'coefficients': constraint_coeffs,
                'sense': sense,
                'rhs': rhs
            })
    
    # Crée un mapping des variables pour avoir un ordre cohérent
    variable_names = sorted(variables)
    num_variables = len(variable_names)
    
    # Convertit les coefficients en listes ordonnées
    final_objective = [0.0] * num_variables
    for var_name, coeff in zip(variable_names, objective_coefficients):
        final_objective[variable_names.index(var_name)] = coeff
    
    final_constraints = []
    for constraint in constraints:
        coeffs = [0.0] * num_variables
        for var_name, coeff in zip(variable_names, constraint['coefficients']):
            coeffs[variable_names.index(var_name)] = coeff
        
        final_constraints.append({
            'coefficients': coeffs,
            'sense': constraint['sense'],
            'rhs': constraint['rhs']
        })
    
    return {
        'num_variables': num_variables,
        'variable_names': variable_names,
        'objective_coefficients': final_objective,
        'constraints': final_constraints
    }

@login_required
def problem_detail(request, pk):
    problem = get_object_or_404(Problem, pk=pk, user=request.user)
    context = {
        'problem': problem,
    }
    return render(request, 'problems/problem_detail.html', context)

@login_required
def solve_problem(request, pk):
    problem = get_object_or_404(Problem, pk=pk, user=request.user)
    
    try:
        # Préparation des données pour le solveur
        solver = SimplexSolver(
            objective_type=problem.objective_type,
            objective_coefficients=problem.objective_coefficients,
            constraints=problem.constraints
        )
        
        # Résolution du problème
        result = solver.solve()
        
        print("\nRésultat du solveur:")
        print(result)
        
        # Mise à jour du problème avec les résultats
        problem.status = result['status']
        if result['status'] == 'optimal':
            problem.optimal_value = result['optimal_value']
            problem.solution_variables = result['solution']
        
        # Conversion des tableaux en format JSON-sérialisable
        if 'tableaus' in result:
            tableaus_json = []
            for tableau in result['tableaus']:
                print("\nTableau avant conversion:")
                print(tableau)
                
                tableau_json = {
                    'tableau': [row.tolist() if hasattr(row, 'tolist') else row for row in tableau['tableau']],
                    'basis_vars': [int(x) if hasattr(x, 'item') else x for x in tableau['basis_vars']],  # Conversion des np.int64 en int
                    'variable_names': tableau['variable_names']
                }
                print("\nTableau après conversion:")
                print(tableau_json)
                tableaus_json.append(tableau_json)
            
            print("\nTableaus JSON final:")
            print(tableaus_json)
            problem.tableaus_history = tableaus_json
        
        problem.save()
        
        messages.success(request, 'Le problème a été résolu avec succès.')
        
    except Exception as e:
        print("\nErreur détaillée:")
        print(str(e))
        messages.error(request, f'Erreur lors de la résolution : {str(e)}')
    
    return redirect('problem_detail', pk=problem.pk)

import logging
logger = logging.getLogger(__name__)

@login_required
def import_problem(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        
        # Vérification du type de fichier
        allowed_types = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg']
        if file.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'error': 'Format de fichier non supporté'
            })
        
        try:
            # Création du problème importé
            problem = ImportedProblem.objects.create(
                user=request.user,
                file=file,
                nom=f"Problème importé - {file.name}",
                statusForImport='processing',
                processing_started_at=timezone.now()
            )
            
            # Traitement avec Gemini
            gemini_service = GeminiService()
            
            if file.content_type.startswith('image/'):
                result = gemini_service.process_image(file)
            else:
                result = gemini_service.process_pdf(file)
            
            print(result['objective_coefficients'])
            
            # Mise à jour du problème avec les résultats
            problem.objective_type = result['objective_type']
            problem.objective_coefficients = result['objective_coefficients']
            problem.constraints = result['constraints']
            
            problem.num_variables = len(result['objective_coefficients'])
            
            # Assurer la cohérence des longueurs de coefficients dans les contraintes
            for constraint in problem.constraints:
                if len(constraint['coefficients']) < problem.num_variables:
                    constraint['coefficients'].extend(
                        [0.0] * (problem.num_variables - len(constraint['coefficients'])))
                    
            problem.variable_names = [f"x{i+1}" for i in range(problem.num_variables)]
            
            if 'objective_function' in result: # Si Gemini renvoie la chaîne de l'objectif
                problem.objective_equation_str = result['objective_function']
            if 'constraints_equations' in result: # Si Gemini renvoie la liste des chaînes des contraintes
                problem.constraints_equation_str = "\n".join(result['constraints_equations'])
                
            problem.statusForImport = 'completed'
            problem.processing_completed_at = timezone.now()
            
            problem.save()
            
            return JsonResponse({
                'success': True,
                'problem_id': problem.id
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de l'importation : {str(e)}", exc_info=True)
            if problem:
                problem.statusForImport = 'failed'
                problem.error_message = str(e)
                problem.processing_completed_at = timezone.now() 
                problem.save()
            
            return JsonResponse({
                'success': False,
                'error': f"Erreur interne du serveur : {str(e)}" # Message d'erreur plus générique à l'utilisateur
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Méthode non autorisée ou fichier manquant'
    })