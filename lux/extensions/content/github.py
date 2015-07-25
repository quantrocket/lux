import os
import hmac
import hashlib
from asyncio import create_subprocess_shell, subprocess

from pulsar.apps.wsgi import Json
from pulsar.utils.string import to_bytes
from pulsar import task, HttpException, PermissionDenied, BadRequest

import lux


class GithubHook(lux.Router):
    response_content_types = ['application/json']
    repo = None
    secret = None

    @task
    def post(self, request):
        data = request.body_data()

        if self.secret:
            try:
                self.validate(request)
            except Exception as exc:
                if hasattr(exc, 'status'):
                    raise
                else:
                    raise BadRequest

        event = request.get('HTTP_X_GITHUB_EVENT')
        data = self.handle_payload(request, event, data)
        return Json(data).http_response(request)

    def handle_payload(self, request, event, data):
        response = dict(success=True, event=event)
        if event == 'push':
            if self.repo and os.path.isdir(self.repo):
                command = 'cd %s; git symbolic-ref --short HEAD' % self.repo
                branch = yield from self.execute(command)
                branch = branch.split('\n')[0]
                response['command'] = self.command(branch)
                result = yield from self.execute(response['command'])
                response['result'] = result
            else:
                raise HttpException('Repo directory not valid', status=412)

        return response

    def validate(self, request):
        secret = to_bytes(self.secret)
        hub_signature = request.get('HTTP_X_HUB_SIGNATURE')

        if not hub_signature:
            raise PermissionDenied('No signature')

        sha_name, signature = hub_signature.split('=')
        if sha_name != 'sha1':
            raise PermissionDenied('Bad signature')

        payload = request.get('wsgi.input').read()
        sig = hmac.new(secret, msg=payload, digestmod=hashlib.sha1)

        if sig.hexdigest() != signature:
            raise PermissionDenied('Bad signature')

    def execute(self, command):
        p = yield from create_subprocess_shell(command,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
        b, _ = yield from p.communicate()
        return b.decode('utf-8')

    def command(self, branch):
        # git checkout HEAD path/to/your/dir/or/file
        return 'cd %s; git pull origin %s;' % (self.repo, branch)
