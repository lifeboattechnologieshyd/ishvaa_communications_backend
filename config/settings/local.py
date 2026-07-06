ALLOWED_HOSTS = ["*"]

# ruff: noqa

from config.settings.common import *  # noqa : F403

############################
#       SILK SETTINGS      #
############################
ENABLE_SILK = True if os.environ.get("ENABLE_SILK", "False") == "True" else False

SILKY_PYTHON_PROFILER = True
SILKY_INTERCEPT_PERCENT = 100
SILKY_META = True

if ENABLE_SILK:
    INSTALLED_APPS += ["silk"]
    MIDDLEWARE += ["silk.middleware.SilkyMiddleware"]



DEBUG = True

ALLOWED_HOSTS = ["*"]