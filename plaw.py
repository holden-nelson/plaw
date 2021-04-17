'''
Plaw.py
'''
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

    def _call(self, endpoint):
        '''
        just calls the API with the parameters given. used exclusively by _call_api()
        :param endpoint: string of the endpoint being called.
        :return: the decoded JSON from response
        '''
        endpoint = self.BASE_URL + endpoint
        bearer = {
            'Authorization': 'Bearer ' + self.access_token
        }

        response = request('GET', endpoint, headers=bearer)
        if response.status_code == 401 or response.status_code == 400:
            raise InvalidToken('Access Token is Expired.')
        return response.json()

    def _call_api(self, endpoint):
        '''
        utility function for calling API. this is the one that other functions
        of the class will use. handles pagination, rate limiting,
        token refreshes.
        :param endpoint: string of the endpoint being called.
                         passed on to _call()
        :return: the decoded JSON from response
        '''
        try:
            return self._call(endpoint)
        except InvalidToken:
            self.access_token = self._refresh_access_token()
            return self._call(endpoint)
