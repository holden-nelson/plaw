import random, string
from unittest import TestCase
from unittest.mock import patch

from plaw import Plaw, InvalidGrant, InvalidToken

class TestPlaw(TestCase):

    # helper
    def generate_random_token(self, length=16):
        return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase
                                     + string.digits) for _ in range(length))

    def setUp(self):
        self.test_api = Plaw(client_id=self.generate_random_token(),
                                     client_secret=self.generate_random_token(),
                                     account_id=self.generate_random_token(length=5),
                                     refresh_token=self.generate_random_token(),
                                     access_token=self.generate_random_token())

    @patch('plaw.request')
    def test_refresh_access_token_successfully_saves_new_token(self, mock_request):
        mock_request.return_value.status_code = 200

        mocked_response = {
            'access_token': self.generate_random_token(),
            'expires_in': 3600,
            'token_type': 'bearer',
            'scope': 'employee:all systemuserid:152663'
        }
        mock_request.return_value.json.return_value = mocked_response

        new_refresh_token = self.test_api.__refresh_access_token__()

        self.assertEqual(new_refresh_token, mocked_response['access_token'])

    @patch('plaw.request')
    def test_refresh_access_token_raises_on_invalid_token(self, mock_request):
        mock_request.return_value.status_code = 400

        with self.assertRaises(InvalidGrant):
            self.test_api.__refresh_access_token__()