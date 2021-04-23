# PLAW - Python Lightspeed API Wrapper

This module provides a pythonic interface to the Lightspeed API.

This is an incomplete project - I'm building another tool that depends on the Lightspeed API so I built this little wrapper to make it easier.

I've only implemented interfaces to the endpoints I'm using - ```Account```, ```Shop```, ```Employee```, and ```EmployeeHours```. It's possible I'll come back later and implement more, but not guaranteed.

I'd accept any contribution with open arms - just do me a favor and make sure you add tests. 
## Installation
```pip install plaw```

## Usage
The ```Plaw``` class contains all attributes and methods necessary to interact with the API. Most users would probably instantiate a new object like so:
```
>>> from plaw import Plaw

>>> client_id = # your client id from lightspeed
>>> client_secret = # your client secret from lightspeed

>>> api = Plaw(client_id, client_secret)
```
To make any real use of the API, you need to get a temp access code from Lightspeed in order to receive an access and refresh token. The temp code expires after 30 seconds, so it's likely this would take place in e.g. a Django view - but regardless:
```
>>> code = # temp access code
>>> api.get_tokens(code)
>>> api.fetch_account_id()
``` 
Once you have this information you can make requests through the interfaces. 
### Pagination
Pagination is sort of built-in to the interface. These interfaces are going to return a generator object, with each item in the generator being a page of results from your query. This makes requesting the next page of results very simple:
```
>>> all_employee_hours = api.employee_hours()
>>> next(all_employee_hours) # first page
{
    "@attributes": {
        "count": "4252",
        "offset": "0",
        "limit": "100"
    },
    "EmployeeHours": [
        {
            "employeeHoursID": "2",
            "checkIn": "2014-02-19T23:08:08+00:00",
            "checkOut": "2014-02-19T23:08:22+00:00",
            "employeeID": "4",
            "shopID": "1"
        },
    ...

>>> next(all_employee_hours) # second page
{
    "@attributes": {
        "count": "4252",
        "offset": "100",
        "limit": "100"
    },
    "EmployeeHours": [
        {
            "employeeHoursID": "202",
            "checkIn": "2014-05-24T16:40:00+00:00",
            "checkOut": "2014-05-25T00:10:27+00:00",
            "employeeID": "2",
            "shopID": "1"
        },
    ...
```
etc.
### Parameters
Each interface takes an optional ```params``` argument that expects a dictionary of query string parameters.
```
>>> params = {
...   'shopID': '1'
... }

>>> ny_store = api.shop(params)
>>> next(ny_store)
{
    "@attributes": {
        "count": "1",
        "offset": "0",
        "limit": "100"
    },
    "Shop": {
        "shopID": "1",
        "name": "New York Storefront",
    ...
```
### Timestamps
Pass in all timestamps as datetime objects - this library will convert them to iso format for you. 
The Lightspeed API actually accepts timezone encoded timestamps, but will always return UTC. 
### Query Operators
The default operator for any query is '=', but you can specify others to make your searches more powerful. If your intention is the = operator, just put the value in the params dict like the Parameters section above. If you'd like to make use of other operators, put the operators in a list with the values you're operating on, like so:
```
>>> from datetime import datetime
>>> import pytz

>>> jan_first = pytz.timezone('America/Boise').localize(datetime(2021, 1, 1), is_dst=None)
>>> feb_first = pytz.timezone('America/Boise').localize(datetime(2021, 2, 1), is_dst=None)

>>> params = {
...     'checkIn': ['><', jan_first, feb_first]
... }

>>> all_january_shifts = api.employee_hours(params)
>>> next(all_january_shifts)
{
    "@attributes": {
        "count": "116",
        "offset": "0",
        "limit": "100"
    },
    "EmployeeHours": [
        {
            "employeeHoursID": "4453",
            "checkIn": "2021-01-02T16:31:30+00:00",
            "checkOut": "2021-01-02T23:53:41+00:00",
            "employeeID": "55",
            "shopID": "1"
        },
    ...
```
### Relations
You're always welcome to load relations manually in your params. The ```Employee``` endpoint has an option ```load_contact``` that, when True, loads the Contact relation.