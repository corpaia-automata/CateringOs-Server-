from .base import *
import os

DEBUG = False

# ✅ REQUIRED (THIS FIXES YOUR 400 ERROR)
ALLOWED_HOSTS = [
    "cateringos.corpaia.com",
    "www.cateringos.corpaia.com",
    "api.cateringos.corpaia.com",  
]

# Secrets
SECRET_KEY = os.getenv("SECRET_KEY")

# CORS (frontend → backend)
CORS_ALLOWED_ORIGINS = [
    "https://cateringos.corpaia.com",
    "https://www.cateringos.corpaia.com",
]

# CSRF (VERY IMPORTANT for admin login)
CSRF_TRUSTED_ORIGINS = [
    "https://cateringos.corpaia.com",
]

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Static
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')