import random, string
from datetime import datetime
import pytz
import json
import types

from unittest import TestCase
from unittest.mock import patch

from plaw.wrapper import Plaw, InvalidGrant, InvalidToken

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

    @patch('plaw.wrapper.request')
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

    @patch('plaw.wrapper.request')
    def test_refresh_access_token_raises_on_revoked_access(self, mock_request):
        mock_request.return_value.status_code = 400

        with self.assertRaises(InvalidGrant):
            self.test_api._refresh_access_token()

    @patch('plaw.wrapper.request')
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

        decoded_response = self.test_api._call('/API/Account.json', params=None)

        self.assertEqual(decoded_response, mocked_response)

    @patch('plaw.wrapper.request')
    def test_call_raises_on_invalid_token(self, mock_request):
        mock_request.return_value.status_code = 401

        with self.assertRaises(InvalidToken):
            self.test_api._call('/API/Account.json', params=None)

    @patch('plaw.wrapper.Plaw._call')
    @patch('plaw.wrapper.Plaw._refresh_access_token')
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
                        'href': '/API/Account/12345T'
                    }
                }
            }
        }
        mock_call.side_effect = [InvalidToken, refreshed_call_response]

        response_gen = self.test_api._call_api('/API/Account.json')
        decoded_response = next(response_gen)

        self.assertEqual(new_access_token, self.test_api.access_token)
        self.assertEqual(decoded_response, refreshed_call_response)

    @patch('plaw.wrapper.Plaw._call')
    def test_call_api_converts_datetimes_to_iso(self, mock_call):
        test_date = pytz.timezone('America/Boise').localize(datetime(2021, 1, 1, 10, 58), is_dst=None)

        # without query op
        next(self.test_api._call_api(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                     params={
                                         'checkIn': test_date
                                     }))

        mock_call.assert_called_with(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                     {
                                         'checkIn': f'{test_date.isoformat()}'
                                     })

        # with query op
        next(self.test_api._call_api(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                params={
                                    'checkIn': ['>', test_date]
                                }))

        mock_call.assert_called_with(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                     {
                                         'checkIn': f'>,{test_date.isoformat()}'
                                     })


    @patch('plaw.wrapper.Plaw._call')
    def test_call_api_handles_query_ops(self, mocked_call):
        # the default operator is =
        # so if the user intends equals they don't pass in a query op
        # if they intend another op they pass in a list, with the op first

        equals_params = {
            'shopID': '1'
        }
        next(self.test_api._call_api(f'API/Account/{self.test_api.account_id}/Shop.json',
                                                  equals_params))

        mocked_call.assert_called_with(f'API/Account/{self.test_api.account_id}/Shop.json',
                                     {
                                         'shopID': '1'
                                     })

        less_than_params = {
            'shopID': ['<', '3']
        }

        next(self.test_api._call_api(f'API/Account/{self.test_api.account_id}/Shop.json',
                                                  less_than_params))
        mocked_call.assert_called_with(f'API/Account/{self.test_api.account_id}/Shop.json',
                                       {
                                           'shopID': '<,3'
                                       })



    @patch('plaw.wrapper.Plaw._call')
    def test_call_api_handles_pagination(self, mock_call):
        with open('pagination_test_file.json') as jf:
            mocked_responses = json.load(jf)
        mock_call.side_effect = mocked_responses

        test_date = pytz.timezone('America/Boise').localize(datetime(2021, 2, 1, 1), is_dst=None)
        shifts_since_february = self.test_api._call_api(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                                        params={
                                                            'checkIn': ['>', test_date]
                                                        })

        self.assertTrue(isinstance(shifts_since_february, types.GeneratorType))

        first_page = next(shifts_since_february)
        self.assertEqual('0', first_page['@attributes']['offset'])
        self.assertEqual(first_page, mocked_responses[0])

        second_page = next(shifts_since_february)
        self.assertEqual('100', second_page['@attributes']['offset'])
        self.assertEqual(second_page, mocked_responses[1])

        third_page = next(shifts_since_february)
        self.assertEqual('200', third_page['@attributes']['offset'])
        self.assertEqual(third_page, mocked_responses[2])

        with self.assertRaises(StopIteration):
            next(shifts_since_february)

    def test_call_api_handles_rate_limiting(self):
        # so
        # LS uses a leaky bucket algorithm to handle rate limiting
        # The current bucket use is given in the X-LS-API-Bucket-Level header
        # and the current drip rate is given in X-LS-API-Drip-Rate
        # LS will send a 429 response if we are being rate limited

        # tabling this for now
        pass

    @patch('plaw.wrapper.request')
    def test_get_tokens_saves_new_tokens(self, mocked_request):
        test_access_token = self.generate_random_token()
        test_refresh_token = self.generate_random_token()
        test_code = self.generate_random_token()

        mocked_request.return_value.json.return_value = {
            'access_token': test_access_token,
            'expires_in': 1800,
            'token_type': 'bearer',
            'scope': f'employee:all systemuserid:{self.generate_random_token(length=5)}',
            'refresh_token': test_refresh_token
        }

        self.test_api.get_tokens(test_code)

        self.assertEqual(self.test_api.access_token, test_access_token)
        self.assertEqual(self.test_api.refresh_token, test_refresh_token)
        mocked_request.assert_called_with('POST', self.test_api.AUTH_URL, data={
            'client_id': self.test_api.client_id,
            'client_secret': self.test_api.client_secret,
            'code': test_code,
            'grant_type': 'authorization_code'
        })

    @patch('plaw.wrapper.Plaw.account')
    def test_fetch_account_id_saves_account_id(self, mocked_account):
        mocked_account.return_value = {
            "accountID": "67890",
            "name": "Test Account",
            "link": {
                "@attributes": {
                    "href": "/API/Account/67890"
                }
            }
        }

        self.test_api.fetch_account_id()

        self.assertTrue(self.test_api.account_id, '67890')


    @patch('plaw.wrapper.Plaw._call')
    def test_account_returns_account_info(self, mocked_call):
        # mocked call is necessary because it tries to evaluate before _strip_attributes does
        mocked_call.return_value = {
            '@attributes': {
                'count': '1'
            },
            'Account': {
                'accountID': '12345',
                'name': 'Test Account',
                'link': {
                    '@attributes': {
                        'href': '/API/Account/12345'
                    }
                }
            }
        }

        account_info = self.test_api.account()

        self.assertTrue(isinstance(account_info, dict))
        self.assertFalse(isinstance(account_info, types.GeneratorType))

    @patch('plaw.wrapper.Plaw._call')
    def test_shop_returns_shop_info(self, mocked_call):
        with open('shop_test_file.json') as jf:
            test_shop_info = json.load(jf)
        mocked_call.return_value = test_shop_info

        shop_info = self.test_api.shop()

        self.assertTrue(isinstance(shop_info, types.GeneratorType))
        self.assertEqual(next(shop_info), test_shop_info)

    @patch('plaw.wrapper.Plaw._call')
    def test_employee_returns_employee_info(self, mocked_call):
        with open('employee_test_file.json') as jf:
            test_employee_info = json.load(jf)[0]
        mocked_call.return_value = test_employee_info

        employee_info = self.test_api.employee()

        self.assertTrue(isinstance(employee_info, types.GeneratorType))
        self.assertEqual(next(employee_info), test_employee_info)

    @patch('plaw.wrapper.Plaw._call')
    def test_employee_loads_contact_relation(self, mocked_call):
        with open('employee_test_file.json') as jf:
            test_employee_info = json.load(jf)[1]
        mocked_call.return_value = test_employee_info

        employee_info = self.test_api.employee(load_contact=True)

        self.assertTrue(isinstance(employee_info, types.GeneratorType))
        self.assertEqual(next(employee_info), test_employee_info)
        mocked_call.assert_called_with(f'API/Account/{self.test_api.account_id}/Employee.json',
                                       {
                                           'load_relations': json.dumps(['Contact'])
                                       })

    @patch('plaw.wrapper.Plaw._call')
    def test_employee_hours_returns_employee_hours_info(self, mocked_call):
        with open('employee_hours_test_file.json') as jf:
            test_employee_hours_info = json.load(jf)
        mocked_call.return_value = test_employee_hours_info

        employee_hours_info = self.test_api.employee_hours()

        self.assertTrue(isinstance(employee_hours_info, types.GeneratorType))
        self.assertEqual(next(employee_hours_info), test_employee_hours_info)
