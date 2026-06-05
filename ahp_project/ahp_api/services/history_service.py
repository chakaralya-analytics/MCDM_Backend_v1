"""
history_service.py — alternative calculation history operations.

All reads and writes to AlternativeCalculation go through here so views
remain thin and the persistence strategy can be changed independently.
"""

import logging
from django.db import transaction

from ..models import AlternativeCalculation, AHPProject

logger = logging.getLogger(__name__)


def save_alternative_calculation(project, alternatives, scores, ranking, final_scores):
    """Persist a completed alternative calculation and return the new record.

    Also promotes the project type to 'full_analysis' if it was not already.
    Everything runs inside a single atomic block.
    """
    with transaction.atomic():
        calc = AlternativeCalculation.objects.create(
            project=project,
            alternatives=alternatives,
            scores=scores,
            ranking=ranking,
            final_scores=final_scores,
        )

        if project.project_type != 'full_analysis':
            project.project_type = 'full_analysis'
            project.save(update_fields=['project_type'])

    logger.info(
        "Saved AlternativeCalculation id=%s for project id=%s (%d alternatives)",
        calc.id, project.id, len(alternatives),
    )
    return calc


def get_history_list(project):
    """Return a list of calculation summary dicts, newest first.

    Each dict has the keys the frontend expects:
      id, created_at, alternative_count, alternatives,
      top_ranking, top_score, has_full_data
    """
    calcs = (
        AlternativeCalculation.objects
        .filter(project=project)
        .order_by('-created_at')
    )

    history = []
    for calc in calcs:
        ranking = calc.ranking or []
        final_scores = calc.final_scores or {}
        top_name = ranking[0] if ranking else None
        history.append({
            'id': calc.id,
            'created_at': calc.created_at.isoformat(),
            'alternative_count': len(calc.alternatives or []),
            'alternatives': calc.alternatives or [],
            'top_ranking': top_name,
            'top_score': final_scores.get(top_name) if top_name else None,
            'has_full_data': bool(calc.final_scores and calc.scores),
        })
    return history


def get_history_entry(project, calc_id):
    """Return the full data for a single calculation.

    Raises AlternativeCalculation.DoesNotExist if not found or project mismatch.
    """
    return AlternativeCalculation.objects.get(id=calc_id, project=project)
