import os

# 🔒 ISSUE 1: Hardcoded sensitive information
API_KEY = "12345-secret-key"

def calculate(x, y):
    # 📖 ISSUE 2: Poor variable naming
    a = x
    b = y
    return a + b

def read_data(filename):
    # ⚠️ ISSUE 3: Missing error handling (No try/except)
    f = open(filename, 'r')
    data = f.read()
    f.close()
    return data

print(calculate(5, 10))
