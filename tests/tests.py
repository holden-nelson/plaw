import random, string
from datetime import datetime
import pytz
import json
import types

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

        decoded_response = self.test_api._call('/API/Account.json', params=None)

        self.assertEqual(decoded_response, mocked_response)

    @patch('plaw.request')
    def test_call_raises_on_invalid_token(self, mock_request):
        mock_request.return_value.status_code = 401

        with self.assertRaises(InvalidToken):
            self.test_api._call('/API/Account.json', params=None)

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

    @patch('plaw.Plaw._call')
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


    @patch('plaw.Plaw._call')
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



    @patch('plaw.Plaw._call')
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

    def test_strip_attributes_strips_attributes(self):
        with open('pagination_test_file.json') as jf:
            example_responses = json.load(jf)

        for response in example_responses:
            stripped_response = self.test_api._strip_attributes(response)
            self.assertFalse(isinstance(stripped_response, dict))
            self.assertTrue(isinstance(stripped_response, list))
            self.assertEqual(response['EmployeeHours'], stripped_response)

    def test_strip_attributes_puts_solo_responses_into_lists(self):
        example_solo_response = {
            '@attributes': None,
            'Endpoint': {
                'Example Response': None
            }
        }

        stripped_response = self.test_api._strip_attributes(example_solo_response)

        self.assertFalse(isinstance(stripped_response, dict))
        self.assertTrue(isinstance(stripped_response, list))
        self.assertEqual(example_solo_response['Endpoint'], stripped_response[0])

    @patch('plaw.Plaw._call')
    def test_combine_paginated_response_combines_paginated_response(self, mock_call):
        with open('pagination_test_file.json') as jf:
            mocked_responses = json.load(jf)
        mock_call.side_effect = mocked_responses

        test_date = pytz.timezone('America/Boise').localize(datetime(2021, 2, 1, 1), is_dst=None)
        shifts_since_february = self.test_api._call_api(f'API/Account/{self.test_api.account_id}/EmployeeHours.json',
                                                        params={
                                                            'checkIn': ['>', test_date]
                                                        })

        combined_response = self.test_api._combine_paginated_response(shifts_since_february)
        expected_response = []
        for response in mocked_responses:
            expected_response += response['EmployeeHours']

        self.assertTrue(isinstance(combined_response, list))
        self.assertEqual(combined_response, expected_response)


    @patch('plaw.Plaw._strip_attributes')
    @patch('plaw.Plaw._call_api')
    def test_account_returns_account_info(self, mocked_call, mocked_strip):
        # mocked call is necessary because it tries to evaluate before _strip_attributes does
        mocked_strip.return_value = [{
            "accountID": "12345",
            "name": "Test Store",
            "link": {
                "@attributes": {
                    "href": "/API/Account/12345"
                }
            }
        }]

        account_info = self.test_api.account()

        self.assertTrue(isinstance(account_info, dict))
        self.assertFalse(isinstance(account_info, list))
        self.assertFalse('link' in account_info)

    @patch('plaw.Plaw._combine_paginated_response')
    def test_shop_returns_shop_info(self, mocked_combine):
        example_shop_list = [
            {
                "shopID": "1",
                "name": "Test Shop 1",
                "serviceRate": "0",
                "timeZone": "US/Mountain",
                "taxLabor": "false",
                "labelTitle": "Shop Name",
                "labelMsrp": "false",
                "archived": "false",
                "timeStamp": "2021-01-03T22:06:01+00:00",
                "companyRegistrationNumber": "",
                "vatNumber": "",
                "zebraBrowserPrint": "false",
                "contactID": "4",
                "taxCategoryID": "2",
                "receiptSetupID": "1",
                "ccGatewayID": "4",
                "gatewayConfigID": "2c3ee5bd-ff2c-4ce1-a7b4-0adsdafdcd82",
                "priceLevelID": "1"
            },
            {
                "shopID": "2",
                "name": "Test Shop 2",
                "serviceRate": "0",
                "timeZone": "America/Denver",
                "taxLabor": "false",
                "labelTitle": "No Title",
                "labelMsrp": "false",
                "archived": "false",
                "timeStamp": "2021-01-12T22:04:53+00:00",
                "companyRegistrationNumber": "",
                "vatNumber": "",
                "zebraBrowserPrint": "false",
                "contactID": "1214",
                "taxCategoryID": "3",
                "receiptSetupID": "2",
                "ccGatewayID": "0",
                "gatewayConfigID": "54f8edb4-3c5e-4c2a-b137-ddafsfad17b70",
                "priceLevelID": "1"
            }
        ]
        mocked_combine.return_value = example_shop_list

        shop_info = self.test_api.shop()

        self.assertEqual(shop_info, example_shop_list)

    @patch('plaw.Plaw._combine_paginated_response')
    def test_shop_handles_requests_for_pagination(self, mocked_combine):
        # the user can choose to paginate responses by passing in paginated=True to the function
        # if they do they'll be given a generator to get their responses from
        # if they don't they'll be given the list of dicts

        # paginated False
        combined_shop_list = [
            {
                "shopID": "1",
                "name": "Test Shop 1",
                "serviceRate": "0",
                "timeZone": "US/Mountain",
                "taxLabor": "false",
                "labelTitle": "Shop Name",
                "labelMsrp": "false",
                "archived": "false",
                "timeStamp": "2021-01-03T22:06:01+00:00",
                "companyRegistrationNumber": "",
                "vatNumber": "",
                "zebraBrowserPrint": "false",
                "contactID": "4",
                "taxCategoryID": "2",
                "receiptSetupID": "1",
                "ccGatewayID": "4",
                "gatewayConfigID": "2c3ee5bd-ff2c-4ce1-a7b4-0adsdafdcd82",
                "priceLevelID": "1"
            },
            {
                "shopID": "2",
                "name": "Test Shop 2",
                "serviceRate": "0",
                "timeZone": "America/Denver",
                "taxLabor": "false",
                "labelTitle": "No Title",
                "labelMsrp": "false",
                "archived": "false",
                "timeStamp": "2021-01-12T22:04:53+00:00",
                "companyRegistrationNumber": "",
                "vatNumber": "",
                "zebraBrowserPrint": "false",
                "contactID": "1214",
                "taxCategoryID": "3",
                "receiptSetupID": "2",
                "ccGatewayID": "0",
                "gatewayConfigID": "54f8edb4-3c5e-4c2a-b137-ddafsfad17b70",
                "priceLevelID": "1"
            }
        ]
        mocked_combine.return_value = combined_shop_list
        shop_info = self.test_api.shop()
        self.assertTrue(isinstance(shop_info, list))

        # paginated True
        shop_info = self.test_api.shop(paginated=True)
        self.assertTrue(isinstance(shop_info, types.GeneratorType))


    def test_employee_returns_employee_info(self):
        pass

    def test_employee_hours_returns_employee_hours_info(self):
        pass





