import logging
from datetime import timedelta
import structlog

from corsheaders.defaults import default_headers
logger = structlog.get_logger("default")
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-local-dev-key"
)
#################################
#       PROJECT ROOT DIR        #
#################################
BASE_DIR = Path(__file__).resolve().parent.parent.parent


##############################
#   DJANGO BASE SETTINGS     #
##############################
DEBUG = True if os.environ.get("DEBUG", "True") == "True" else False
ENABLE_TRACING = True if os.environ.get("ENABLE_TRACING", "True") == "True" else False
ENABLE_DOCS = True if os.environ.get("ENABLE_DOCS", "True") == "True" else False
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"


##############################################
#     INTERNATIONALIZATION AND TIMEZONE      #
##############################################
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


##############################
#      INSTALLED APPS        #
##############################
INSTALLED_APPS = [
    # Default
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Internal Apps
    "db",
    # Third Party
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "storages",
    "django_structlog",
    "django_crontab",
    # health checks
    "health_check",  # required
    # "health_check.db",  # stock Django health checkers
    "health_check.contrib.migrations",
]


#############################
#        MIDDLEWARES        #
#############################
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # CORS
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "crum.CurrentRequestUserMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
]


#############################
#        TEMPLATES          #
#############################
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


#############################
#        DATABASES          #
#############################
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": (os.environ.get("POSTGRES_NAME")
                 or os.environ.get("POSTGRES_DB")),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT"),
        "OPTIONS": (
            {}
            if os.environ.get("POSTGRES_DB_SSL_ENABLED", "False") == "False"
            else {
                "sslmode": "verify-full",
                "sslrootcert": "./postgresql_ssl_cert.pem",
            }
        ),
    }
}

#############################
#       AWS CREDS         #
#############################
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", None)  # Optional: set for MinIO
AWS_S3_USE_SSL = os.environ.get("AWS_S3_USE_SSL", "True") == "True"  # Optional: set for MinIO
AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "False") == "False"


#############################
#       STORAGE ENGINE      #
#############################
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "region_name": AWS_S3_REGION_NAME,
            "bucket_name": AWS_S3_BUCKET,
            "endpoint_url": AWS_S3_ENDPOINT_URL if AWS_S3_ENDPOINT_URL else None,
            "use_ssl": AWS_S3_USE_SSL,
        },
    },
    "staticfiles": {  # Static files
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "region_name": AWS_S3_REGION_NAME,
            "bucket_name": AWS_S3_BUCKET,
            "endpoint_url": AWS_S3_ENDPOINT_URL if AWS_S3_ENDPOINT_URL else None,
            "use_ssl": AWS_S3_USE_SSL,
            "location": "static",
        },
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 4294967296  # 4GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 4294967296  # 4GB


#############################
#       STATIC FILES        #
#############################
STATIC_URL = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"


#############################
#       MEDIA FILES         #
#############################
MEDIA_URL = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"

DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

AWS_QUERYSTRING_AUTH = False
AWS_S3_CUSTOM_DOMAIN = ""



########################################
#       REST FRAMEWORK SETTINGS        #
########################################
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.FileUploadParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
}


#################################
#       JWT AUTH SETTINGS       #
#################################
AUTH_USER_MODEL = "db.UserMaster"
AUTHENTICATION_BACKENDS = [
    "user.authentication.EmailAuthenticationBackend",
]
SIMPLE_JWT = {
    "BLACKLIST_DB_ALIAS": "default",
    "ACCESS_TOKEN_LIFETIME": timedelta(days=float(os.getenv("ACCESS_TOKEN_LIFETIME_IN_MINUTES", 1))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=float(os.getenv("REFRESH_TOKEN_LIFETIME_IN_DAYS", 7))),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


#############################
#       CORS SETTINGS       #
#############################
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    *default_headers,
    "x-request-id",
    'X-API-KEY'
]
CORS_EXPOSE_HEADERS = [
    "x-request-id",
]


#############################
#     STRUCTLOG SETTINGS    #
#############################
DJANGO_STRUCTLOG_STATUS_4XX_LOG_LEVEL = logging.INFO
DJANGO_STRUCTLOG_USER_ID_FIELD = "id"

DEBUG = True

CRONJOBS = [


]

from phonepe.sdk.pg.env import Env


PHONE_PE_CLIENT_ID=os.environ.get("PHONE_PE_CLIENT_ID", "M232O4UX2AXM7_2604211147")
PHONE_PE_CLIENT_SECRETE=os.environ.get("PHONE_PE_CLIENT_SECRET", "ZDZkZjFmOTQtOGNiMS00NjNiLThhOTMtYWEyYzcxODg5ZTZk")
PHONE_PE_CLIENT_VERSION="1.0"
PHONE_PE_ENV=Env.SANDBOX
PHONEPE_WEBHOOK_USERNAME = os.environ.get("PHONEPE_WEBHOOK_USERNAME","Ranjith")
PHONEPE_WEBHOOK_PASSWORD =os.environ.get("PHONEPE_WEBHOOK_PASSWORD","Password@123")





