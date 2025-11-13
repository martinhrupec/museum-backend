from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view
import json
from django.http import JsonResponse

# Create your views here.

# django rest framework api way
@api_view(['GET'])
def hello_world(request):
    return Response({"message": "Hello from API!"})

# standard django way
def api_home(request, *args, **kwargs):
    body = request.body  # raw body as a byte string (of JSON data)
    #print("Request body:", body)
    #print("Request body type:", type(body))
    data = {}
    try:
        data = json.loads(body)  # try to parse JSON data
    except:
        pass
    #print("Data:", data)  # log the parsed data
    #print(data.keys())
    #print("Request headers:", request.headers)
    #print(type(request.headers))
    #print("Request headers as a dict:", dict(request.headers))
    #print(json.dumps(dict(request.headers), indent=4))

    # JsonResponse cannot serialize 'django.http.request.HttpHeaders' object. 
    # it can only serialize standard data types like dict, list, str, int, float, tuple etc.
    data["headers"] = dict(request.headers)
    #print("Request content type:", request.content_type)
    #print(type(request.content_type))
    data["content_type"] = request.content_type
    data["params"] = dict(request.GET)
    print("Data for JsonResponse:", data)
    #print("url query params:", request.GET)

    #return JsonResponse({"status": "API is running"})
    return JsonResponse(data)