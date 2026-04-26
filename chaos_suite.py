import requests
import concurrent.futures

URL = "http://localhost:8000/api/solve"

def color_print(status, message):
    if status == "PASS":
        print(f"\033[92m[PASS]\033[0m {message}")
    else:
        print(f"\033[91m[FAIL]\033[0m {message}")

def test_tester_json():
    print("Running Test 2 (Tester JSON)...")
    payload = {"query": "Thermodynamics", "engine_mode": "tester"}
    try:
        response = requests.post(URL, json=payload)
        if response.status_code == 429:
            color_print("FAIL", "Rate limited too early!")
            return
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) == 3:
            color_print("PASS", "Returned exactly 3 valid JSON items.")
        else:
            color_print("FAIL", f"Response is not a list of 3 items. Got: {data}")
    except Exception as e:
        color_print("FAIL", f"Exception occurred: {e}")

def test_solver_intelligence():
    print("\nRunning Test 3 (Solver Intelligence)...")
    payload = {"query": "Find the unit digit of 7^105.", "engine_mode": "solver"}
    try:
        response = requests.post(URL, json=payload)
        if response.status_code == 429:
            color_print("FAIL", "Rate limited too early!")
            return
        response.raise_for_status()
        data = response.json()
        if "response" in data and "7" in data.get("response", "") and "API Error" not in data.get("response", ""):
            color_print("PASS", "String '7' found in the deterministic response.")
        else:
            color_print("FAIL", f"Expected '7' in response, got: {data}")
    except Exception as e:
        color_print("FAIL", f"Exception occurred: {e}")

def test_rate_limit():
    print("\nRunning Test 1 (Rate Limit)...")
    payload = {"query": "test", "engine_mode": "solver"}
    
    def send_req():
        return requests.post(URL, json=payload)
        
    responses = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(send_req) for _ in range(20)]
        for future in concurrent.futures.as_completed(futures):
            try:
                responses.append(future.result())
            except Exception as e:
                print(e)

    status_codes = [r.status_code for r in responses]
    if 429 in status_codes:
        color_print("PASS", "Rate limit correctly enforced. Got 429 status code.")
        # Check if it's clean JSON
        for r in responses:
            if r.status_code == 429:
                try:
                    r.json()
                    color_print("PASS", "Rate limit response is clean JSON.")
                except Exception:
                    color_print("FAIL", "Rate limit response is not clean JSON.")
                break
    else:
        color_print("FAIL", f"Expected 429 status code, got: {status_codes}")

if __name__ == "__main__":
    # We run Tester and Solver tests first before the rate limit blocks us
    test_tester_json()
    test_solver_intelligence()
    test_rate_limit()
