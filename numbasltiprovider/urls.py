from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path(r'', include('numbas_lti.urls')),
]

urlpatterns += [path(f'apps/{url}/', include(f'{name}.urls', namespace=name)) for name, url in getattr(settings, 'NUMBAS_EXTRA_APPS', [])]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
