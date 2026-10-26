"""
WSGI config for archeion project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'archeion.settings')

application = get_wsgi_application()

# Warm up before serving: load BGE-M3 and the repository embeddings once,
# so the first similarity check doesn't pay the loading time.
from django.db import close_old_connections
from similarity.pipeline import get_model, load_corpus

print("Loading BGE-M3 and repository embeddings...")
get_model()
load_corpus()
close_old_connections()
print("Model ready.")