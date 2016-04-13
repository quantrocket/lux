"""HTML views for authenticating users
"""
from pulsar import Http404, HttpRedirect
from pulsar.apps.wsgi import route

from lux.core import Router, raise_http_error
from lux.forms import WebFormRouter, Layout, Fieldset, Submit

from .user import AuthenticationError, login, logout, signup
from . import forms


class Login(WebFormRouter):
    """Web login view with post handler
    """
    template = 'login.html'
    default_form = Layout(forms.LoginForm,
                          Fieldset(all=True),
                          Submit('Login', disabled="form.$invalid"),
                          model='login',
                          showLabels=False,
                          resultHandler='login')

    def get(self, request):
        if request.cache.user.is_authenticated():
            raise HttpRedirect('/')
        return super().get(request)

    def post(self, request):
        return login(request, self.fclass)


class Logout(Router):
    response_content_types = ['application/json']

    def post(self, request):
        return logout(request)


class SignUp(WebFormRouter):
    """Display a signup form anf handle signup
    """
    template = 'signup.html'
    confirmation_template = 'registration/confirmation.html'
    default_form = Layout(forms.CreateUserForm,
                          Fieldset('username', 'email', 'password',
                                   'password_repeat'),
                          Submit('Sign up',
                                 disabled="form.$invalid"),
                          showLabels=False,
                          directive='user-form',
                          resultHandler='signUp')

    def get(self, request):
        if request.cache.user.is_authenticated():
            raise HttpRedirect('/')
        return super().get(request)

    def post(self, request):
        return signup(request, self.fclass)

    @route('<key>')
    def confirmation(self, request):
        key = request.urlargs['key']
        url = 'authorizations/signup/%s' % key
        api = request.app.api(request)
        response = api.post(url)
        raise_http_error(response)
        return self.html_response(request, '', self.confirmation_template)

    @route('confirmation/<username>')
    def new_confirmation(self, request):
        username = request.urlargs['username']
        api = request.app.api(request)
        response = api.post('authorizations/%s' % username)
        raise_http_error(response)
        return self.html_response(request, '', self.confirmation_template)


class ForgotPassword(WebFormRouter):
    """Manage forget passwords routes
    """
    default_form = Layout(forms.EmailForm,
                          Fieldset(all=True),
                          Submit('Submit'),
                          showLabels=False,
                          resultHandler='passwordRecovery')

    reset_form = Layout(forms.PasswordForm,
                        Fieldset(all=True),
                        Submit('Change Password'),
                        showLabels=False,
                        resultHandler='passwordChanged')

    template = 'forgot.html'
    reset_template = 'reset_password.html'

    @route('<key>')
    def get_reset_form(self, request):
        key = request.urlargs['key']
        try:
            user = request.cache.auth_backend.get_user(request, auth_key=key)
        except AuthenticationError as exc:
            session = request.cache.session
            session.error('The link is no longer valid, %s' % exc)
            return request.redirect('/')
        if not user:
            raise Http404
        form = self.reset_form(request)
        if self.form_action:
            action = self.form_action.copy()
            action['path'] = '%s/%s' % (action['path'], key)
        else:
            action = request.full_path()
        html = form.as_form(action=action,
                            enctype='multipart/form-data',
                            method='post')
        return self.html_response(request, html, self.reset_template)


class ComingSoon(WebFormRouter):
    release = 'release'
    template = 'comingsoon.html'
    default_form = Layout(forms.EmailForm,
                          Fieldset(all=True),
                          Submit('Get notified'),
                          showLabels=False)
