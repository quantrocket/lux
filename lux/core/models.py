from copy import copy

from pulsar import ImproperlyConfigured


class ModelContainer(dict):
    """Mapping of model identifiers to :class:`.LuxModel` objects
    """
    def __init__(self, app):
        super().__init__()
        self._app = app

    def register(self, model):
        '''Register a new Lux Model to the application
        '''
        if not model:
            return

        if not isinstance(model, LuxModel):
            model = model()

        if model.identifier in self:
            return self[model.identifier]

        model = copy(model)
        model.register(self._app)
        if model.identifier:
            self[model.identifier] = model

        return model

    def get(self, name, default=None):
        if isinstance(name, LuxModel):
            name = name.identifier
        return super().get(name, default)


class LuxModel:
    """Base class for models
    """
    name = None
    identifier = None
    """Unique string that identifies the model"""
    _app = None

    @property
    def app(self):
        if not self._app:
            raise ImproperlyConfigured('Model "%s" not registered' % self)
        return self._app

    # ABSTRACT METHODS
    def session(self, request, session=None):
        """Return a session for aggregating a query.

        A session must be a context manager and support these methods:

        * ``query(model)``: to create a model :class:`.Query`
        * ``add(model)``: add a model to the session
        * ``delete(model)`: delete a model
        """
        raise NotImplementedError

    def get_query(self, session):
        '''Create a new :class:`.Query` from a session
        '''
        raise NotImplementedError

    def tojson(self, request, instance, **kw):
        """Convert a ``instance`` into a JSON serialisable dictionary
        """
        raise NotImplementedError

    def create_instance(self):
        """Create the underlying instance for this model
        """
        raise NotImplementedError

    def fields(self):
        """Return a Mapping name-Field of all fields in this model
        """
        raise NotImplementedError

    # API
    def field(self, name):
        """Get the field object for field ``name``
        """
        return self.fields().get(name)

    def instance(self, o=None, fields=None):
        """Return a :class:`.ModelInstance`

        :param o: None, a raw instance or a :class:`.ModelInstance
        :param fields: optional list of fields to include in the instance
        """
        """Create a new :class:`.ModelInstance`
            """
        if isinstance(o, ModelInstance):
            return o
        if o is None:
            o = self.create_instance()
        return ModelInstance.create(self, o, fields)

    # QUERY API
    def query(self, request, session, *filters, check_permission=None,
              load_only=None, **params):
        """Get a :class:`.Query` object

        :param request: WsgiRequest object
        :param session: A session for this model query
        :param filters: optional positional filters
        :param check_permission: Optional action or dictionary to check
            permission for (string or dictionary)
        :param load_only: optional list of fields to load
        :param params: key-valued filters
        """
        query = self.get_query(session)
        if check_permission:
            fields = check_permission(request, load_only=load_only)
            query = query.load_only(*fields)
        elif load_only:
            query = query.load_only(*load_only)
        return query.filter(*filters, **params)

    def get_instance(self, request, *filters, session=None, **kwargs):
        """Get a single instance from positional and keyed-valued filters
        """
        with self.session(request, session=session) as session:
            query = self.query(request, session, *filters, **kwargs)
            return query.one()

    def get_list(self, request, *filters, session=None, **kwargs):
        """Get a list of instances from positional and keyed-valued filters
        """
        with self.session(request, session=session) as session:
            query = self.query(request, session, *filters, **kwargs)
            return query.all()

    # CRUD API
    def create_model(self, request, instance, data, session=None):
        """Create a model ``instance``"""
        return self.update_model(request, instance, data,
                                 session=session, flush=True)

    def update_model(self, request, instance, data, session=None, flush=False):
        """Update a model ``instance``"""
        with self.session(request, session=session) as session:
            session.add(instance.obj)
            for name, value in data.items():
                if instance.has(name):
                    instance.set(name, value)
            if flush:
                session.flush()
        return instance

    def delete_model(self, request, instance, session=None):
        """Delete a model ``instance``"""
        with self.session(request, session=session) as session:
            session.delete(instance.obj)

    def set_instance_value(self, instance, name, value):
        setattr(instance.obj, name, value)

    def get_instance_value(self, instance, name):
        return getattr(instance.obj, name, None)

    # INTERNALS
    def register(self, app):
        self._app = app

    def load_only_fields(self, load_only=None):
        """Generator of field names"""
        for field in self.fields():
            if load_only is None or field in load_only:
                yield field

    def context(self, request, instance, context):
        """Add context to an instance context

        :param request: WSGI request
        :param instance: an instance of this model
        :param context: context dictionary
        :return:
        """

    def validate_fields(self, request, instance, data):
        """Validate fields values
        """
        pass


class ModelInstance:

    def __init__(self, model, obj, fields=None):
        self.model = model
        self.obj = obj
        self.fields = fields
        try:
            obj._model_instance = self
        except Exception:
            pass

    @property
    def id(self):
        return self.get(self.model.id_field)

    def __repr__(self):
        return repr(self.obj)

    def __str__(self):
        return str(self.obj)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def create(cls, model, obj, fields=None):
        if hasattr(obj, '_model_instance'):
            return obj._model_instance
        return cls(model, obj, fields)

    def has(self, field):
        return self.fields is None or field in self.fields

    def set(self, name, value):
        self.model.set_instance_value(self, name, value)

    def get(self, name):
        return self.model.get_instance_value(self, name)


class Query:
    "Interface for a Query"

    def __init__(self, model, session=None):
        self.model = model
        self.fields = None

    @property
    def name(self):
        return self.model.name

    @property
    def app(self):
        return self.model.app

    def one(self):
        raise NotImplementedError

    def all(self):
        """Aggregate results of this query.

        :return: an iterable over :class:`.ModelInstance`"""
        raise NotImplementedError

    def count(self):
        raise NotImplementedError

    def limit(self, limit):
        raise NotImplementedError

    def offset(self, offset):
        raise NotImplementedError

    def sortby_field(self, entry, direction):
        raise NotImplementedError

    def filter_args(self, *args):
        raise NotImplementedError

    def filter_field(self, field, op, value):
        raise NotImplementedError

    def search(self, search):
        return self

    def load_only(self, *fields):
        if self.fields is None:
            self.fields = set(fields)
        else:
            self.fields = self.fields.intersection(fields)
        return self

    def filter(self, *filters, search=None, **params):
        if filters:
            self.filter_args(*filters)

        fields = self.model.fields()

        for key, value in params.items():
            bits = key.split(':')
            field = bits[0]
            if field in fields:
                op = bits[1] if len(bits) == 2 else 'eq'
                field = fields[field].field
                if isinstance(field, str):
                    self.filter_field(field, op, value)

        if search:
            self.search(search)

        return self

    def sortby(self, sortby=None):
        if sortby:
            if not isinstance(sortby, list):
                sortby = (sortby,)
            for entry in sortby:
                direction = None
                if ':' in entry:
                    entry, direction = entry.split(':')
                self.sortby_field(entry, direction)
        return self

    def tojson(self, request, **kw):
        """Convert to a JSON serializable list

        :return: a JSON serialisable list of model objects
        """
        model = self.model
        kw['in_list'] = True
        return [model.tojson(request, o, **kw) for o in self.all()]


def permission_args(action):
    args = ()
    if isinstance(action, dict):
        args = action.get('args', args)
        action = action.get('action', 'read')
    return action, args
