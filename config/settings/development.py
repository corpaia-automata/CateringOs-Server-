from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

# Playwright PDF capture: default local frontend origin for ``/q/<token>``
SITE_URL = env('SITE_URL', default='http://localhost:3000')

# Run Celery tasks inline when no broker is available (local development)
CELERY_TASK_ALWAYS_EAGER = True
