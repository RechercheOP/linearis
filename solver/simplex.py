# solver/simplex.py

import numpy as np
import traceback # Importez traceback pour les erreurs détaillées

# Définition des constantes pour les sens de contraintes
SENSE_LE = '<='
SENSE_GE = '>='
SENSE_EQ = '='

# Constante pour indiquer un type de problème non supporté
STATUS_UNSUPPORTED = 'unsupported'

class SimplexSolver:
    def __init__(self, objective_type, objective_coefficients, constraints, verbose=False):
        self.objective_type = objective_type.lower() # 'max' ou 'min'
        self.c = np.array(objective_coefficients, dtype=float) # Coefficients fonction objectif
        # Cloner les contraintes pour ne pas modifier les données originales passées à l'instance
        self.constraints_data = [c.copy() for c in constraints]
        self.num_original_variables = len(objective_coefficients)
        self.num_original_constraints = len(constraints)
        self.verbose = verbose # Affichage verbeux des étapes
        self.tableaus = [] # Liste pour stocker les tableaux pour l'affichage pas à pas

        # Attributs de résultat (initialisés après solve)
        self.status = None # 'optimal', 'unbounded', 'infeasible', 'unsupported', 'error'
        self.solution = None # Solution pour les variables originales (ndarray ou None)
        self.optimal_value = None # Valeur optimale de la fonction objectif originale (float ou None)

        # Noms des variables (définis lors de la construction du tableau)
        self.variable_names = None


    def solve(self):
        """
        Résout le problème de Programmation Linéaire.
        Gère Max (<=) directement et Min (>=) via le dual.
        Signale les problèmes non supportés.
        """
        # Réinitialiser les résultats et tableaux pour un nouvel appel à solve()
        self.tableaus = []
        self.status = None
        self.solution = None
        self.optimal_value = None
        self.variable_names = None # S'assurer que les noms sont générés par _build_initial_tableau ou dual

        try:
            # --- Étape 0: Vérifier le type de problème et rediriger ou signaler non supporté ---
            # Cloner à nouveau les données pour les modifications internes comme les RHS négatifs
            # Cette copie dans __init__ et une autre ici assurent que chaque appel à solve()
            # part des données originales sans l'affecter.
            current_constraints_data = [c.copy() for c in self.constraints_data]


            if self.objective_type == 'min':
                # Pour la minimisation, toutes les contraintes doivent être >=
                if any(c.get('sense') != SENSE_GE for c in current_constraints_data):
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="L'outil ne gère que les problèmes de Minimisation avec uniquement des contraintes '>=' pour le moment.")
                # Vérifier les RHS négatifs pour Min(>=)
                if any(c.get('rhs', 0) < -1e-9 for c in current_constraints_data): # Utiliser .get() pour plus de robustesse
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="Un problème Min avec contraintes '>=' ne peut pas avoir de second membre négatif dans cette version.")


                # Si c'est un Min(>=) valide, construire le dual et le résoudre
                return self._solve_via_dual()


            elif self.objective_type == 'max':
                 # Pour la maximisation, toutes les contraintes doivent être <=
                 if any(c.get('sense') != SENSE_LE for c in current_constraints_data):
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="L'outil ne gère que les problèmes de Maximisation avec uniquement des contraintes '<=' pour le moment.")

                 # Vérifier les RHS négatifs pour Max(<=)
                 if any(c.get('rhs', 0) < -1e-9 for c in current_constraints_data): # Utiliser .get() pour plus de robustesse
                     # Pour Max(<=), un RHS négatif rend le problème infaisable directement
                     self.status = 'infeasible'
                     return self._build_result_dict(error="Un problème Max avec contraintes '<=' ne peut pas avoir de second membre négatif.")


                 # Si c'est un Max(<=) valide, continuer avec la résolution primale directe
                 return self._solve_primal_max_le() # Résoudre les Max(<=) directement

            else:
                self.status = STATUS_UNSUPPORTED
                return self._build_result_dict(error=f"Type d'objectif non supporté : {self.objective_type}. Seuls 'max' et 'min' sont acceptés.")

        except NotImplementedError as e:
            self.status = STATUS_UNSUPPORTED
            return self._build_result_dict(error=f"Fonctionnalité non implémentée : {e}. Ce type de problème n'est pas encore géré.")
        except ValueError as e:
             self.status = 'error'
             # Capturer les ValueErrors qui peuvent venir de la construction du tableau ou des pivots
             return self._build_result_dict(error=f"Erreur lors du traitement ou de la résolution de l'algorithme : {e}")
        except Exception as e:
             # Gérer d'autres erreurs potentielles lors de l'exécution de l'algorithme
             self.status = 'error'
             # Inclure la traceback complète de l'erreur inattendue peut être utile pour le débogage interne
             print(f"Erreur inattendue dans solve(): {e}\n{traceback.format_exc()}") # Afficher dans la console pour debug
             return self._build_result_dict(error=f"Une erreur inattendue est survenue lors de la résolution : {e}")


    def _build_result_dict(self, error=None):
        """
        Construit le dictionnaire de résultat standard.
        Convertit les tableaux NumPy en listes pour la sérialisation JSON.
        """
        # self.tableaus est supposé contenir une liste de dictionnaires { 'tableau': ndarray, 'basis_vars': list, 'variable_names': list }
        serializable_tableaus = []
        for t_info in self.tableaus:
             # Vérifier que t_info est un dictionnaire et a bien la clé 'tableau' qui est un ndarray
             if isinstance(t_info, dict) and 'tableau' in t_info and isinstance(t_info['tableau'], np.ndarray):
                  serializable_tableaus.append({
                       'tableau': t_info['tableau'].tolist(), # Convertir ndarray en liste
                       'basis_vars': t_info.get('basis_vars'), # Utiliser .get() au cas où, bien que cela ne devrait pas être None
                       'variable_names': t_info.get('variable_names') # Utiliser .get() au cas où, bien que cela ne devrait pas être None
                  })
             else:
                  # Si ce n'est pas le format dictionnaire attendu, c'est un problème.
                  # Afficher un avertissement plus clair et ne pas inclure l'élément mal formé.
                  print(f"Warning: Skipping unprocessable item in self.tableaus during serialization. Format: {type(t_info)}. Content Sample: {str(t_info)[:100]}")
                  pass # Ignorer l'élément non conforme pour la sortie JSON


        return {
            'status': self.status,
            # S'assurer que la solution est une liste ou None pour la sérialisation JSON
            'solution': self.solution.tolist() if isinstance(self.solution, np.ndarray) else self.solution,
            # S'assurer que la valeur optimale est un float ou None
            'optimal_value': float(self.optimal_value) if isinstance(self.optimal_value, (int, float, np.number)) else self.optimal_value,
            'tableaus': serializable_tableaus,
            # Les noms finaux des variables du tableau principal (primal ou dual)
            'variable_names': self.variable_names,
            'error': error,
            'unsupported_message': "Ce type de problème n'est pas encore géré par l'application. Nous travaillons à étendre nos capacités !" if self.status == STATUS_UNSUPPORTED else None
        }


    def _solve_primal_max_le(self):
        """
        Résout un problème de Maximisation avec uniquement des contraintes <=
        en utilisant l'algorithme du Simplexe primal direct.
        On assume ici que les RHS sont >= 0 (vérifié dans solve()).
        """
        # --- Étape 1.1: Construire le tableau initial pour Max(<=) avec RHS >= 0 ---
        # On ajoute seulement des variables d'écart.
        # _build_initial_tableau est implémentée ci-dessous pour ce cas strict.
        # Elle gérera la construction du tableau et la nomination des variables.

        # Utiliser la méthode _build_initial_tableau adaptée au périmètre
        # Elle retourne le tableau, les indices de base et les indices des variables de décision (0 à num_original_variables-1)
        tableau, basis_vars, decision_vars_indices_primal = self._build_initial_tableau()

        # Enregistrer le tableau initial using _record_tableau
        # self.variable_names est défini DANS _build_initial_tableau
        self._record_tableau({'tableau': tableau.copy(), 'basis_vars': basis_vars.copy(), 'variable_names': self.variable_names}, 0)


        # --- Étape 2: Itérations du Simplexe ---
        current_tableau = tableau.copy() # Travailler sur une copie, la première copie a déjà été enregistrée

        max_iterations = 100 # Limite d'itérations pour éviter les boucles infinies (dégénérescence non gérée)
        iteration = 0

        while iteration < max_iterations:
            if self._check_optimality(current_tableau):
                self.status = 'optimal'
                # Extraire la solution pour les variables originales (x1, x2, ...)
                # _extract_solution utilise self.num_original_variables de l'instance courante (primal)
                self.solution, self.optimal_value = self._extract_solution(current_tableau, basis_vars)
                return self._build_result_dict() # Sortie optimale

            pivot_col = self._choose_pivot_column(current_tableau)

            # Si _choose_pivot_column retourne None ALORS QUE _check_optimality est False,
            # c'est une situation inattendue. Dans un solveur complet, cela pourrait indiquer
            # un problème d'implémentation ou une erreur numérique.
            # Pour notre périmètre Max(<=) avec RHS>=0, le cas non borné est détecté dans _choose_pivot_row
            # quand tous les éléments de la colonne pivot sont <= 0.
            if pivot_col is None:
                 # Ce cas ne devrait pas arriver si _check_optimality est False, mais sécurité.
                 # Peut-être un problème d'arrondi très près de zéro.
                 print("Warning: _choose_pivot_column returned None, but _check_optimality was False.")
                 self.status = 'error' # Indiquer une erreur interne
                 return self._build_result_dict(error="Incohérence dans le choix du pivot.")


            pivot_row = self._choose_pivot_row(current_tableau, pivot_col)

            if pivot_row is None:
                # Si aucune ligne pivot n'est trouvée (tous les éléments de la colonne pivot <= 0)
                self.status = 'unbounded'
                self.solution = None # Pas de solution finie
                self.optimal_value = None # Pas de valeur finie
                return self._build_result_dict() # Sortie non borné


            # Effectuer l'opération de pivot sur une copie du tableau
            current_tableau = self._perform_pivot_operations(current_tableau.copy(), pivot_row, pivot_col)

            # Mettre à jour la variable de base pour la ligne pivot
            basis_vars[pivot_row] = pivot_col

            iteration += 1
            # Enregistrer le tableau après les opérations de pivot
            self._record_tableau({'tableau': current_tableau.copy(), 'basis_vars': basis_vars.copy(), 'variable_names': self.variable_names}, iteration)


        # Si la boucle atteint la limite, on suspecte un problème (dégénérescence, cyclage)
        self.status = 'error' # Ou 'degenerate' si on gère la détection
        return self._build_result_dict(error="Limite d'itérations atteinte, possible problème de dégénérescence ou bug non géré.")


    def _solve_via_dual(self):
        """
        Résout un problème de Minimisation (>=) en transformant et résolvant son dual
        (Maximisation avec <=).
        On assume ici que toutes les contraintes primales sont >= et RHS >= 0
        (vérifié dans solve()).
        """
        # --- Étape Dual 1: Construire le Problème Dual ---
        # Primal (Min, >=) : Min c.x s.t. A.x >= b, x >= 0
        # Dual (Max, <=) : Max b.y s.t. A_transpose.y <= c, y >= 0

        A_primal_coeffs = []
        b_primal = [] # RHS du primal -> Coefficients objectif du dual
        c_primal = self.c # Coefficients objectif du primal -> RHS du dual

        # On a déjà vérifié dans solve() que toutes les contraintes sont >= et RHS >= 0.
        # Construire la matrice A du primal
        for constraint in self.constraints_data:
            # Utiliser .get() pour plus de robustesse au cas où une clé manquerait (bien que vérifié avant)
            A_primal_coeffs.append(constraint.get('coefficients', []))
            b_primal.append(constraint.get('rhs', 0)) # Collecter les RHS du primal pour le c_dual

        A_primal_matrix = np.array(A_primal_coeffs, dtype=float)

        A_dual_matrix = A_primal_matrix.T # Transposer la matrice A
        c_dual_coeffs = b_primal # Les RHS du primal deviennent les coeffs objectifs du dual
        b_dual_vector = c_primal # Les coeffs objectifs du primal deviennent les RHS du dual

        # Les contraintes du dual sont toutes de type <=
        dual_constraints_data = []
        num_primal_vars = self.num_original_variables # Nombre de contraintes duales
        # num_primal_constraints = self.num_original_constraints # Nombre de variables duales (pour le solveur dual)

        # Chaque ligne transposée de A_primal_matrix devient une contrainte du dual
        # (la ligne i de A_dual correspond à la contrainte i du dual)
        for i in range(num_primal_vars):
            dual_constraints_data.append({
                "coefficients": A_dual_matrix[i, :].tolist(), # Ligne i de A_dual devient coeffs
                "sense": SENSE_LE, # Toutes les contraintes du dual sont <=
                "rhs": b_dual_vector[i] # Coeff objectif i du primal devient RHS de contrainte i du dual
            })

        # --- Étape Dual 2: Résoudre le Problème Dual (qui est un Max avec <=) ---
        # On utilise une nouvelle instance du SimplexSolver, configurée pour la Maximisation.
        # On lui passe les données du problème dual.
        # Le solveur dual utilisera _solve_primal_max_le en interne.
        # Les "variables originales" pour le solveur dual sont les variables duales (y_j).
        # Le nombre de variables originales pour le solveur dual est le nombre de contraintes primales.
        num_dual_original_vars = self.num_original_constraints
        # Le nombre de contraintes originales pour l'instance dual_solver est le nombre de variables primales.
        num_dual_constraints = self.num_original_variables


        # Créer une instance du solveur dual
        dual_solver = SimplexSolver(
            objective_type='max',
            objective_coefficients=c_dual_coeffs, # Coeffs objectifs du dual
            constraints=dual_constraints_data, # Contraintes du dual
            verbose=self.verbose # Garder le mode verbeux si activé
        )
        # Assurer que l'instance du solveur dual a les bons nombres pour son contexte
        dual_solver.num_original_variables = num_dual_original_vars
        dual_solver.num_original_constraints = num_dual_constraints


        dual_result = dual_solver.solve() # Le solveur dual va exécuter _solve_primal_max_le sur le problème dual

        # --- Étape Dual 3: Interpréter les Résultats du Dual ---
        # Transférer les tableaux du solveur dual au solveur primal pour l'affichage
        # dual_result['tableaus'] est déjà une liste de dictionnaires { 'tableau': list, ... }
        # Nous devons les convertir en liste de dictionnaires { 'tableau': ndarray, ... }
        # pour le format interne du solveur primal si on veut utiliser _record_tableau.
        # Alternativement, on peut stocker la liste de dicts sérialisables directement
        # si _build_result_dict sait les gérer (ce qui est l'approche tentée maintenant).
        self.tableaus = dual_result['tableaus']


        self.optimal_value = dual_result['optimal_value'] # La valeur optimale est la même pour primal et dual
        self.status = dual_result['status'] # Le statut optimal/non borné/infaisable du dual est le statut du dual

        if dual_result['status'] == 'optimal':
            # Si le dual est optimal, le primal l'est aussi.
            # La solution optimale du problème PRIMAL se trouve dans la ligne Z du tableau FINAL du DUAL,
            # spécifiquement sous les colonnes des variables d'écart du DUAL.
            final_dual_tableau_info = dual_result['tableaus'][-1]
            # Le 'tableau' dans final_dual_tableau_info est déjà une liste de listes (car vient du _build_result_dict du solveur dual)
            final_dual_tableau_list = final_dual_tableau_info['tableau']
            final_dual_tableau = np.array(final_dual_tableau_list) # Convertir en ndarray pour les opérations numpy

            # Noms des variables dans le tableau final dual
            dual_variable_names_in_tableau = final_dual_tableau_info['variable_names']

            # Trouver les indices des variables d'écart dans le tableau FINAL du DUAL.
            # Les variables d'écart du dual sont celles nommées 'sX'.
            dual_slack_col_indices = [i for i, name in enumerate(dual_variable_names_in_tableau) if name.startswith('s')]


            # Les valeurs des variables originales du PRIMAL (x_i) sont les coûts réduits (ligne Z)
            # des variables d'écart du DUAL.
            # La ligne Z est la dernière ligne du tableau dual.
            primal_solution_values = final_dual_tableau[-1, dual_slack_col_indices]

            self.solution = primal_solution_values # C'est la solution pour les variables originales du PRIMAL (x1, x2, ...)
            # Les noms des variables de la solution sont ceux du primal original
            self.variable_names = [f"x{i+1}" for i in range(self.num_original_variables)]

            # Le statut est déjà 'optimal' du solveur dual

            return self._build_result_dict()

        elif dual_result['status'] == 'unbounded':
            # Si le DUAL (Max, <=) est non borné, le PRIMAL (Min, >=) est infaisable.
            self.status = 'infeasible'
            self.solution = None
            self.optimal_value = None
            return self._build_result_dict(error="Le problème primal est infaisable (son dual est non borné).")

        elif dual_result['status'] == 'infeasible':
             # Si le DUAL (Max, <=) est infaisable (ex: RHS négatif pour le dual), le PRIMAL (Min, >=) est non borné.
             # Notre solveur dual (Max/<=) devrait détecter l'infaisabilité si un RHS est négatif.
             self.status = 'unbounded'
             self.solution = None
             self.optimal_value = None
             return self._build_result_dict(error="Le problème primal est non borné (son dual est infaisable).")

        else:
            # Autre statut du solveur dual (ex: 'error', 'unsupported' si le dual avait des contraintes non supportées, ce qui ne devrait pas arriver ici)
            # Transférer le statut et l'erreur du solveur dual.
            self.status = dual_result['status']
            self.solution = None
            self.optimal_value = None
            # Inclure l'erreur du solveur dual dans le message d'erreur primal
            dual_error_message = dual_result.get('error', 'Erreur inconnue dans le solveur dual.')
            return self._build_result_dict(error=f"Une erreur est survenue lors de la résolution du problème dual : {dual_error_message}")


    # --- Méthodes utilitaires (adaptées si nécessaire pour le nouveau périmètre) ---

    # _build_initial_tableau n'est appelée QUE par _solve_primal_max_le (pour le moment)
    # et par le solveur dual dans _solve_via_dual. Elle ne doit donc gérer QUE les contraintes <= et RHS >= 0.
    def _build_initial_tableau(self):
         """
         Construit le tableau initial pour un problème Max avec uniquement des contraintes <= et RHS >= 0.
         (Utilisé par _solve_primal_max_le et par le solveur dual dans _solve_via_dual).
         Retourne un tableau NumPy.
         """
         # On assume ici que les vérifications des types de contraintes et des RHS négatifs
         # ont déjà été faites par la méthode solve() ou _solve_via_dual avant d'appeler cette méthode.
         # Si on arrive ici, self.constraints_data ne devrait contenir que des contraintes <= avec RHS >= 0.

         # Dans le contexte actuel (primal ou dual) :
         # self.num_original_variables est le nombre de variables originales DU PROBLEME ACTUEL
         # self.num_original_constraints est le nombre de contraintes originales DU PROBLEME ACTUEL

         num_vars_in_this_problem = self.num_original_variables
         num_constraints_in_this_problem = self.num_original_constraints


         # Vérifier rapidement le format des contraintes au cas où (sécurité interne)
         if any(c.get('sense') != SENSE_LE or c.get('rhs') is None or c.get('coefficients') is None for c in self.constraints_data):
             print("Internal Error: _build_initial_tableau received invalid constraint data format or unsupported sense/RHS.")
             # Tenter de continuer, mais le résultat pourrait être incorrect
             # Ou lever une erreur fatale: raise ValueError(...)

         if any(len(c.get('coefficients', [])) != num_vars_in_this_problem for c in self.constraints_data):
              print(f"Internal Error: Coefficient list length mismatch in _build_initial_tableau. Expected {num_vars_in_this_problem}, got different.")
              # Tenter de continuer, mais le résultat pourrait être incorrect
              # Ou lever une erreur fatale: raise ValueError(...)


         num_slack = num_constraints_in_this_problem # Une variable d'écart par contrainte <=

         num_total_vars_in_tableau = num_vars_in_this_problem + num_slack

         # Tableau: (nombre de contraintes + 1) x (nombre total de variables + 1)
         tableau = np.zeros((num_constraints_in_this_problem + 1, num_total_vars_in_tableau + 1), dtype=float)

         basis_vars = [] # Indices des variables de base (initialement les variables d'écart)
         slack_col_offset = num_vars_in_this_problem
         current_slack = 0

         # Remplir les lignes de contraintes
         for i, constraint in enumerate(self.constraints_data):
             # Coefficients des variables originales du problème actuel (primal ou dual)
             coeffs = constraint.get('coefficients', [0.0] * num_vars_in_this_problem) # Default à 0 si manquants
             tableau[i, :num_vars_in_this_problem] = coeffs[:num_vars_in_this_problem] # S'assurer de ne prendre que le bon nombre


             # Coefficient +1 pour la variable d'écart de cette contrainte
             if current_slack < num_slack: # Sécurité pour ne pas dépasser la taille des variables d'écart
                  tableau[i, slack_col_offset + current_slack] = 1.0
                  # La variable d'écart est la variable de base pour cette ligne
                  basis_vars.append(slack_col_offset + current_slack)
                  current_slack += 1
             else:
                  # Erreur interne : plus de contraintes <= que de variables d'écart allouées
                  print("Internal Error: Slack variable allocation mismatch in _build_initial_tableau.")
                  # Tenter de continuer, mais l'état est probablement incorrect
                  pass


             # Second membre (RHS)
             tableau[i, -1] = constraint.get('rhs', 0.0)


         # Ligne de la fonction objectif (Z)
         # Coefficients initiaux = -c pour les variables originales du problème actuel, 0 pour les variables d'écart
         # La ligne Z est la dernière ligne
         c_coeffs = self.c[:num_vars_in_this_problem] # S'assurer de ne prendre que le bon nombre
         tableau[num_constraints_in_this_problem, :num_vars_in_this_problem] = -c_coeffs
         # Les 0 pour les variables d'écart et le 0 final pour le RHS sont déjà là.

         # Générer les noms des variables pour ce tableau (variables originales + écarts)
         # Utiliser le nombre de variables originales *du contexte actuel*
         original_prefix = 'y' if self.objective_type == 'min' else 'x' # Objective type de l'instance actuelle
         original_var_names = [f"{original_prefix}{i+1}" for i in range(num_vars_in_this_problem)] # Variables originales du contexte actuel
         slack_var_names = [f"s{i+1}" for i in range(num_slack)]
         self.variable_names = original_var_names + slack_var_names


         # Le tableau est prêt pour les itérations du Simplexe primal
         # Retourne le tableau NumPy, les indices des variables de base, et les indices des variables de décision originales (du contexte actuel)
         decision_vars_indices = list(range(num_vars_in_this_problem))

         return tableau, basis_vars, decision_vars_indices

    # Note: _generate_variable_names est appelée à la fin de _build_initial_tableau
    # _record_tableau enregistre le tableau et les indices de base (utiles pour l'affichage)
    def _record_tableau(self, tableau_info, iteration):
         """ Enregistre les informations d'un tableau pour l'historique et l'affichage verbeux. """
         # tableau_info est un dictionnaire attendu avec 'tableau' (ndarray), 'basis_vars' (list), 'variable_names' (list)
         # Cloner les objets pour s'assurer que les états sont bien capturés à cette itération
         cloned_info = {
             'tableau': tableau_info['tableau'].copy(), # Doit être un ndarray
             'basis_vars': tableau_info['basis_vars'][:] if tableau_info.get('basis_vars') is not None else None, # Copie de la liste
             'variable_names': tableau_info['variable_names'][:] if tableau_info.get('variable_names') is not None else None # Copie de la liste des noms
         }
         self.tableaus.append(cloned_info)
         if self.verbose:
              # S'assurer que print_tableau utilise les données clonées enregistrées
              self.print_tableau(cloned_info, iteration)


    # Méthode utilitaire pour imprimer un tableau (utilise les noms de variables stockés)
    def print_tableau(self, tableau_info, iteration=None):
        """ Affiche un tableau du Simplexe dans la console. """
        tableau = tableau_info['tableau'] # Doit être un ndarray
        basis_vars = tableau_info.get('basis_vars') # Peut être None si non défini/transféré
        var_names = tableau_info.get('variable_names') # Peut être None

        if tableau is None:
             print(f"\n--- Iteration {iteration} ---")
             print("Tableau data is missing or not in the expected format.")
             return

        if iteration is not None:
            print(f"\n--- Iteration {iteration} ---")


        # Utiliser les noms stockés ou générer des placeholders si manquants
        if var_names is None:
             num_vars = tableau.shape[1] - 1
             var_names = [f"v{i+1}" for i in range(num_vars)]
             print("Warning: Variable names missing, using placeholders.")

        # Calculer les noms des variables de base
        basic_var_names = []
        if basis_vars is not None and var_names is not None:
             try:
                  basic_var_names = [var_names[idx] for idx in basis_vars]
             except IndexError:
                  print("Warning: Index error when getting basic variable names. Basis indices or var names might be wrong.")
                  basic_var_names = [f"Base_{i}" for i in range(len(basis_vars))] # Fallback

        # En-tête : Variables de base, Noms de toutes les variables, RHS
        header = ['Base'] + var_names + ['RHS']
        # Déterminer la largeur maximale pour chaque colonne pour un alignement propre
        # Largeurs min par défaut
        col_widths = [max(len(name) for name in basic_var_names + ['Base'])] # Largeur pour 'Base'


        # Initialiser les largeurs pour les colonnes de variables et RHS
        col_widths += [max(len(name), 6) for name in var_names] # Largeur pour variables
        col_widths.append(max(len('RHS'), 6)) # Largeur pour RHS

        # Ajuster les largeurs réelles en fonction des valeurs du tableau
        num_rows_tableau, num_cols_tableau = tableau.shape
        for r in range(num_rows_tableau):
            for j in range(num_cols_tableau):
                # L'indice j parcourt les colonnes des variables et le RHS
                # Les colonnes des variables sont de 0 à len(var_names) - 1
                # La colonne RHS est len(var_names)
                col_idx_in_widths = j + 1 # +1 car col_widths[0] est pour 'Base'

                str_val = f"{tableau[r, j]:.2f}"
                if len(str_val) > col_widths[col_idx_in_widths]:
                      col_widths[col_idx_in_widths] = len(str_val)


        # Imprimer l'en-tête formatée
        formatted_header = [header[0].ljust(col_widths[0])] + \
                           [header[j+1].ljust(col_widths[j+1]) for j in range(len(var_names))] + \
                           [header[-1].ljust(col_widths[-1])]
        print(" ".join(formatted_header))


        # Imprimer les lignes du tableau formatées (sauf la dernière ligne Z)
        num_constraint_rows = num_rows_tableau - 1
        for i in range(num_constraint_rows):
            base_var = basic_var_names[i] if i < len(basic_var_names) else f"Base_{i}" # Fallback pour nom de base
            formatted_row = [base_var.ljust(col_widths[0])]
            for j in range(num_cols_tableau):
                 col_idx_in_widths = j + 1
                 formatted_row.append(f"{tableau[i, j]:.2f}".ljust(col_widths[col_idx_in_widths]))
            print(" ".join(formatted_row))

        # Imprimer la ligne Z formatée (dernière ligne)
        formatted_z_row = ['Z'.ljust(col_widths[0])]
        for j in range(num_cols_tableau):
             col_idx_in_widths = j + 1
             formatted_z_row.append(f"{tableau[num_constraint_rows, j]:.2f}".ljust(col_widths[col_idx_in_widths]))
        print(" ".join(formatted_z_row))


    # _check_optimality vérifie la dernière ligne pour >= 0 (correct pour Max)
    def _check_optimality(self, tableau):
        last_row = tableau[-1, :-1]
        # Optimal si tous les coûts réduits sont >= 0 (à tolérance près)
        # Exclure les coûts réduits des variables artificielles si on utilisait la Grande M
        # Dans notre périmètre, il n'y a pas d'artificielles dans le tableau principal.
        return np.all(last_row >= -1e-9)


    # _choose_pivot_column cherche le plus négatif (correct pour Max)
    def _choose_pivot_column(self, tableau):
        last_row = tableau[-1, :-1]
        # Trouver l'indice de la colonne avec le coût réduit le plus négatif
        j = np.argmin(last_row)
        # Si le coût réduit le plus négatif est >= 0 (à tolérance près), c'est optimal.
        # Sinon, retourner l'indice de la colonne pivot.
        # Utiliser une tolérance pour la comparaison au cas où c'est très proche de zéro.
        if last_row[j] < -1e-9:
             return j
        else:
             # Si le min est >= 0, c'est optimal.
             return None


    # _choose_pivot_row effectue le test du ratio minimum et détecte non borné (correct pour Max)
    def _choose_pivot_row(self, tableau, pivot_col):
        rhs = tableau[:-1, -1] # Second membres (dernière colonne, sauf ligne Z)
        col = tableau[:-1, pivot_col] # Colonne pivot (sauf ligne Z)
        ratios = []
        for i in range(len(rhs)):
            # Test du ratio : RHS / élément colonne pivot, seulement si élément colonne pivot > 0
            # Utiliser une petite tolérance pour > 0
            if col[i] > 1e-9:
                ratio = rhs[i] / col[i]
                 # Le ratio doit être non négatif (RHS est déjà >= 0 en forme standard)
                # Le test du ratio minimum ne considère que les ratios >= 0
                # Si le ratio est négatif (RHS < 0 et col[i] > 0), on l'ignore pour le min ratio test.
                # Mais comme on gère les RHS négatifs en amont pour les problèmes gérés,
                # tous les RHS dans le tableau devraient être >= 0.
                if ratio >= -1e-9: # Le ratio doit être positif ou nul
                    ratios.append((ratio, i))
                # else: ratio négatif ou col[i] <= 0, ignoré pour le test du ratio minimum


        # Si aucune ligne n'a un élément > 0 dans la colonne pivot, le problème est non borné
        # ET la colonne pivot a un coût réduit négatif (vérifié avant par _choose_pivot_column)
        # Notre _choose_pivot_column s'assure déjà que coût réduit < 0 (si pivot_col is not None).
        # Donc si ratios est vide ici, c'est non borné.
        if not ratios: # La liste est vide
            return None # Indique non borné

        # Trouver l'indice de la ligne avec le ratio minimum non négatif.
        # Utiliser une petite tolérance pour les comparaisons de ratios afin de gérer la dégénérescence simple.
        min_ratio = min(ratios)[0]
        # Filtrer les lignes avec le ratio minimum (à tolérance près)
        min_ratio_indices = [i for ratio, i in ratios if abs(ratio - min_ratio) < 1e-9]

        # Pour gérer la dégénérescence, on peut choisir la ligne avec le plus petit indice parmi les minima (règle de Bland partielle)
        pivot_row_index = min(min_ratio_indices) # Prendre le plus petit indice de ligne en cas d'égalité

        return pivot_row_index


    # _perform_pivot_operations effectue les opérations sur les lignes (standard)
    def _perform_pivot_operations(self, tableau, pivot_row, pivot_col):
        new_tableau = tableau.copy() # Travailler sur une copie
        pivot_elem = new_tableau[pivot_row, pivot_col]

        # Sécurité : s'assurer que l'élément pivot n'est pas proche de zéro
        # Ceci ne devrait pas arriver si _choose_pivot_row fonctionne correctement,
        # mais c'est une protection contre des erreurs potentielles.
        if abs(pivot_elem) < 1e-9:
             raise ValueError("Pivot element is zero or close to zero. Algorithm error.")


        # Diviser la ligne pivot par l'élément pivot pour rendre l'élément pivot égal à 1
        new_tableau[pivot_row, :] /= pivot_elem

        # Pour toutes les autres lignes, soustraire un multiple de la ligne pivot
        # pour rendre l'élément dans la colonne pivot égal à 0
        num_rows = new_tableau.shape[0] # Nombre de lignes (contraintes + 1)
        for i in range(num_rows):
            if i != pivot_row:
                factor = new_tableau[i, pivot_col]
                new_tableau[i, :] -= factor * new_tableau[pivot_row, :]

        return new_tableau


    # _extract_solution extrait la solution pour les variables originales.
    # Elle est appelée par _solve_primal_max_le et _solve_via_dual (qui interprète le résultat dual).
    # Elle extrait la solution pour les variables de DÉCISION originales *du problème actuellement résolu* (primal ou dual)
    # L'interprétation pour passer du dual au primal se fait dans _solve_via_dual.
    def _extract_solution(self, tableau, basis_vars):
         """
         Extrait la solution pour les variables de décision originales du problème
         actuellement résolu (primal Max/<= ou dual Max/<=) et la valeur optimale.
         """
         # Le nombre de variables de décision originales *du problème actuellement résolu*.
         # Si on est dans le solveur primal (Max/<=), c'est self.num_original_variables (du primal).
         # Si on est dans le solveur dual (appelé dans _solve_via_dual), c'est le nombre de contraintes du primal = self.num_original_constraints.
         # L'instance du solveur dual aura self.num_original_variables = self.num_original_constraints (du primal).
         # Donc on utilise self.num_original_variables de L'INSTANCE COURANTE.

         num_vars_to_extract = self.num_original_variables # Nombre de variables originales du contexte actuel

         solution = np.zeros(num_vars_to_extract) # Initialiser avec des zéros pour les variables originales du contexte actuel

         # Parcourir les variables de base actuelles (leur indice dans le tableau complet)
         # et voir si elles correspondent aux indices des variables originales du contexte actuel (0 à num_vars_to_extract - 1).
         for i, var_idx in enumerate(basis_vars): # i est l'indice de la ligne dans le tableau (0 à num_constraints-1)
             # var_idx est l'indice de la variable de base dans le tableau complet (0 à num_total_vars - 1)

             # Si l'indice de la variable de base (var_idx) est l'indice d'une variable originale (0 à num_vars_to_extract - 1)
             if var_idx < num_vars_to_extract:
                 # Alors la valeur de la variable originale (var_idx) est le second membre de cette ligne (i)
                 solution[var_idx] = tableau[i, -1]
             # else: si var_idx >= num_vars_to_extract, c'est une variable supplémentaire (écart, excédent, artificielle).
             # Leur valeur est soit 0 (si non en base), soit tableau[i, -1] (si en base), mais on n'extrait que les variables originales ici.


         # La valeur optimale est la dernière valeur de la dernière ligne du tableau actuel.
         optimal_value = tableau[-1, -1]

         # Pour le solveur dual, cette valeur optimale sera celle du dual.
         # _solve_via_dual s'assurera que c'est aussi la bonne valeur pour le primal
         # et gérera l'interprétation de la solution primale.

         return solution, optimal_value

    # Note: _generate_variable_names est appelée à la fin de _build_initial_tableau
    def _generate_variable_names(self, num_slack):
        """ Génère les noms des variables pour l'affichage du tableau pour Max(<=). """
        # num_artificial est 0 dans ce périmètre pour le solveur principal
        num_artificial = 0
        # Déterminer le préfixe (x pour primal Max, y pour dual Max)
        original_prefix = 'y' if self.objective_type == 'min' else 'x' # Objective type de l'instance actuelle

        names = [f"{original_prefix}{i+1}" for i in range(self.num_original_variables)] # Variables originales du contexte actuel
        names += [f"s{i+1}" for i in range(num_slack)] # Variables d'écart
        # Pas de variables artificielles dans ce périmètre
        # if num_artificial > 0: names += [f"a{i+1}" for i in range(num_artificial)]
        return names