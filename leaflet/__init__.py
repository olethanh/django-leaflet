# -*- coding: utf8 -*-
import urlparse
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext as _


DEFAULT_TILES = [(_('OSM'), 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                  u'© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')]

LEAFLET_CONFIG = getattr(settings, 'LEAFLET_CONFIG', {})

app_settings = dict({
    'TILES': DEFAULT_TILES,
    'ATTRIBUTION_PREFIX': None,
    'SPATIAL_EXTENT': None,
    'DEFAULT_ZOOM': None,
    'DEFAULT_CENTER': None,
    'SRID': None,
    'TILES_EXTENT': [],
    'SCALE': True,
    'MINIMAP': False,
    'RESET_VIEW': True,
    'NO_GLOBALS': True,
    'PLUGINS': {},
}, **LEAFLET_CONFIG)


# Backward-compatibility : defaults TILES with value of TILES_URL
if 'TILES_URL' in LEAFLET_CONFIG:
    warnings.warn("TILES_URL is deprecated.", DeprecationWarning)
    if 'TILES' in LEAFLET_CONFIG:
        raise ImproperlyConfigured(_("Remove TILES_URL and keep TILES value."))
    app_settings['TILES'] = [(app_settings['TILES_URL'])]


# If TILES is a string, convert to tuple
if isinstance(app_settings.get('TILES'), basestring):
    app_settings['TILES'] = [(_('Background'), app_settings.get('TILES'), '')]

SPATIAL_EXTENT = app_settings.get("SPATIAL_EXTENT")
if SPATIAL_EXTENT is None:
    # Deprecate lookup in global Django settings
    if hasattr(settings, 'SPATIAL_EXTENT'):
        warnings.warn("SPATIAL_EXTENT is deprecated. Use LEAFLET_CONFIG['SPATIAL_EXTENT'] instead.", DeprecationWarning)
    SPATIAL_EXTENT = getattr(settings, 'SPATIAL_EXTENT', (-180, -90, 180, 90))
if SPATIAL_EXTENT is not None:
    if not isinstance(SPATIAL_EXTENT, (tuple, list)) or len(SPATIAL_EXTENT) != 4:
        raise ImproperlyConfigured(_("Spatial extent should be a tuple (minx, miny, maxx, maxy)"))


TILES_EXTENT = app_settings.get("TILES_EXTENT")
# Due to bug in Leaflet/Proj4Leaflet ()
# landscape extents are not supported.
if TILES_EXTENT and (TILES_EXTENT[2] - TILES_EXTENT[0] > TILES_EXTENT[3] - TILES_EXTENT[1]):
    raise ImproperlyConfigured('Landscape tiles extent not supported (%s).' % (TILES_EXTENT,))


SRID = app_settings.get("SRID")
if SRID is None:
    # Deprecate lookup in global Django settings
    if hasattr(settings, 'MAP_SRID'):
        warnings.warn("MAP_SRID is deprecated. Use LEAFLET_CONFIG['SRID'] instead.", DeprecationWarning)
    if hasattr(settings, 'SRID'):
        warnings.warn("SRID is deprecated. Use LEAFLET_CONFIG['SRID'] instead.", DeprecationWarning)
    SRID = getattr(settings, 'MAP_SRID', getattr(settings, 'SRID', 3857))
if SRID == 3857:  # Leaflet's default, do not setup custom projection machinery
    SRID = None


DEFAULT_CENTER = app_settings.get('DEFAULT_CENTER', None)
if DEFAULT_CENTER is not None and not (isinstance(DEFAULT_CENTER, (list, tuple)) and len(DEFAULT_CENTER) == 2):
    raise ImproperlyConfigured("LEAFLET_CONFIG['DEFAULT_CENTER'] must be an list/tuple with two elements - (lon, lat)")


DEFAULT_ZOOM = app_settings.get("DEFAULT_ZOOM", None)
if DEFAULT_ZOOM is not None and not (isinstance(DEFAULT_ZOOM, int) and (1 <= DEFAULT_ZOOM <= 24)):
    raise ImproperlyConfigured("LEAFLET_CONFIG['DEFAULT_ZOOM'] must be an int between 1 and 24.")


PLUGINS = app_settings.get("PLUGINS", None)
if PLUGINS is not None and not (isinstance(PLUGINS, dict) and all(map(lambda el: isinstance(el, dict), PLUGINS.itervalues()))):
    error_msg = """LEAFLET_CONFIG['PLUGINS'] must be dict of dicts in the format:
    { '[plugin_name]': { 'js': '[path-to-js]', 'css': '[path-to-css]' } } .)"""
    raise ImproperlyConfigured(error_msg)

PLUGIN_ALL = 'ALL'
PLUGINS_DEFAULT = '__default__'


# Take advantage of plugin system for Leaflet.MiniMap
if app_settings.get('MINIMAP'):
    PLUGINS['minimap'] = {
        'css': 'leaflet/Control.MiniMap.css',
        'js': 'leaflet/Control.MiniMap.js',
        'auto-include': True
    }


def _normalize_plugins_config():
    """
    Normalizes the PLUGINS setting:
        * ensures the 'css' and 'js' are arrays of URLs
        * ensures all URLs are transformed as follows:
            ** if the URL is absolute - leave it as-is
            ** if the URL is a root URL - starts with a / - leave it as-is
            ** the the URL is not a root URL - does not start with / - prepend settings.STATIC_URL
    Also, adds a special key - ALL - that includes 'css' and 'js' for all plugins listed
    """
    if '__is_normalized__' in PLUGINS:  # already normalized
        return

    listed_plugins = PLUGINS.keys()
    PLUGINS[PLUGINS_DEFAULT] = dict()
    PLUGINS[PLUGIN_ALL] = dict()

    RESOURCE_TYPE_KEYS = ['css', 'js']

    for key in listed_plugins:
        plugin_dict = PLUGINS[key]

        for resource_type in RESOURCE_TYPE_KEYS:
            # normalize the resource URLs
            urls = plugin_dict.get(resource_type, None)
            if isinstance(urls, (str, unicode)):
                urls = [urls]
            elif isinstance(urls, tuple):  # force to list
                urls = list(urls)
            elif isinstance(urls, list):  # already a list
                pass
            else:  # css/js has not been specified or the wrong type
                urls = []

            # normalize the URLs - see the docstring for details
            for i, url in enumerate(urls):
                url_parts = urlparse.urlparse(url)
                if url_parts.scheme or url_parts.path.startswith('/'):
                    # absolute URL or a URL starting at root
                    pass
                else:
                    urls[i] = urlparse.urljoin(settings.STATIC_URL, url)

            plugin_dict[resource_type] = urls

            # Append it to the DEFAULT pseudo-plugin if auto-include
            if plugin_dict.get('auto-include', False):
                PLUGINS[PLUGINS_DEFAULT].setdefault(resource_type, []).extend(urls)

            # also append it to the ALL pseudo-plugin;
            PLUGINS[PLUGIN_ALL].setdefault(resource_type, []).extend(urls)

    PLUGINS['__is_normalized__'] = True

_normalize_plugins_config()
