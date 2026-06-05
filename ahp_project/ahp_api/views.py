# ahp_api/views.py

import logging
import time
from functools import wraps

from django.core.cache import cache
from django.db import connections, connection
from django.db.utils import OperationalError
from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import AHPProject, AlternativeCalculation
from .serializers import (
    AHPCriteriaInputSerializer,
    AHPAlternativesScoringSerializer,
    AHPProjectListSerializer,
    AHPProjectDetailSerializer,
    CriteriaOnlyProjectSerializer,
    AlternativeCalculationSerializer,
)
from .services import project_service, ahp_service, history_service
from plans.services import usage_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Infrastructure helpers
# ---------------------------------------------------------------------------

def db_retry(max_retries=3, delay=2):
    """Decorator: retry view method on transient DB connection failures."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    connection.close_if_unusable_or_obsolete()
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    last_exc = exc
                    msg = str(exc).lower()
                    if any(k in msg for k in ('timeout', 'connection', 'server')):
                        logger.warning(
                            "DB connection failed (attempt %d/%d): %s",
                            attempt + 1, max_retries, exc,
                        )
                        if attempt < max_retries - 1:
                            time.sleep(delay * (2 ** attempt))
                            connection.close()
                            continue
                    raise
                except Exception:
                    raise
            raise last_exc
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Calculation views
# ---------------------------------------------------------------------------

class AHPCalculateView(APIView):
    """POST /api/v1/calculate/ — run AHP criteria weighting and persist."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @db_retry()
    def post(self, request):
        allowed, quota = project_service.check_can_create_project(request.user)
        if not allowed:
            return Response(
                {
                    "error": quota.get('error', 'Project limit reached'),
                    "quota": quota,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AHPCriteriaInputSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("Invalid AHP criteria input from user %s: %s",
                           request.user.id, serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            result = ahp_service.run_criteria_calculation(
                project_name=data['project_name'],
                criteria=data['criteria'],
                pairwise_matrix=data['pairwise_matrix'],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("AHP criteria calculation failed for user %s", request.user.id)
            return Response(
                {"error": "Calculation failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        project = project_service.create_criteria_project(
            user=request.user,
            project_name=data['project_name'],
            criteria=data['criteria'],
            pairwise_matrix=data['pairwise_matrix'],
            weights=result['weights'],
            consistency_ratio=result['consistency_ratio'],
        )
        usage_service.track_event(request.user, 'project_created')
        usage_service.track_event(request.user, 'calculation_run')

        result['id'] = project.id
        result['project_type'] = 'criteria_only'
        result['project_name'] = data['project_name']
        result['criteria'] = data['criteria']
        return Response(result, status=status.HTTP_201_CREATED)


class AHPCalculateAlternativesView(APIView):
    """POST /api/v1/calculate-alternatives/ — score and rank alternatives."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @db_retry()
    def post(self, request):
        serializer = AHPAlternativesScoringSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            project = project_service.get_project_for_user(
                data['project_id'], request.user
            )
        except AHPProject.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        if not project.weights:
            return Response(
                {"error": "Criteria weights not found. Complete criteria calculation first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed, quota = project_service.check_can_add_alternative(project)
        if not allowed:
            return Response(
                {
                    "error": quota.get('error', 'Alternative limit exceeded'),
                    "quota": quota,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate per-criterion score coverage
        alternatives = data['alternatives']
        alternative_scores = data['alternative_scores']
        for alt in alternatives:
            for criterion in project.criteria:
                if criterion not in alternative_scores.get(alt, {}):
                    return Response(
                        {"error": f"Missing score for '{alt}' on criterion '{criterion}'"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        try:
            final_scores, ranking_list = ahp_service.run_alternative_scoring(
                criteria=project.criteria,
                weights=project.weights,
                alternatives=alternatives,
                alternative_scores=alternative_scores,
            )
        except Exception:
            logger.exception(
                "Alternative scoring failed for project %s user %s",
                project.id, request.user.id,
            )
            return Response(
                {"error": "Calculation failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        calc = history_service.save_alternative_calculation(
            project=project,
            alternatives=alternatives,
            scores=alternative_scores,
            ranking=ranking_list,
            final_scores=final_scores,
        )
        usage_service.track_event(request.user, 'alternative_created')
        usage_service.track_event(request.user, 'calculation_run')

        limits = project_service.get_alternative_limits(project)
        return Response(
            {
                'id': project.id,
                'calculation_id': calc.id,
                'project_name': project.project_name,
                'criteria': project.criteria,
                'weights': project.weights,
                'current_alternatives': alternatives,
                'alternative_scores_raw': alternative_scores,
                'ranking_list': ranking_list,
                'final_scores': final_scores,
                'alternative_history': {
                    'count': limits['current_alternatives'],
                    'latest_id': calc.id,
                    'latest': calc.created_at.isoformat(),
                },
                **limits,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Project list / detail views
# ---------------------------------------------------------------------------

class AllProjectsView(APIView):
    """GET /api/v1/projects/all/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request):
        projects = project_service.get_projects_for_user(request.user)
        serializer = AHPProjectListSerializer(projects, many=True)
        limits = project_service.get_project_limits(request.user)
        return Response(
            {'projects': serializer.data, 'project_limits': limits},
            status=status.HTTP_200_OK,
        )


class CriteriaOnlyProjectsView(APIView):
    """GET /api/v1/projects/criteria-only/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request):
        projects = project_service.get_projects_for_user(request.user, with_weights=True)
        serializer = CriteriaOnlyProjectSerializer(projects, many=True)
        limits = project_service.get_project_limits(request.user)
        return Response(
            {'projects': serializer.data, 'project_limits': limits},
            status=status.HTTP_200_OK,
        )


class ProjectDetailView(APIView):
    """GET /api/v1/projects/<id>/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request, id):
        try:
            project = project_service.get_project_for_user(id, request.user)
        except AHPProject.DoesNotExist:
            return Response(
                {"error": "Project not found or not accessible"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AHPProjectDetailSerializer(project)
        data = dict(serializer.data)
        data['alternative_limits'] = project_service.get_alternative_limits(project)
        return Response(data, status=status.HTTP_200_OK)


class ProjectCriteriaWeightsView(APIView):
    """GET /api/v1/projects/<id>/criteria-weights/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request, id):
        try:
            project = project_service.get_project_for_user(id, request.user)
        except AHPProject.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        if not project.weights:
            return Response(
                {"error": "Criteria weights not calculated for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        criteria_weights = dict(zip(project.criteria, project.weights))
        return Response(
            {
                'id': project.id,
                'project_name': project.project_name,
                'criteria': project.criteria,
                'weights': project.weights,
                'criteria_weights': criteria_weights,
                'consistency_ratio': project.consistency_ratio,
                'alternative_limits': project_service.get_alternative_limits(project),
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Alternative history views
# ---------------------------------------------------------------------------

class AlternativeHistoryListView(APIView):
    """GET /api/v1/projects/<project_id>/history/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request, project_id):
        try:
            project = project_service.get_project_for_user(project_id, request.user)
        except AHPProject.DoesNotExist:
            return Response(
                {"error": "Project not found or not accessible"},
                status=status.HTTP_404_NOT_FOUND,
            )

        history = history_service.get_history_list(project)
        return Response({"history": history}, status=status.HTTP_200_OK)


class AlternativeHistoryDetailView(APIView):
    """GET /api/v1/projects/<project_id>/history/<int:calc_id>/"""
    permission_classes = [IsAuthenticated]

    @db_retry()
    def get(self, request, project_id, calc_id):
        try:
            project = project_service.get_project_for_user(project_id, request.user)
        except AHPProject.DoesNotExist:
            return Response(
                {"error": "Project not found or not accessible"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            calc = history_service.get_history_entry(project, calc_id)
        except AlternativeCalculation.DoesNotExist:
            return Response(
                {"error": "Calculation history entry not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                'project_id': project.id,
                'project_name': project.project_name,
                'calculation_id': calc.id,
                'created_at': calc.created_at.isoformat(),
                'criteria': project.criteria,
                'weights': project.weights,
                'alternatives': calc.alternatives,
                'scores': calc.scores,
                'ranking': calc.ranking,
                'final_scores': calc.final_scores,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """GET /api/v1/health/ — returns only 'connected'/'error' labels.

    Never leaks exception strings to unauthenticated callers.
    """
    health_status = {
        'status': 'healthy',
        'database': 'disconnected',
        'cache': 'disconnected',
    }

    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['database'] = 'connected'
    except Exception:
        logger.exception("Health check: database connection failed")
        health_status['database'] = 'error'
        health_status['status'] = 'unhealthy'

    try:
        cache.set('health_check', 'ok', 30)
        health_status['cache'] = 'connected' if cache.get('health_check') == 'ok' else 'no_response'
        if health_status['cache'] != 'connected':
            health_status['status'] = 'unhealthy'
    except Exception:
        logger.exception("Health check: cache connection failed")
        health_status['cache'] = 'error'
        health_status['status'] = 'unhealthy'

    return JsonResponse(health_status, status=200 if health_status['status'] == 'healthy' else 503)
