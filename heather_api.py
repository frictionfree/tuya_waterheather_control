import requests

def get_device_details(device_id, access_token):
    # Define the API endpoint
    url = f"https://openapi.tuya.com/v1.1/iot-03/devices/{device_id}"
    
    # Set the headers including the access token for authentication
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Make the GET request to the Tuya API
    response = requests.get(url, headers=headers)
    
    # Check if the request was successful
    if response.status_code == 200:
        device_info = response.json().get('result', {})
        
        # Extract the IP address and local key from the response
        ip_address = device_info.get('ip', 'N/A')
        local_key = device_info.get('local_key', 'N/A')
        
        print(f"Device IP Address: {ip_address}")
        print(f"Device Local Key: {local_key}")
    else:
        print(f"Failed to retrieve device details. Status Code: {response.status_code}")
        print(f"Response: {response.text}")

# Example usage
device_id = "your_device_id_here"
access_token = "your_access_token_here"
get_device_details(device_id, access_token)
