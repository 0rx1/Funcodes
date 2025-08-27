import requests
import json

config_names = ["ExampleCompany1", "ExampleCompany2", "Groupe Montclair"]  # Add the names you want to pick here

# Onion URL for the JSON data
url = 'http://noname2j6zkgnt7ftxsjju5tfd3s45s4i3egq5bqtl72kgum4ldc6qyd.onion/data/all.json'


session = requests.Session()
session.proxies = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

try:
    # Fetch the JSON over Tor
    response = session.get(url, timeout=60)  # Increased timeout for Tor
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    print(f"Error fetching data over Tor: {e}")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    exit(1)

target_names = []

print("Fetched JSON structure (first 500 chars):", json.dumps(data)[:500])
print("...")

if isinstance(data, list):
    for item in data:
        target_name = item.get('name') or item.get('title') or item.get('company') or item.get('victim')
        if target_name:
            target_names.append(target_name)
elif isinstance(data, dict):
    if 'data' in data and isinstance(data['data'], list):
        for item in data['data']:
            target_name = item.get('name') or item.get('title') or item.get('company') or item.get('victim')
            if target_name:
                target_names.append(target_name)
    else:
        target_name = data.get('name') or data.get('title') or data.get('company') or data.get('victim')
        if target_name:
            target_names.append(target_name)

# Remove duplicates if any
target_names = list(set(target_names))

# Check for matches with config list
matches = set(target_names) & set(config_names)

if matches:
    print("Matching target names found:")
    for match in matches:
        print(f"- {match}")
else:
    print("No matching target names found in the config list.")

print("\nAll extracted target names from JSON:")
for name in target_names:
    print(f"- {name}")
