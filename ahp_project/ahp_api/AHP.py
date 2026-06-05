import warnings
from typing import Any, Optional

import numpy as np

random_index_choices = {
    # number of criteria : Random Index (Saaty, 1980)
    1:0.00,
    2:0.00,
    3:0.58,
    4:0.90,
    5:1.12,
    6:1.24,
    7:1.32,
    8:1.41,
    9:1.45,
    10:1.49,
    11:1.51,
    12:1.48,
    13:1.56,
    14:1.57,
    15:1.58
}

class AHP:
    def __init__(self, criteria:list, alternatives:Optional[list] = None, project_name:str = "AHP_Project") -> None:
        self.project_name = project_name
        self.criteria = criteria
        self.alternatives = alternatives or []
        self.num_criteria = len(criteria)
        self.num_alternatives = len(self.alternatives)
        self.pairwise_matrix = np.ones((self.num_criteria, self.num_criteria))
        self.alternative_matrices = None
        if self.num_alternatives > 0:
            self.alternative_matrices = np.ones((self.num_criteria, self.num_alternatives, self.num_alternatives))
        self.weights = None
        self.consistency_ratio = None

    def set_pairwise_matrix(self, matrix: list) -> None:
        self.pairwise_matrix = np.array(matrix)

    def set_alternative_matrix(self, index: int, matrix: list) -> None:
        if self.alternative_matrices is None:
            raise ValueError("No alternatives defined. Cannot set alternative matrix.")
        self.alternative_matrices[index] = np.array(matrix)

    def calculate_weights(self) -> None:
        # np.ComplexWarning was removed in numpy 2.0; use numpy.exceptions.ComplexWarning.
        # Wrap eig() inside the context so the filter actually applies.
        _complex_warn = getattr(np, 'ComplexWarning', None) or getattr(
            getattr(np, 'exceptions', None), 'ComplexWarning', Warning
        )
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', _complex_warn)
            eig_vals, eig_vecs = np.linalg.eig(self.pairwise_matrix)
        
        # Find the index of the largest eigenvalue
        max_eig_idx = np.argmax(np.real(eig_vals))
        principal_eigenvector = np.real(eig_vecs[:, max_eig_idx])
        
        # Ensure all weights are positive (AHP requirement)
        if np.any(principal_eigenvector < 0):
            principal_eigenvector = -principal_eigenvector
            
        # Normalize to get weights
        self.weights = principal_eigenvector / np.sum(principal_eigenvector)

    def calculate_consistency_ratio(self) -> None:
        if self.num_criteria <= 2:
            self.consistency_ratio = 0.0
            return
            
        # Calculate λ_max using the principal eigenvalue
        eig_vals, _ = np.linalg.eig(self.pairwise_matrix)
        lambda_max = np.max(np.real(eig_vals))

        # Consistency index = (λ_max - n)/(n-1)
        consistency_index = (lambda_max - self.num_criteria) / (self.num_criteria - 1)
        
        # Random index based on matrix size
        random_index = random_index_choices.get(self.num_criteria, 1.49)

        self.consistency_ratio = consistency_index / random_index if random_index != 0 else 0.0

    def calculate_alternative_scores(self) -> np.ndarray:
        if self.alternative_matrices is None:
            raise ValueError("No alternative matrices defined. Cannot calculate alternative scores.")
            
        alternative_scores = np.zeros(self.num_alternatives)
        
        for j in range(self.num_criteria):
            # Get weights for alternatives under this criterion
            eig_vals, eig_vecs = np.linalg.eig(self.alternative_matrices[j])
            
            # Find principal eigenvector
            max_eig_idx = np.argmax(np.real(eig_vals))
            principal_eigenvector = np.real(eig_vecs[:, max_eig_idx])
            
            # Ensure positive weights
            if np.any(principal_eigenvector < 0):
                principal_eigenvector = -principal_eigenvector
                
            # Normalize alternative weights
            alt_weights = principal_eigenvector / np.sum(principal_eigenvector)
            
            # Add weighted contribution to each alternative's score
            for i in range(self.num_alternatives):
                alternative_scores[i] += self.weights[j] * alt_weights[i]
                
        return alternative_scores

    def rank_alternatives(self) -> np.ndarray:
        scores = self.calculate_alternative_scores()
        # Sort in descending order (highest score = rank 1)
        rankings = np.argsort(-scores)
        return rankings

    def run_criteria_only(self) -> dict[str, Any]:
        """Run AHP calculation for criteria weights only"""
        self.calculate_weights()
        self.calculate_consistency_ratio()
        
        return {
            'criteria': self.criteria,
            'criteria_comparison_matrix': self.pairwise_matrix.tolist(),
            'weights': self.weights.tolist(),
            'consistency_ratio': float(self.consistency_ratio),
        }

    def run(self) -> dict[str, Any]:
        """ returns a json of format:
            'criteria_comparison_matrix'    : the pairwise comparison matrix of criteria
            'alternative_matrices'          : the alternative matrix
            'Ranking data'                  : the ranked indices of alternatives (best to worst)
            'Ranking list'                  : the ordered list of alternatives by ranks
            'weights'                       : weights of the criteria
            'consistency_ratio'             : consistency ratio
            'Alternative scores'            : final scores for each alternative
        """
        self.calculate_weights()
        self.calculate_consistency_ratio()
        rankings = self.rank_alternatives()
        alternative_scores = self.calculate_alternative_scores()
        
        # Ranking the alternatives from the ranked indices
        ranked_alternatives = [self.alternatives[i] for i in rankings]
        
        return {
            'criteria_comparison_matrix': self.pairwise_matrix.tolist(),
            'alternative_matrices': self.alternative_matrices.tolist(),
            'Ranking data': rankings.tolist(),
            'Ranking list': ranked_alternatives,
            'weights': self.weights.tolist(),
            'consistency_ratio': float(self.consistency_ratio),
            'Alternative scores': alternative_scores.tolist(),
        }