from django.apps import AppConfig


class SurveysConfig(AppConfig):
    name = "surveys"

    def ready(self):
        import surveys.signals  # noqa
