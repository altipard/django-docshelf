"""How a permitted file is delivered.

``DOCSHELF_SERVE_BACKEND`` is one of ``django``, ``x-accel``, ``x-sendfile``, ``redirect`` or the
dotted path of a callable ``serve(request, version, public) -> HttpResponse``.
"""

import mimetypes
from urllib.parse import quote

from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.utils.http import content_disposition_header
from django.utils.module_loading import import_string

from .conf import get_setting

# Version files never change, so public ones may be cached for good.
PUBLIC_CACHE = "public, max-age=31536000, immutable"
PRIVATE_CACHE = "private, no-cache"


def _headers(response, version, public):
    response["Content-Disposition"] = content_disposition_header(False, version.filename)
    response["Cache-Control"] = PUBLIC_CACHE if public else PRIVATE_CACHE
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _content_type(version):
    return mimetypes.guess_type(version.filename)[0] or "application/octet-stream"


def serve_django(request, version, public):
    response = FileResponse(version.file.open("rb"), content_type=_content_type(version))
    return _headers(response, version, public)


def serve_x_accel(request, version, public):
    response = HttpResponse(content_type=_content_type(version))
    response["X-Accel-Redirect"] = get_setting("X_ACCEL_PREFIX") + quote(version.file.name)
    return _headers(response, version, public)


def serve_x_sendfile(request, version, public):
    response = HttpResponse(content_type=_content_type(version))
    response["X-Sendfile"] = version.file.path
    return _headers(response, version, public)


def serve_redirect(request, version, public):
    return HttpResponseRedirect(version.file.url)


BACKENDS = {
    "django": serve_django,
    "x-accel": serve_x_accel,
    "x-sendfile": serve_x_sendfile,
    "redirect": serve_redirect,
}


def serve(request, version, public):
    backend = get_setting("SERVE_BACKEND")
    func = BACKENDS.get(backend) or import_string(backend)
    return func(request, version, public)
