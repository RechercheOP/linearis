import google.generativeai as genai
from django.conf import settings
import os
from PIL import Image
import io
import json
import re
from pdf2image import convert_from_path
import tempfile

class GeminiService:
    def __init__(self):
        # Configuration de l'API Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def process_image(self, image_file):
        """
        Traite une image avec Gemini pour extraire les équations du problème de PL
        """
        try:
            # Lecture de l'image
            image = Image.open(image_file)
            
            # Préparation du prompt
            prompt = """
            Analyse cette image qui contient un problème de programmation linéaire.
            Extrais et renvoie uniquement les informations au format JSON suivant :
            {
                "objective_type": "max" ou "min",
                "objective_function": "équation complète (ex: 3x1 + 2x2)",
                "constraints": [
                    "1x1 + 1x2 <= 10",  # TOUJOURS avec tous les coefficients
                    "1x1 + 0x2 >= 5"    # Même les coefficients nuls
                ]
            }
            
            Important :
            - Utilise x1, x2, x3, etc. pour les variables
            - Utilise <=, >=, ou = pour les contraintes
            - N'inclue que les coefficients numériques (pas de fractions)
            - Assure-toi que le format est exactement comme dans les exemples
            
            Règles strictes :
            1. Utilisez TOUJOURS toutes les variables dans chaque équation
            2. Même si un coefficient est 0, incluez-le explicitement (ex: 0x2)
            3. Format exact : [coefficient][variable] +/- [coefficient][variable]...
            
            """
            
            # Génération de la réponse
            response = self.model.generate_content([prompt, image])
            
            # Extraction du JSON de la réponse
            try:
                # Recherche du JSON dans la réponse
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    data = json.loads(json_str)
                else:
                    raise ValueError("Format JSON non trouvé dans la réponse")
                
                # Validation des données
                if not self._validate_data(data):
                    raise ValueError("Données invalides dans la réponse")
                
                # Validation des équations
                if not self._validate_equations(data):
                    raise ValueError("Format des équations invalide")
                
                # Formatage des données pour correspondre au format attendu
                formatted_data = {
                    'objective_type': data['objective_type'],
                    'objective_coefficients': self._parse_equation(data['objective_function']),
                    'constraints': [
                        {
                            'coefficients': self._parse_equation(constraint),
                            'sense': self._get_constraint_sense(constraint),
                            'rhs': self._get_constraint_rhs(constraint)
                        }
                        for constraint in data['constraints']
                    ]
                }
                
                # Validation finale des données formatées
                if not self._validate_formatted_data(formatted_data):
                    raise ValueError("Données formatées invalides")
                
                return formatted_data
                
            except json.JSONDecodeError as e:
                raise ValueError(f"Erreur de parsing JSON : {str(e)}")
            
        except Exception as e:
            raise Exception(f"Erreur lors du traitement de l'image : {str(e)}")

    def process_pdf(self, pdf_file):
        """
        Traite un PDF avec Gemini pour extraire les équations du problème de PL
        """
        try:
            # Création d'un dossier temporaire pour les images
            with tempfile.TemporaryDirectory() as temp_dir:
                # Conversion du PDF en images
                images = convert_from_path(
                    pdf_file,
                    output_folder=temp_dir,
                    fmt='png',
                    dpi=300  # Résolution élevée pour une meilleure qualité
                )
                
                if not images:
                    raise ValueError("Aucune page trouvée dans le PDF")
                
                # Traitement de chaque page
                all_results = []
                for i, image in enumerate(images):
                    try:
                        # Sauvegarde temporaire de l'image
                        image_path = os.path.join(temp_dir, f'page_{i+1}.png')
                        image.save(image_path, 'PNG')
                        
                        # Traitement de l'image
                        with open(image_path, 'rb') as img_file:
                            result = self.process_image(img_file)
                            all_results.append(result)
                            
                    except Exception as e:
                        print(f"Erreur lors du traitement de la page {i+1}: {str(e)}")
                        continue
                
                if not all_results:
                    raise ValueError("Aucune page n'a pu être traitée avec succès")
                
                # Fusion des résultats
                # Pour l'instant, nous prenons le premier résultat valide
                # TODO: Implémenter une logique plus sophistiquée pour fusionner les résultats
                return all_results[0]
                
        except Exception as e:
            raise Exception(f"Erreur lors du traitement du PDF : {str(e)}")

    def _validate_data(self, data):
        """Valide la structure des données"""
        required_keys = ['objective_type', 'objective_function', 'constraints']
        if not all(key in data for key in required_keys):
            return False
        
        if data['objective_type'] not in ['max', 'min']:
            return False
        
        if not isinstance(data['constraints'], list):
            return False
        
        return True

    def _validate_equations(self, data):
        """Valide le format des équations"""
        # Validation de la fonction objectif
        if not re.match(r'^[+-]?\s*\d*\.?\d*x\d+(\s*[+-]\s*\d*\.?\d*x\d+)*$', data['objective_function']):
            return False
        
        # Validation des contraintes
        for constraint in data['constraints']:
            if not re.match(r'^[+-]?\s*\d*\.?\d*x\d+(\s*[+-]\s*\d*\.?\d*x\d+)*\s*([<>=]=?)\s*[+-]?\s*\d*\.?\d+$', constraint):
                return False
        
        return True

    def _validate_formatted_data(self, data):
        # Vérification des clés obligatoires
        required_keys = ['objective_type', 'objective_coefficients', 'constraints']
        if not all(key in data for key in required_keys):
            raise ValueError("Données manquantes dans la réponse de Gemini")
        
        # Vérifie que toutes les contraintes ont le bon nombre de variables
        expected_length = len(data['objective_coefficients'])
        for i, constraint in enumerate(data['constraints']):
            if len(constraint['coefficients']) != expected_length:
                # Essaye de réparer automatiquement en ajoutant des 0
                if len(constraint['coefficients']) < expected_length:
                    constraint['coefficients'].extend(
                        [0.0] * (expected_length - len(constraint['coefficients'])))
                else:
                    raise ValueError(
                        f"Contrainte {i+1} : Trop de coefficients. "
                        f"Attendu: {expected_length}, Reçu: {len(constraint['coefficients'])}"
                    )
        # Vérification du type d'objectif
        if data['objective_type'] not in ['max', 'min']:
            return False
        
        # Vérification des coefficients de la fonction objectif
        if not data['objective_coefficients'] or not all(isinstance(x, (int, float)) for x in data['objective_coefficients']):
            return False
        
        # Vérifie la cohérence du nombre de coefficients
        num_vars = len(data['objective_coefficients'])
        for constraint in data['constraints']:
            if len(constraint['coefficients']) != num_vars:
                raise ValueError(
                    f"Nombre incohérent de coefficients dans une contrainte. "
                    f"Attendu: {num_vars}, Reçu: {len(constraint['coefficients'])}"
                )
            return True
        
        # Vérification des contraintes
        for constraint in data['constraints']:
            if not all(key in constraint for key in ['coefficients', 'sense', 'rhs']):
                return False
            
            if not constraint['coefficients'] or not all(isinstance(x, (int, float)) for x in constraint['coefficients']):
                return False
            
            if constraint['sense'] not in ['<=', '>=', '=']:
                return False
            
            if not isinstance(constraint['rhs'], (int, float)):
                return False
        
        return True

    def _parse_equation(self, equation):
        # Détecte toutes les variables du problème
        all_vars = sorted(set(re.findall(r'x\d+', equation)))
        if not all_vars:
            raise ValueError("Aucune variable détectée dans l'équation")
        
        # Initialise tous les coefficients à 0
        coefficients = {var: 0.0 for var in all_vars}
        
        # Extrait les termes présents
        terms = re.findall(r'([+-]?\s*\d*\.?\d*)\s*(x\d+)', equation)
        for coeff_str, var in terms:
            coeff = 1.0  # Valeur par défaut si pas de coefficient
            if coeff_str.strip() not in ['', '+', '-']:
                coeff = float(coeff_str.replace(' ', ''))
            if '-' in coeff_str:
                coeff *= -1
            coefficients[var] = coeff
        
        return [coefficients[var] for var in all_vars]  # Retourne dans l'ordre x1, x2, etc.

    def _get_constraint_sense(self, constraint):
        """Extrait le sens de la contrainte (<=, >=, =)"""
        if '<=' in constraint:
            return '<='
        elif '>=' in constraint:
            return '>='
        elif '=' in constraint:
            return '='
        return None

    def _get_constraint_rhs(self, constraint):
        """Extrait la valeur du côté droit de la contrainte"""
        match = re.search(r'([<>=]=?)\s*([+-]?\s*\d*\.?\d+)', constraint)
        if match:
            return float(match.group(2).replace(' ', ''))
        return None 