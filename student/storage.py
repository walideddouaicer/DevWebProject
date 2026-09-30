"""Private file storage for project deliverables (PLAN P1.7).

Files live under settings.PRIVATE_MEDIA_ROOT, which is never exposed by the web
server. `url()` is deliberately unsupported so no template can link a raw file; use
`ProjectDeliverable.download_url` (permission-checked view) instead.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.signals import setting_changed
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


@deconstructible
class PrivateStorage(FileSystemStorage):
    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def url(self, name):
        raise NotImplementedError(
            "Private files have no public URL; use ProjectDeliverable.download_url."
        )


private_storage = PrivateStorage()


def get_private_storage():
    """Callable used by FileField(storage=...) so migrations don't embed a path."""
    return private_storage


def _reset_on_settings_change(*, setting, **kwargs):
    # Tests override PRIVATE_MEDIA_ROOT; drop the cached paths when that happens.
    if setting == "PRIVATE_MEDIA_ROOT":
        for attribute in ("base_location", "location"):
            private_storage.__dict__.pop(attribute, None)


setting_changed.connect(_reset_on_settings_change)
