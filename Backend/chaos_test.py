import concurrent.futures
import requests

URL = "http://localhost:8000/api/solve"

def print_result(name, passed, detail=""):
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    status = "PASS" if passed else "FAIL"
    print(f"{color}[{status}] {name}{reset} {detail}")

def test_1():
    print("Running Test 1 - Advanced Physics (Text Route)...")
    payload = {"query": "Derive the Schrödinger equation for a quantum harmonic oscillator."}
    r = requests.post(URL, json=payload)
    if r.status_code == 200 and "Groq Llama 3 Text Model Answer" in r.json().get("answer", ""):
        print_result("Test 1", True)
    else:
        print_result("Test 1", False, r.text)

def test_2():
    print("Running Test 2 - Advanced Vision (Image Route)...")
    payload = {"query": "Apply Kirchhoff's laws to find the current across the central resistor.", "image_base64": "dummy_base64"}
    r = requests.post(URL, json=payload)
    if r.status_code == 200 and "Mistral Vision Model Answer" in r.json().get("answer", ""):
        print_result("Test 2", True)
    else:
        print_result("Test 2", False, r.text)

def test_3():
    print("Running Test 3 - Rate Limit Attack...")
    payload = {"query": "test"}
    def make_req():
        return requests.post(URL, json=payload).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_req) for _ in range(20)]
        status_codes = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    if 429 in status_codes:
        print_result("Test 3", True, f"Blocked with 429. (Status codes: {status_codes})")
    else:
        print_result("Test 3", False, f"Failed to block. (Status codes: {status_codes})")

if __name__ == "__main__":
    try:
        test_1()
        test_2()
        test_3()
    except Exception as e:
        print("Error during tests:", e)
