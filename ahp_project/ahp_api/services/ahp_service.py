"""
ahp_service.py — pure calculation logic, no Django model imports.

These functions can be tested in isolation without a database.  Views call
them, receive plain dicts, then hand off persistence to project_service or
history_service.
"""

import logging
from ..AHP import AHP

logger = logging.getLogger(__name__)


def run_criteria_calculation(project_name, criteria, pairwise_matrix):
    """Run the AHP eigenvector method for criteria-only weighting.

    Returns the result dict produced by AHP.run_criteria_only(), which
    contains 'weights', 'consistency_ratio', and related diagnostics.

    Raises ValueError if dimensions are inconsistent.
    """
    if len(pairwise_matrix) != len(criteria):
        raise ValueError(
            f"Pairwise matrix has {len(pairwise_matrix)} rows "
            f"but {len(criteria)} criteria were supplied."
        )

    ahp = AHP(criteria, project_name=project_name)
    ahp.set_pairwise_matrix(pairwise_matrix)
    result = ahp.run_criteria_only()
    logger.debug(
        "AHP criteria calc done: project=%r criteria=%d CR=%.4f",
        project_name, len(criteria), result.get('consistency_ratio', -1),
    )
    return result


def run_alternative_scoring(criteria, weights, alternatives, alternative_scores):
    """Compute weighted TOPSIS-style scores for each alternative.

    Each score is normalised from the 1-10 input range to [0, 1] and then
    multiplied by the corresponding criterion weight.

    Returns a tuple (final_scores, ranking_list) where:
      - final_scores:  {alternative_name: float}
      - ranking_list:  alternative names sorted best-first
    """
    final_scores = {}

    for alt_name in alternatives:
        total = 0.0
        for i, criterion in enumerate(criteria):
            raw = alternative_scores[alt_name][criterion]
            # Map 1-10 → 0.0-1.0
            normalised = (raw - 1) / 9.0
            total += normalised * weights[i]
        final_scores[alt_name] = total

    ranking_list = sorted(final_scores, key=lambda k: final_scores[k], reverse=True)
    logger.debug(
        "Alternative scoring done: %d alternatives, winner=%r score=%.4f",
        len(alternatives),
        ranking_list[0] if ranking_list else None,
        final_scores.get(ranking_list[0], 0) if ranking_list else 0,
    )
    return final_scores, ranking_list
