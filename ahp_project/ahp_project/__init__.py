# Make the Celery app available at the package level so Django's app registry
# initialises it on startup.  This is the pattern recommended by the Celery docs.
from .celery import app as celery_app

__all__ = ('celery_app',)
