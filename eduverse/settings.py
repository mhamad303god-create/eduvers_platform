"""
Django settings for eduverse project.
تعديل خاص لتشغيل البث المباشر عبر النفق (Cloudflare Tunnel)
"""

from pathlib import Path
from decouple import config, Csv

# --------------------------------------------------
# Base
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool) # اجعله True أثناء التجربة

# تعديل للسماح بجميع الروابط الخارجية
ALLOWED_HOSTS = ['*']

SITE_BASE_URL = config('SITE_BASE_URL', default='http://localhost:8000').rstrip('/')

# --------------------------------------------------
# Security Settings (التعديلات الجوهرية هنا)
# --------------------------------------------------

# السماح لديجانجو بالثوق في الروابط التي تنتهي بـ trycloudflare.com
CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# إعدادات الـ Proxy لكي يفهم ديجانجو أن الاتصال آمن عبر النفق
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# أثناء التجربة المحلية، نترك هذه False لضمان عدم حدوث تعارض مع المتصفحات
SECURE_SSL_REDIRECT = False 
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# تعديل للسماح بعرض محتوى البث (WebRTC) بدون قيود المتصفح المتشددة
X_FRAME_OPTIONS = 'SAMEORIGIN'

# --------------------------------------------------
# Cache & Database & Auth (بقيت كما هي)
# --------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'eduverse-local-cache',
    }
}

AUTH_USER_MODEL = 'accounts.User'
SITE_ID = 1

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'none' # غيرتها لـ none للتجربة السريعة بدون إرسال إيميلات حقيقية
LOGIN_REDIRECT_URL = 'accounts:dashboard_redirect'
LOGOUT_REDIRECT_URL = '/'

# --------------------------------------------------
# Applications & Middleware
# --------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.humanize",
    'django_daisy',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'accounts.apps.AccountsConfig',
    'courses',
    'bookings',
    'assessments',
    'payments',
    'notifications',
    'widget_tweaks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'notifications.middleware.SessionDueNotificationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --------------------------------------------------
# Channels & Real-time (ضروري للبث المباشر)
# --------------------------------------------------
ROOT_URLCONF = 'eduverse.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.user_roles_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'eduverse.wsgi.application'
ASGI_APPLICATION = 'eduverse.asgi_channels.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': config('CHANNEL_LAYERS_BACKEND', default='channels.layers.InMemoryChannelLayer'),
        'CONFIG': {
            'hosts': config('CHANNEL_LAYERS_CONFIG_HOSTS', default='redis://localhost:6379/1', cast=Csv()),
        } if config('CHANNEL_LAYERS_BACKEND', default='channels.layers.InMemoryChannelLayer') != 'channels.layers.InMemoryChannelLayer' else {},
    }
}

WEBRTC_STUN_URLS = config(
    'WEBRTC_STUN_URLS',
    default='stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302',
    cast=Csv(),
)
WEBRTC_TURN_URLS = config('WEBRTC_TURN_URLS', default='', cast=Csv())
WEBRTC_TURN_USERNAME = config('WEBRTC_TURN_USERNAME', default='')
WEBRTC_TURN_CREDENTIAL = config('WEBRTC_TURN_CREDENTIAL', default='')

WEBRTC_ICE_SERVERS = []
if WEBRTC_STUN_URLS:
    WEBRTC_ICE_SERVERS.append({'urls': WEBRTC_STUN_URLS})

if WEBRTC_TURN_URLS and WEBRTC_TURN_USERNAME and WEBRTC_TURN_CREDENTIAL:
    WEBRTC_ICE_SERVERS.append({
        'urls': WEBRTC_TURN_URLS,
        'username': WEBRTC_TURN_USERNAME,
        'credential': WEBRTC_TURN_CREDENTIAL,
    })

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --------------------------------------------------
# Internationalization
# --------------------------------------------------
LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Aden'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# Static & Media
# --------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --------------------------------------------------
# CORS (توسيع الصلاحيات للتجربة)
# --------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True # للسهولة أثناء التجربة

# --------------------------------------------------
# Default Settings
# --------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

