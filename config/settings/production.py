from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = [
    "cateringos.corpaia.com",
    "www.cateringos.corpaia.com",
    "api.cateringos.corpaia.com",
]

SECRET_KEY = os.getenv("SECRET_KEY")

# CORS — specific origins only; CORS_ALLOW_ALL_ORIGINS must NOT be set
CORS_ALLOWED_ORIGINS = [
    "https://cateringos.corpaia.com",
    "https://www.cateringos.corpaia.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://cateringos.corpaia.com",
    "https://www.cateringos.corpaia.com",
]

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')