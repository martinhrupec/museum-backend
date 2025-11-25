from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    
    def ready(self):
        """
        OVERRIDE: Run code when Django starts.
        Import signals to register them.
        """
        # Import signals
        import api.api_models.user_type  # noqa - registers signals
