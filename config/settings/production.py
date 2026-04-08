from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = [
    "13.60.235.174",
    "ec2-13-60-235-174.eu-north-1.compute.amazonaws.com",
]

# Static
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Security (TEMP SAFE MODE)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False

# Secrets
SECRET_KEY = os.getenv("SECRET_KEY")



# 🔐 ENABLE AFTER DOMAIN + SSL (IMPORTANT)

# ALLOWED_HOSTS = [
#     "yourdomain.com",
#     "www.yourdomain.com",
# ]

# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True