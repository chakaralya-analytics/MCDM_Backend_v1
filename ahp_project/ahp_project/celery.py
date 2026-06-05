"""
Celery application entry point.

Worker infrastructure is wired up here but no tasks are defined in this file.
Tasks live in <app>/tasks.py modules and are auto-discovered.

Current purpose: prepare the async infrastructure for:
  - Payment webhook processing (Phase 3)
  - Transactional email sending (Phase 3)
  - Heavy AHP/TOPSIS batch calculations that would otherwise block a web worker

Start the worker locally:
    celery -A ahp_project worker --loglevel=info
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ahp_project.settings')

app = Celery('ahp_project')

# Read CELERY_* settings from Django settings using the CELERY_ namespace prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in any installed app's tasks.py.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Smoke-test task — verifies the worker is running and connected."""
    print(f'Celery worker OK — request: {self.request!r}')
