import os
import unittest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('MYSQL_PASSWORD', '')

import app as app_module


class AppRoutesTest(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()

    def test_login_page_is_public(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_forgot_password_page_is_public(self):
        response = self.client.get('/forgot-password')
        self.assertEqual(response.status_code, 200)

    def test_complaints_api_requires_login(self):
        response = self.client.get('/api/complaints')
        self.assertEqual(response.status_code, 401)

    def test_admin_page_requires_admin_role(self):
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)

    def test_security_cookies_are_http_only_and_samesite_lax(self):
        self.assertTrue(app_module.app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(app_module.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

    def test_attachment_api_requires_login(self):
        response = self.client.get('/api/complaints/1/attachments')
        self.assertEqual(response.status_code, 401)

    def test_assignment_api_requires_admin_role(self):
        response = self.client.post(
            '/api/complaints/1/assignment',
            json={'assigned_admin_id': 1, 'due_at': '2026-12-01T12:00'}
        )
        self.assertEqual(response.status_code, 403)

    def test_separate_complaint_form_requires_login(self):
        response = self.client.get('/complaints/new')
        self.assertEqual(response.status_code, 302)


if __name__ == '__main__':
    unittest.main()
