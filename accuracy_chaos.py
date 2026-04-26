import requests
import json

URL = "http://localhost:8000/api/solve"

# Color Codes
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

test_cases = [
    {
        "name": "Question 1",
        "payload": {"query": "A particle moves along the x-axis with velocity v(t) = 3t^2 - 6t. What is the total distance traveled from t=0 to t=3?", "engine_mode": "solver"},
        "expected": "6"
    },
    {
        "name": "Question 2",
        "payload": {"query": "Find the unit digit of 7^105.", "engine_mode": "solver"},
        "expected": "7"
    },
    {
        "name": "Question 3",
        "payload": {"query": "Evaluate the definite integral of 2x with respect to x from x=0 to x=4.", "engine_mode": "solver"},
        "expected": "16"
    },
    {
        "name": "Question 4",
        "payload": {"query": "Balance this equation: C3H8 + O2 -> CO2 + H2O. What is the final coefficient of O2?", "engine_mode": "solver"},
        "expected": "5"
    }
]

def run_accuracy_chaos():
    print("Executing Final Accuracy Validation...\n")
    
    for test in test_cases:
        try:
            response = requests.post(URL, json=test["payload"], timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract response string, default to empty if not found
            answer = data.get("response", "")
            
            if test["expected"] in answer:
                print(f"{GREEN}[PASS] {test['name']} - Target acquired.{RESET}")
            else:
                # Provide a snippet of the AI response to show what went wrong
                snippet = answer[:200] + ("..." if len(answer) > 200 else "")
                print(f"{RED}[FAIL] {test['name']} - Calculation Error. Expected: {test['expected']}, Got: {snippet}{RESET}")
                
        except requests.exceptions.Timeout:
            print(f"{RED}[FAIL] {test['name']} - Request timed out after 30 seconds.{RESET}")
        except Exception as e:
            print(f"{RED}[FAIL] {test['name']} - Exception occurred: {e}{RESET}")

if __name__ == "__main__":
    run_accuracy_chaos()
