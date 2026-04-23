try:
    from .asgi_channels import application
except ModuleNotFoundError:
    import os
    from django.core.asgi import get_asgi_application

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')
    application = get_asgi_application()
