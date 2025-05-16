# solver/simplex.py

import numpy as np
import traceback

SENSE_LE = '<='
SENSE_GE = '>='
SENSE_EQ = '='

STATUS_UNSUPPORTED = 'unsupported'

class SimplexSolver:
    def __init__(self, objective_type, objective_coefficients, constraints, verbose=False):
        self.objective_type = objective_type.lower()
        self.c = np.array(objective_coefficients, dtype=float)
        self.constraints_data = [c.copy() for c in constraints]
        self.num_original_variables = len(objective_coefficients)
        self.num_original_constraints = len(constraints)
        self.verbose = verbose
        self.tableaus = []

        self.status = None
        self.solution = None
        self.optimal_value = None
        self.variable_names = None

    def solve(self):
        self.tableaus = []
        self.status = None
        self.solution = None
        self.optimal_value = None
        self.variable_names = None

        try:
            current_constraints_data = [c.copy() for c in self.constraints_data]

            if self.objective_type == 'min':
                if any(c.get('sense') != SENSE_GE for c in current_constraints_data):
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="L'outil ne gère que les problèmes de Minimisation avec uniquement des contraintes '>=' pour le moment.")
                if any(c.get('rhs', 0) < -1e-9 for c in current_constraints_data):
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="Un problème Min avec contraintes '>=' ne peut pas avoir de second membre négatif dans cette version.")

                return self._solve_via_dual()

            elif self.objective_type == 'max':
                 if any(c.get('sense') != SENSE_LE for c in current_constraints_data):
                     self.status = STATUS_UNSUPPORTED
                     return self._build_result_dict(error="L'outil ne gère que les problèmes de Maximisation avec uniquement des contraintes '<=' pour le moment.")

                 if any(c.get('rhs', 0) < -1e-9 for c in current_constraints_data):
                     self.status = 'infeasible'
                     return self._build_result_dict(error="Un problème Max avec contraintes '<=' ne peut pas avoir de second membre négatif.")

                 return self._solve_primal_max_le()

            else:
                self.status = STATUS_UNSUPPORTED
                return self._build_result_dict(error=f"Type d'objectif non supporté : {self.objective_type}. Seuls 'max' et 'min' sont acceptés.")

        except NotImplementedError as e:
            self.status = STATUS_UNSUPPORTED
            return self._build_result_dict(error=f"Fonctionnalité non implémentée : {e}. Ce type de problème n'est pas encore géré.")
        except ValueError as e:
             self.status = 'error'
             return self._build_result_dict(error=f"Erreur lors du traitement ou de la résolution de l'algorithme : {e}")
        except Exception as e:
             self.status = 'error'
             print(f"Erreur inattendue dans solve(): {e}\n{traceback.format_exc()}")
             return self._build_result_dict(error=f"Une erreur inattendue est survenue lors de la résolution : {e}")

    def _build_result_dict(self, error=None):
        serializable_tableaus = []
        for t_info in self.tableaus:
             if isinstance(t_info, dict) and 'tableau' in t_info and isinstance(t_info['tableau'], np.ndarray):
                  serializable_tableaus.append({
                       'tableau': t_info['tableau'].tolist(),
                       'basis_vars': t_info.get('basis_vars'),
                       'variable_names': t_info.get('variable_names')
                  })
             else:
                  print(f"Warning: Skipping unprocessable item in self.tableaus during serialization. Format: {type(t_info)}. Content Sample: {str(t_info)[:100]}")
                  pass

        return {
            'status': self.status,
            'solution': self.solution.tolist() if isinstance(self.solution, np.ndarray) else self.solution,
            'optimal_value': float(self.optimal_value) if isinstance(self.optimal_value, (int, float, np.number)) else self.optimal_value,
            'tableaus': serializable_tableaus,
            'variable_names': self.variable_names,
            'error': error,
            'unsupported_message': "Ce type de problème n'est pas encore géré par l'application. Nous travaillons à étendre nos capacités !" if self.status == STATUS_UNSUPPORTED else None
        }

    def _solve_primal_max_le(self):
        tableau, basis_vars = self._build_initial_tableau()

        self._record_tableau({'tableau': tableau.copy(), 'basis_vars': basis_vars.copy(), 'variable_names': self.variable_names}, 0)

        current_tableau = tableau.copy()

        max_iterations = 100
        iteration = 0

        while iteration < max_iterations:
            if self._check_optimality(current_tableau):
                self.status = 'optimal'
                self.solution, self.optimal_value = self._extract_solution(current_tableau, basis_vars)
                return self._build_result_dict()

            pivot_col = self._choose_pivot_column(current_tableau)

            if pivot_col is None:
                 print("Warning: _choose_pivot_column returned None, but _check_optimality was False.")
                 self.status = 'error'
                 return self._build_result_dict(error="Incohérence dans le choix du pivot.")

            pivot_row = self._choose_pivot_row(current_tableau, pivot_col)

            if pivot_row is None:
                self.status = 'unbounded'
                self.solution = None
                self.optimal_value = None
                return self._build_result_dict()

            current_tableau = self._perform_pivot_operations(current_tableau.copy(), pivot_row, pivot_col)
            basis_vars[pivot_row] = pivot_col

            iteration += 1
            self._record_tableau({'tableau': current_tableau.copy(), 'basis_vars': basis_vars.copy(), 'variable_names': self.variable_names}, iteration)

        self.status = 'error'
        return self._build_result_dict(error="Limite d'itérations atteinte, possible problème de dégénérescence ou bug non géré.")

    def _solve_via_dual(self):
        A_primal_coeffs = []
        b_primal = []
        c_primal = self.c

        for constraint in self.constraints_data:
            A_primal_coeffs.append(constraint.get('coefficients', []))
            b_primal.append(constraint.get('rhs', 0))

        A_primal_matrix = np.array(A_primal_coeffs, dtype=float)

        A_dual_matrix = A_primal_matrix.T
        c_dual_coeffs = b_primal
        b_dual_vector = c_primal

        dual_constraints_data = []
        num_primal_vars = self.num_original_variables
        num_primal_constraints = self.num_original_constraints

        for i in range(num_primal_vars):
            dual_constraints_data.append({
                "coefficients": A_dual_matrix[i, :].tolist(),
                "sense": SENSE_LE,
                "rhs": b_dual_vector[i]
            })

        num_dual_original_vars = self.num_original_constraints
        num_dual_constraints = self.num_original_variables

        dual_solver = SimplexSolver(
            objective_type='max',
            objective_coefficients=c_dual_coeffs,
            constraints=dual_constraints_data,
            verbose=self.verbose
        )

        dual_solver.num_original_variables = num_dual_original_vars
        dual_solver.num_original_constraints = num_dual_constraints

        dual_result = dual_solver.solve()

        # Transfer dual tableaus to primal solver's tableaus, converting list of lists back to ndarray
        self.tableaus = []
        if dual_result.get('tableaus'):
             for t_info_serializable in dual_result['tableaus']:
                  if isinstance(t_info_serializable, dict) and 'tableau' in t_info_serializable:
                       try:
                           dual_tableau_ndarray = np.array(t_info_serializable['tableau'], dtype=float)
                           # Re-record using the primal solver's method to store as ndarray
                           # Use current length as iteration number for recording order
                           self._record_tableau({
                               'tableau': dual_tableau_ndarray,
                               'basis_vars': t_info_serializable.get('basis_vars'),
                               'variable_names': t_info_serializable.get('variable_names')
                           }, iteration=len(self.tableaus))
                       except Exception as e:
                           print(f"Error converting dual tableau to ndarray for recording: {e}")
                           pass
                  else:
                      print(f"Warning: Skipping unprocessable item from dual result tableaus during transfer. Format: {type(t_info_serializable)}")
                      pass

        self.optimal_value = dual_result['optimal_value']
        self.status = dual_result['status']

        if dual_result['status'] == 'optimal':
            if not dual_result.get('tableaus'):
                 self.status = 'error'
                 return self._build_result_dict(error="Le solveur dual a retourné optimal mais sans tableaux.")

            final_dual_tableau_info = dual_result['tableaus'][-1]
            final_dual_tableau_list = final_dual_tableau_info['tableau']
            final_dual_tableau = np.array(final_dual_tableau_list)

            dual_variable_names_in_tableau = final_dual_tableau_info['variable_names']

            # Find columns for dual slack variables ('sX')
            dual_slack_col_indices = [i for i, name in enumerate(dual_variable_names_in_tableau) if name.startswith('s')]

            # Ensure the number of slack indices matches the number of original primal variables
            if len(dual_slack_col_indices) != self.num_original_variables:
                print(f"Error: Mismatch in dual slack count ({len(dual_slack_col_indices)}) and original primal variable count ({self.num_original_variables}).")
                self.status = 'error'
                return self._build_result_dict(error="Erreur interne lors de l'interprétation du résultat dual.")


            # Primal solution values are the reduced costs of the dual slack variables
            # Extract values from the Z-row (last row) at these indices
            primal_solution_values = final_dual_tableau[-1, dual_slack_col_indices]

            self.solution = primal_solution_values
            self.variable_names = [f"x{i+1}" for i in range(self.num_original_variables)]

            return self._build_result_dict()

        elif dual_result['status'] == 'unbounded':
            self.status = 'infeasible'
            self.solution = None
            self.optimal_value = None
            return self._build_result_dict(error="Le problème primal est infaisable (son dual est non borné).")

        elif dual_result['status'] == 'infeasible':
             self.status = 'unbounded'
             self.solution = None
             self.optimal_value = None
             return self._build_result_dict(error="Le problème primal est non borné (son dual est infaisable).")

        else:
            self.status = dual_result['status']
            self.solution = None
            self.optimal_value = None
            dual_error_message = dual_result.get('error', 'Erreur inconnue dans le solveur dual.')
            return self._build_result_dict(error=f"Une erreur est survenue lors de la résolution du problème dual : {dual_error_message}")

    def _build_initial_tableau(self):
         num_vars_in_this_problem = self.num_original_variables
         num_constraints_in_this_problem = self.num_original_constraints

         if any(c.get('sense') != SENSE_LE or c.get('rhs') is None or c.get('coefficients') is None for c in self.constraints_data):
             raise ValueError("Internal Error: _build_initial_tableau received invalid constraint data format.")
         if any(len(c.get('coefficients', [])) != num_vars_in_this_problem for c in self.constraints_data):
              raise ValueError(f"Internal Error: Coefficient list length mismatch in _build_initial_tableau. Expected {num_vars_in_this_problem}, got different.")

         num_slack = num_constraints_in_this_problem
         num_total_vars_in_tableau = num_vars_in_this_problem + num_slack

         tableau = np.zeros((num_constraints_in_this_problem + 1, num_total_vars_in_tableau + 1), dtype=float)

         basis_vars = []
         slack_col_offset = num_vars_in_this_problem
         current_slack = 0

         for i, constraint in enumerate(self.constraints_data):
             coeffs = constraint.get('coefficients', [0.0] * num_vars_in_this_problem)
             tableau[i, :num_vars_in_this_problem] = coeffs
             tableau[i, slack_col_offset + current_slack] = 1.0
             tableau[i, -1] = constraint.get('rhs', 0.0)
             basis_vars.append(slack_col_offset + current_slack)
             current_slack += 1

         c_coeffs = self.c[:num_vars_in_this_problem]
         tableau[num_constraints_in_this_problem, :num_vars_in_this_problem] = -c_coeffs

         original_prefix = 'y' if self.objective_type == 'min' else 'x'
         original_var_names = [f"{original_prefix}{i+1}" for i in range(num_vars_in_this_problem)]
         slack_var_names = [f"s{i+1}" for i in range(num_slack)]
         self.variable_names = original_var_names + slack_var_names

         return tableau, basis_vars

    def _record_tableau(self, tableau_info, iteration):
         cloned_info = {
             'tableau': tableau_info['tableau'].copy(),
             'basis_vars': tableau_info.get('basis_vars')[:] if tableau_info.get('basis_vars') is not None else None,
             'variable_names': tableau_info.get('variable_names')[:] if tableau_info.get('variable_names') is not None else None
         }
         self.tableaus.append(cloned_info)
         if self.verbose:
              self.print_tableau(cloned_info, iteration)

    def print_tableau(self, tableau_info, iteration=None):
        tableau = tableau_info['tableau']
        basis_vars = tableau_info.get('basis_vars')
        var_names = tableau_info.get('variable_names')

        if tableau is None:
             print(f"\n--- Iteration {iteration} ---")
             print("Tableau data is missing or not in the expected format.")
             return

        if iteration is not None:
            print(f"\n--- Iteration {iteration} ---")

        if var_names is None:
             num_vars = tableau.shape[1] - 1
             var_names = [f"v{i+1}" for i in range(num_vars)]
             print("Warning: Variable names missing, using placeholders.")

        basic_var_names = []
        if basis_vars is not None and var_names is not None:
             try:
                  basic_var_names = [var_names[idx] for idx in basis_vars]
             except IndexError:
                  print("Warning: Index error when getting basic variable names. Basis indices or var names might be wrong.")
                  basic_var_names = [f"Base_{i}" for i in range(len(basis_vars))]

        header = ['Base'] + var_names + ['RHS']
        col_widths = [max(len(name) for name in basic_var_names + ['Base'])]
        col_widths += [max(len(name), 6) for name in var_names]
        col_widths.append(max(len('RHS'), 6))

        num_rows_tableau, num_cols_tableau = tableau.shape
        for r in range(num_rows_tableau):
            for j in range(num_cols_tableau):
                col_idx_in_widths = j + 1
                str_val = f"{tableau[r, j]:.2f}"
                if len(str_val) > col_widths[col_idx_in_widths]:
                      col_widths[col_idx_in_widths] = len(str_val)

        formatted_header = [header[0].ljust(col_widths[0])] + \
                           [header[j+1].ljust(col_widths[j+1]) for j in range(len(var_names))] + \
                           [header[-1].ljust(col_widths[-1])]
        print(" ".join(formatted_header))

        num_constraint_rows = num_rows_tableau - 1
        for i in range(num_constraint_rows):
            base_var = basic_var_names[i] if i < len(basic_var_names) else f"Base_{i}"
            formatted_row = [base_var.ljust(col_widths[0])]
            for j in range(num_cols_tableau):
                 col_idx_in_widths = j + 1
                 formatted_row.append(f"{tableau[i, j]:.2f}".ljust(col_widths[col_idx_in_widths]))
            print(" ".join(formatted_row))

        formatted_z_row = ['Z'.ljust(col_widths[0])]
        for j in range(num_cols_tableau):
             col_idx_in_widths = j + 1
             formatted_z_row.append(f"{tableau[num_constraint_rows, j]:.2f}".ljust(col_widths[col_idx_in_widths]))
        print(" ".join(formatted_z_row))

    def _check_optimality(self, tableau):
        last_row = tableau[-1, :-1]
        return np.all(last_row >= -1e-9)

    def _choose_pivot_column(self, tableau):
        last_row = tableau[-1, :-1]
        j = np.argmin(last_row)
        if last_row[j] < -1e-9:
             return j
        else:
             return None

    def _choose_pivot_row(self, tableau, pivot_col):
        rhs = tableau[:-1, -1]
        col = tableau[:-1, pivot_col]
        ratios = []
        for i in range(len(rhs)):
            if col[i] > 1e-9:
                ratio = rhs[i] / col[i]
                if ratio >= -1e-9:
                    ratios.append((ratio, i))

        if not ratios:
            return None

        min_ratio = min(ratios)[0]
        min_ratio_indices = [i for ratio, i in ratios if abs(ratio - min_ratio) < 1e-9]
        pivot_row_index = min(min_ratio_indices)

        return pivot_row_index

    def _perform_pivot_operations(self, tableau, pivot_row, pivot_col):
        new_tableau = tableau.copy()
        pivot_elem = new_tableau[pivot_row, pivot_col]

        if abs(pivot_elem) < 1e-9:
             raise ValueError("Pivot element is zero or close to zero. Algorithm error.")

        new_tableau[pivot_row, :] /= pivot_elem

        num_rows = new_tableau.shape[0]
        for i in range(num_rows):
            if i != pivot_row:
                factor = new_tableau[i, pivot_col]
                new_tableau[i, :] -= factor * new_tableau[pivot_row, :]

        return new_tableau

    def _extract_solution(self, tableau, basis_vars):
         num_vars_to_extract = self.num_original_variables
         solution = np.zeros(num_vars_to_extract)

         for i, var_idx in enumerate(basis_vars):
             if var_idx < num_vars_to_extract:
                 solution[var_idx] = tableau[i, -1]

         optimal_value = tableau[-1, -1]

         return solution, optimal_value