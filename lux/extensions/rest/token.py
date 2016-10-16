import time
from datetime import datetime, timedelta
from pulsar import Http401
from pulsar.utils.pep import to_string

import lux.utils.token as jwt
from lux.core import backend_action
from .permissions import PemissionsMixin


# Cross-Origin Resource Sharing header
CORS = 'Access-Control-Allow-Origin'


class TokenBackend(PemissionsMixin):
    """Token Backend
    """
    @backend_action
    def login(self, request, user):
        """Handle a request for a token to be used on a web browser
        """
        seconds = request.config['MAX_TOKEN_SESSION_EXPIRY']
        expiry = datetime.now() + timedelta(seconds=seconds)
        token = self.create_token(request, user, expiry=expiry)
        token = to_string(token.encoded)
        request.response.status_code = 201
        return {'success': True,
                'token': token}

    def request(self, request):
        '''Check for ``HTTP_AUTHORIZATION`` header and if it is available
        and the authentication type if ``bearer`` try to perform
        authentication using JWT_.
        '''
        auth = request.get('HTTP_AUTHORIZATION')
        user = request.cache.user
        if auth and user.is_anonymous():
            self.authorize(request, auth)

    def authorize(self, request, auth):
        """Authorize claim

        :param auth: a string containing the authorization information
        """
        auth_type, key = auth.split(None, 1)
        auth_type = auth_type.lower()
        user = None
        try:
            if auth_type == 'bearer':
                token = self.decode_token(request, key)
                request.cache.session = token
                user = self.get_user(request, **token)
            elif auth_type == 'oauth':
                user = self.get_user(request, oauth=key)
        except Http401:
            raise
        except Exception:
            request.app.logger.exception('Could not load user')
        else:
            if user:
                request.cache.user = user

    def response(self, response):
        if CORS not in response.headers:
            origin = response.environ.get('HTTP_ORIGIN', '*')
            response[CORS] = origin
        return response

    def response_middleware(self, app):
        return [self.response]

    def on_preflight(self, app, request, methods=None):
        '''Preflight handler
        '''
        headers = request.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS')
        methods = methods or app.config['CORS_ALLOWED_METHODS']
        response = request.response
        origin = request.get('HTTP_ORIGIN', '*')

        if origin == 'null':
            origin = '*'

        response[CORS] = origin
        if headers:
            response['Access-Control-Allow-Headers'] = headers
        if not isinstance(methods, (str, list)):
            methods = list(methods)
        response['Access-Control-Allow-Methods'] = methods

    def encode_token(self, request, user=None, expiry=None, **token):
        """Encode a JWT
        """
        if expiry:
            token['exp'] = int(time.mktime(expiry.timetuple()))

        request.app.fire('on_token', request, token, user)
        return jwt.encode_json(token, request.config['SECRET_KEY'])

    def decode_token(self, request, token, key=None,
                     algorithm=None, **options):
        algorithm = algorithm or request.config['JWT_ALGORITHM']
        key = key or request.config['SECRET_KEY']
        try:
            return jwt.decode(token, key, algorithm=algorithm, options=options)
        except jwt.ExpiredSignature:
            request.app.logger.warning('JWT token has expired')
            raise Http401('Token')
        except jwt.DecodeError as exc:
            request.app.logger.warning(str(exc))
            raise Http401('Token')

    def create_token(self, request, user, **kwargs):  # pragma    nocover
        """Create a new token and store it
        """
        raise NotImplementedError