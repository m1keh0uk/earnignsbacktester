import requests
import pandas as pd
import json
import os

def fetch_earningcalls(symbol, data_dir):
    # Ensure the directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    # Set the path to save the file
    save_path = os.path.join(data_dir, f"{symbol}_earnings.json")

    # Check if data is already saved locally
    if os.path.exists(save_path):
        with open(save_path, 'r') as file:
            data = json.load(file)
        return pd.DataFrame(data)
    
    # If not, fetch from API and save locally
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": "OQ0K6DQV3DGAMH2S"
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()["quarterlyEarnings"]
    
    with open(save_path, 'w') as file:
        json.dump(data, file)
    
    return pd.DataFrame(data)

if __name__ == "__main__":
    BASE_URL = "https://www.alphavantage.co/query"
    symbol = input("Enter ticker: ").strip().upper()
    data_dir = "data/earnings"  # Directory where the data will be saved
    print(fetch_earningcalls(symbol, data_dir))
