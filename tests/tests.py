import random, string
from unittest import TestCase
from unittest.mock import patch, PropertyMock

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

        new_refresh_token = self.test_api._refresh_access_token()

        self.assertEqual(new_refresh_token, mocked_response['access_token'])

    @patch('plaw.request')
    def test_refresh_access_token_raises_on_revoked_access(self, mock_request):
        mock_request.return_value.status_code = 400

        with self.assertRaises(InvalidGrant):
            self.test_api._refresh_access_token()

    @patch('plaw.request')
    def test_call_returns_decoded_json(self, mock_request):
        mock_request.return_value.status_code = 200
        mocked_response = {
            '@attributes': {
                'count': '1'
            },
            'Account': {
                'accountID': '12345',
                'name': 'Test Store for API Testing',
                'link': {
                    '@attributes': {
                        'href': '/API/Account/12345'
                    }
                }
            }
        }
        mock_request.return_value.json.return_value = mocked_response

        decoded_response = self.test_api._call('/API/Account.json')

        self.assertEqual(decoded_response, mocked_response)

    @patch('plaw.request')
    def test_call_raises_on_invalid_token(self, mock_request):
        mock_request.return_value.status_code = 401

        with self.assertRaises(InvalidToken):
            self.test_api._call('/API/Account.json')

    @patch('plaw.Plaw._call')
    @patch('plaw.Plaw._refresh_access_token')
    def test_call_api_refreshes_access_token_if_necessary(self, mock_refresh, mock_call):
        new_access_token = self.generate_random_token()
        mock_refresh.return_value = new_access_token

        refreshed_call_response = {
            '@attributes': {
                'count': '1'
            },
            'Account': {
                'accountID': '12345',
                'name': 'Test Store for API Testing',
                'link': {
                    '@attributes': {
                        'href': '/API/Account/12345'
                    }
                }
            }
        }
        mock_call.side_effect = [InvalidToken, refreshed_call_response]

        decoded_response = self.test_api._call_api('/API/Account.json')

        self.assertEqual(new_access_token, self.test_api.access_token)
        self.assertEqual(decoded_response, refreshed_call_response)

    def test_call_api_handles_rate_limiting(self):
        pass

    def test_call_api_handles_pagination(self):
        pass

