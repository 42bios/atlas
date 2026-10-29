import socket
import unittest
from unittest.mock import patch
from addin_manager import AddinManager

class DiagnosticsTests(unittest.TestCase):
    def test_dns_and_redaction(self):
        with patch('socket.getaddrinfo', side_effect=socket.gaierror()):
            message=AddinManager.failure_message({'config':{'upstreamUrl':'https://private.example'}})
        self.assertIn('DNS',message)
        self.assertNotIn('private.example',message)
    def test_safe_categories(self):
        for exception,label in [('SSLCertVerificationError','TLS'),('HTTPError','credentials'),('TimeoutError','timed out'),('ConnectionRefusedError','refused')]:
            result=AddinManager.failure_message({},(exception+' SECRET_VALUE').encode())
            self.assertIn(label,result)
            self.assertNotIn('SECRET_VALUE',result)
    def test_unknown_output_not_exposed(self):
        self.assertNotIn('SECRET_VALUE',AddinManager.failure_message({},b'SECRET_VALUE'))
