import json
import urllib.request
import urllib.error

url = 'http://127.0.0.1:8011/api/v1/auth/register'
data = {
    'email': 'test3@example.com',
    'password': 'Password1!',
    'full_name': 'Test User'
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print("Success:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode('utf-8'))
