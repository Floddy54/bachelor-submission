# Test that conda work by writing:
# 1. conda activate bachelorenv
# 2. python main.py
import requests
import numpy
import pandas as pd
import torch
import spacy

response = requests.get('https://httpbin.org/ip')

print('Your IP is {0}'.format(response.json()['origin']))