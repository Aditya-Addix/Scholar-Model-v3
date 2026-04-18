import requests
import time
import json
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/api/solve"
TARGET_MODEL = "deepseek" # Forcing DeepSeek for reasoning
RESULTS_FILE = "benchmark_results.md"
TARGET_EXAM = "NSEJS"

# --- THE STANDARD TRI-CORE STRESS TESTS ---
STANDARD_QUESTIONS = [
    # Test 1: DeepSeek Unit Conversion & SymPy Multiplication
    "A car is traveling at a constant speed of 72 km/h. It maintains this speed for exactly 12.5 minutes. Calculate the total distance covered in meters.",
    
    # Test 2: Quadratic Equation Handling (Requires choosing the positive root)
    "A ball is thrown vertically upwards with a velocity of 20 m/s from the top of a tower 25m high. How long will it take for the ball to hit the ground? (Use g = 10 m/sÂ²)",
    
    # Test 3: Pure Math Bypass & Simplification
    "Find the derivative of x^3 * sin(x) with respect to x.",
    
    # Test 4: Implicit Variables & Angles
    "A 5kg block rests on a frictionless table. It is pulled by a force of 50N at an angle of 30 degrees above the horizontal. Calculate its horizontal acceleration."
]

def load_custom_questions(filename="olympiad_selected_questions.txt"):
    """Loads questions from your text file if it exists."""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            # Reads non-empty lines
            return [line.strip() for line in f if line.strip()]
    return []

def run_benchmark():
    print(f"ðŸš€ Starting ADDIX Scholars Benchmark against {API_URL}")
    print("-" * 50)
    
    all_questions = STANDARD_QUESTIONS + load_custom_questions()
    
    with open(RESULTS_FILE, "w", encoding='utf-8') as log:
        log.write("# ðŸ† ADDIX Scholars - Automated Benchmark Results\n\n")
        
        for i, query in enumerate(all_questions, 1):
            print(f"\n[{i}/{len(all_questions)}] Testing: {query[:50]}...")
            log.write(f"### Question {i}\n**Query:** {query}\n\n")
            
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": query,
                    }
                ],
                "target_exam": TARGET_EXAM,
                "session_id": "benchmark-session",
            }
            start_time = time.time()
            
            try:
                response = requests.post(API_URL, json=payload, timeout=30)
                latency = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", "No result found.")
                    explanation = data.get("explanation", [])
                    engine_trace = data.get("engine_trace", "")

                    if not isinstance(explanation, list) or len(explanation) != 4:
                        raise ValueError("explanation must contain exactly 4 stages")
                    if not all(isinstance(step, str) for step in explanation):
                        raise ValueError("explanation steps must be strings")
                    if not isinstance(engine_trace, str) or not engine_trace.strip():
                        raise ValueError("engine_trace must be non-empty")
                    
                    print(f"  âœ… Success! ({latency:.2f}s)")
                    log.write(f"**Status:** âœ… Success ({latency:.2f}s)\n")
                    log.write(f"**LaTeX Result:**\n```latex\n{result}\n```\n")
                    log.write(f"**Engine Trace:** {engine_trace}\n")
                    log.write(f"**Tri-Core Explanation Steps:**\n")
                    for step in explanation:
                        log.write(f"- {step}\n")
                        
                else:
                    print(f"  âŒ Error {response.status_code}")
                    log.write(f"**Status:** âŒ Error {response.status_code}\n")
                    log.write(f"**Response:** {response.text}\n")
                    
            except requests.exceptions.RequestException:
                print(f"  ðŸš¨ Connection Failed. Is the server running?")
                log.write(f"**Status:** ðŸš¨ Server Unreachable\n")
            except ValueError as e:
                print(f"  âŒ Invalid payload shape: {e}")
                log.write(f"**Status:** âŒ Invalid payload shape\n")
                log.write(f"**Error:** {str(e)}\n")
            
            log.write("\n---\n\n")
            time.sleep(2) # Brief pause so we don't trip API rate limits
            
    print(f"\nðŸŽ‰ Benchmark Complete! Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    run_benchmark()
