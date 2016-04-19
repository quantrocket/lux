from tests import web


class AuthTest(web.WebsiteTest):

    def _get_code(self, message):
        idx = message.find('/reset-password/')
        self.assertTrue(idx)
        msg = message[idx+16:]
        idx = msg.find(' ')
        return msg[:idx]

    async def test_html_signup(self):
        request = await self.webclient.get('/signup')
        html = self.html(request.response, 200)
        self.assertTrue(html)

    async def test_signup(self):
        data = await self._signup()
        self.assertTrue('email' in data)

    async def test_signup_error(self):
        data = {'username': 'djkhvbdf'}
        request = await self.webclient.post('/signup',
                                            body=data,
                                            content_type='application/json')
        self.json(request.response, 403)

    async def test_signup_error_api(self):
        data = {'username': 'djkhvbdf'}
        request = await self.client.post('/authorizations/signup',
                                         body=data,
                                         content_type='application/json')
        self.assertValidationError(request.response)

    async def test_signup_confirmation(self):
        data = await self._signup()
        reg = await self._get_registration(data['email'])
        self.assertTrue(reg.id)
        request = await self.webclient.get('/signup/%s' % reg.id)
        doc = self.bs(request.response, 200)
        body = doc.find('body')
        self.assertTrue(body)
        # await self._check_body(reg, body)

    # PASSWORD RESET
    async def test_reset_password_get(self):
        request = await self.webclient.get('/reset-password')
        bs = self.bs(request.response, 200)
        form = bs.find('lux-form')
        self.assertTrue(form)

    async def test_reset_password_fail(self):
        cookie, data = await self._cookie_csrf('/reset-password')
        request = await self.webclient.post('/reset-password',
                                            body=data,
                                            content_type='application/json',
                                            cookie=cookie)
        self.assertValidationError(request.response, 'email')
        data['email'] = 'dvavf@sdvavadf.com'
        request = await self.webclient.post('/reset-password',
                                            body=data,
                                            content_type='application/json',
                                            cookie=cookie)
        self.assertValidationError(request.response,
                                   text="Can't find user, sorry")

    async def test_reset_password_success(self):
        cookie, data = await self._cookie_csrf('/reset-password')
        data['email'] = 'toni@foo.com'
        request = await self.webclient.post('/reset-password',
                                            body=data,
                                            content_type='application/json',
                                            cookie=cookie)
        data = self.json(request.response, 200)
        self.assertTrue(data['email'], 'toni@foo.com')
        mail = None
        for msg in self.app._outbox:
            if msg.to == 'toni@foo.com':
                mail = msg
                break
        self.assertTrue(mail)
        self.assertEqual(mail.sender, 'admin@lux.com')
        code = self._get_code(mail.message)
        self.assertTrue(code)

    async def _(self, reg, body):
        login = body.find_all('a')
        self.assertEqual(len(login), 1)
        text = login[0].prettify()
        self.assertTrue(self.app.config['LOGIN_URL'] in text)
        text = body.get_text()
        self.assertTrue('You have confirmed your email' in text)
        request = await self.client.get('/signup/%s' % reg.id)
        html = self.html(request.response, 410)
        self.assertTrue(html)

    async def __test_confirm_signup(self):
        data = await self._signup()
        reg = await self.app.green_pool.submit(self._get_registration,
                                               data['email'])
        api_url = '/authorizations/signup/%s' % reg.id
        request = await self.client.options(api_url)
        self.assertEqual(request.response.status_code, 200)
        #
        request = await self.client.post(api_url)
        data = self.json(request.response, 200)
        self.assertTrue(data['success'])
        request = await self.client.post(api_url)
        self.json(request.response, 410)
