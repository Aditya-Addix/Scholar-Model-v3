from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from typing import Optional

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://scholar-model-v3.vercel.app",
    "https://scholar-model-v3-7dnx-jofn4e1nx-adityapatel5912-4069s-projects.vercel.app",
    "*"  # Fallback wildcard to guarantee launch success
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import json

class SolveRequest(BaseModel):
    query: str
    image_base64: Optional[str] = None
    engine_mode: str

import os
from dotenv import load_dotenv
load_dotenv()
from groq import Groq

# Initialize the Groq client (requires GROQ_API_KEY in the environment)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.get("/api/vault")
async def get_vault():
    return {"status": "online", "message": "Engine is awake"}


@app.post("/api/solve")
@limiter.limit("15/minute")
async def solve(request: Request, payload: SolveRequest):
    if payload.engine_mode == "tester":
        system_prompt = (
            "You are a strict examination generator. Generate exactly 3 highly advanced multiple-choice questions based on the user's topic. You MUST return your response as a raw, valid JSON array. DO NOT include markdown formatting like ```json. Use this exact schema:\n"
            "[\n"
            "  {\n"
            "    \"question\": \"Question text?\",\n"
            "    \"options\": {\"A\": \"Opt 1\", \"B\": \"Opt 2\", \"C\": \"Opt 3\", \"D\": \"Opt 4\"},\n"
            "    \"correct\": \"A\",\n"
            "    \"explanation\": \"Reasoning.\"\n"
            "  }\n"
            "]"
        )
    else:
        system_prompt = (
            "You are an elite academic AI tutor. Provide step-by-step, deterministic explanations to the user's query. You MUST use LaTeX delimiters ($ or $$) strictly for mathematical formulas and never for plain English."
        )

    try:
        if payload.image_base64:
            model = "llama-3.2-90b-vision-preview"
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": payload.query},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{payload.image_base64}"}}
                    ]
                }
            ]
        else:
            model = "llama-3.3-70b-versatile"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload.query}
            ]

        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }

        completion = client.chat.completions.create(**completion_kwargs)
        raw_llm_output = completion.choices[0].message.content

        if payload.engine_mode == "tester":
            start_idx = raw_llm_output.find('[')
            end_idx = raw_llm_output.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                clean_json_str = raw_llm_output[start_idx:end_idx]
            else:
                clean_json_str = raw_llm_output
                
            json_response = json.loads(clean_json_str)
            return json_response
        else:
            return {"response": raw_llm_output}
            
    except Exception as e:
        if payload.engine_mode == "tester":
            return [{"error": f"Failed to generate valid JSON quiz: {str(e)}"}]
        return {"response": f"API Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
