'''
Plaw.py
'''
from datetime import datetime
from requests import request

class InvalidGrant(Exception):
    pass

class InvalidToken(Exception):
    pass

class Plaw():

    AUTH_URL = 'https://cloud.lightspeedapp.com/oauth/access_token.php'
    BASE_URL = 'https://api.lightspeedapp.com/'

    def __init__(self, client_id, client_secret,
                 account_id=None, refresh_token=None, access_token=None):

        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.refresh_token = refresh_token
        self.access_token = access_token


    def _refresh_access_token(self):
        '''
        uses refresh token to retrieve a new access token
        :return: new access token
        '''
        payload = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
        }

        response = request('POST', self.AUTH_URL, data=payload)

        if response.status_code == 400:
            raise InvalidGrant('Refresh token is invalid. Perhaps it was revoked?')
        return response.json()['access_token']

    def _call(self, endpoint, params):
        '''
        just calls the API with the parameters given. used exclusively by _call_api()
        :param endpoint: string of the endpoint being called.
        :param params: dict of query parameters used in api call
        :return: the decoded JSON from response
        '''
        endpoint = self.BASE_URL + endpoint
        bearer = {
            'Authorization': 'Bearer ' + self.access_token
        }

        response = request('GET', endpoint, headers=bearer, params=params)
        if response.status_code == 401 or response.status_code == 400:
            raise InvalidToken('Access Token is Expired.')
        return response.json()

    def _call_api(self, endpoint, params=None):
        '''
        utility function for calling API. this is the one that other functions
        of the class will use. handles:
            Token refreshes
            Converting datetimes to iso format
            Pagination
            Rate Limiting (soon)

        :param endpoint: string of the endpoint being called.
                         passed on to _call()
        :param params: dict of query parameters used in the api call
        :return: a generator for each page of the decoded JSON from response
        '''
        if params:
            # look for datetimes to convert and query ops
            for key, param in params.items():
                # datetimes may not have query op passed in
                if isinstance(param, datetime):
                    params[key] = param.isoformat()

                # datetimes may be passed in with query op
                if isinstance(param, list):
                    if isinstance(param[1], datetime):
                        params[key][1] = param[1].isoformat()

                    # necessary for between date lookups
                    if len(param) == 3:
                        if isinstance(param[2], datetime):
                            params[key][2] = param[2].isoformat()

                    # also, join the list
                    params[key] = ','.join(params[key])
        else:
            # we make an empty params dict to make pagination simpler
            params = dict()

        while True:
            try:
                response = self._call(endpoint, params)
                yield response
            except InvalidToken: # refreshing access token when necessary
                self.access_token = self._refresh_access_token()
                response =  self._call(endpoint, params)
                yield response

            if 'offset' in response['@attributes']:
                count = int(response['@attributes']['count'])
                offset = int(response['@attributes']['offset'])

                if count - offset > 100:
                    params['offset'] = str(offset + 100)

                else:
                    break
            else:
                break

    def _strip_attributes(self, response):
        '''
        strips attributes info from json response
        also wraps a list around solo responses
        # TODO move that functionality to its own function
        :param response: the decoded json from the api
        :return: list of dicts from response
        '''
        for key in response.keys():
            if key != '@attributes':
                # if only one result there will be no list in JSON
                if isinstance(response[key], dict):
                    return [response[key]]
                else:
                    return response[key]

    def _combine_paginated_response(self, paginated_response):
        '''
        takes a generator object and returns the full un-paginated response
        :param paginated_response: the paginated response from _call_api
        :return: the combined response list
        '''
        combined_response = []
        for page in paginated_response:
            combined_response += self._strip_attributes(page)

        return combined_response


    def account(self):
        '''
        interface for the account endpoint
        :return: dict of account info - accountID and name
        '''
        # account is special in that we don't return a list, we just return a dict
        # and we also remove the 'link' entry

        account_info = self._strip_attributes(next(self._call_api('API/Account.json')))
        del account_info[0]['link']
        return account_info[0]

    def shop(self, params=None, paginated=False):
        '''
        interface for the shop endpoint
        :return: depends on paginated flag.
                 if False (default) returns list of dicts of shop info
                 if True returns a generator to get results from
        '''
        paginated_response = self._call_api(f'API/Account/{self.account_id}/Shop.json',
                                            params)
        if paginated:
            return paginated_response
        else:
            return self._combine_paginated_response(paginated_response)

    def employee(self):
        '''
        interface for the employee endpoint
        :return:
        '''

    def employee_hours(self):
        '''
        interface for the employeeHours endpoint
        :return:
        '''

