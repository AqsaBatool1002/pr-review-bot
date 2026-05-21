import os

def calculate(x, y):
    # READABILITY ISSUE: variable names a, b, c are bad
    a = x
    b = y
    c = a + b
    
    # BUG/ERROR HANDLING: No check for division by zero
    result = a / b
    
    # SECURITY ISSUE: Hardcoded fake API key (for testing)
    API_KEY = "sk-1234567890abcdef"
    
    return result

print(calculate(10, 0))
