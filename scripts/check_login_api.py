import requests

url = "http://localhost:8000/accounts/token/"
data = {"username": "dilnaz", "password": "123"}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
