#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
wallet = os.getenv('POLYMARKET_WALLET')

resp = requests.get(
    'https://data-api.polymarket.com/positions',
    params={'user': wallet, 'limit': 50},
    timeout=10
)

positions = [p for p in resp.json() if float(p.get('size', 0)) > 0]
print(f'Open positions: {len(positions)}')
print()

total_value = 0
for p in positions:
    size = float(p['size'])
    price = float(p['curPrice'])
    value = size * price
    total_value += value
    print(f'{p["title"]} - {p["asset"]}')
    print(f'  Size: {size:.2f} @ ${price:.4f} = ${value:.2f}')
    print()

print(f'Total position value: ${total_value:.2f}')
