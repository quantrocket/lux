from pulsar import ImproperlyConfigured
from pulsar.apps.greenio import WsgiGreen
from pulsar.utils.log import LocalMixin

import lux
from lux import Parameter

import odm
from odm.green import GreenMapper


class Extension(lux.Extension):

    _config = [
        Parameter('DATASTORE', None,
                  'Dictionary for mapping models to their back-ends database'),
        Parameter('SEARCHENGINE', None,
                  'Search engine for models'),
        Parameter('USEGREENLET', True,
                  ('Use the greenlet package for implicit asynchronous '
                   'paradigm'))]

    def on_loaded(self, app):
        '''Build the API middleware.

        If :setting:`API_URL` is defined, it loops through all extensions
        and checks if the ``api_sections`` method is available.
        '''
        app.mapper = AppMapper(app)
        if app.config['USEGREENLET']:
            app.handler = WsgiGreen(app.handler)


class AppMapper(LocalMixin):

    def __init__(self, app):
        self.app = app

    def __call__(self):
        if not self.local.mapper:
            self.local.mapper = self.create_mapper()
        return self.local.mapper

    def create_mapper(self):
        datastore = self.app.config['DATASTORE']
        if not datastore:
            return
        if 'default' not in datastore:
            raise ImproperlyConfigured('default datastore not specified')
        if self.app.config['USEGREENLET']:
            mapper = GreenMapper(datastore['default'])
        else:
            mapper = odm.Mapper(datastore['default'])
        mapper.register_applications(self.app.config['EXTENSIONS'])
        return mapper