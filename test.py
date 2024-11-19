import requests
import pandas as pd

# Define parameters for the request
params = {
    "function": "EARNINGS",
    "symbol": "KO",
    "apikey": "36ZEALV22T2D3CS6"  # Ensure your API key is included
}

# Make the API request
response = requests.get('https://www.alphavantage.co/query', params=params)

# Parse the response as JSON
data = response.json()

# Check the structure of the response
print(data)

# Extract 'quarterlyEarnings' and create a DataFrame
if "quarterlyEarnings" in data:
    df = pd.DataFrame(data["quarterlyEarnings"])
    print(df)
else:
    print("Key 'quarterlyEarnings' not found in the response.")
