import requests

endpoint = "http://localhost:8000/api/"
#response = requests.get(endpoint)
#print("Json:", response.json())
#print("Status Code:", response.status_code)
#print("Headers:", response.headers)
#print("Content:", response.content)
#print("Elapsed Time:", response.elapsed)
#print("Request URL:", response.url)
#print("Request Method:", response.request.method)
#print("Request Headers:", response.request.headers)
#print("Request Body:", response.request.body)
#print("Is Successful:", response.ok)
#print("Cookies:", response.cookies)
#print("History:", response.history)
#print("Encoding:", response.encoding)
#print("Text:", response.text)

# Http protocol is not designed to send a body with a GET request,
# this is just to test how our api_home view handles it.
"""
Section 4.3.1 - GET:
"A payload within a GET request message has no defined semantics; 
sending a payload body on a GET request might cause some existing 
implementations to reject the request."
"""

response = requests.get(endpoint, params={"abc": 123}, json={"query": "hello world"})
print("Json:", response.json())
#print("Status Code:", response.status_code)
#print("Headers:", response.headers)
#print("Content:", response.content)
#print("Request Headers:", response.request.headers)
#print("Request Body:", response.request.body)
#print("Text:", response.text)