# ADDIX Scholars — API Documentation

> **Version:** 1.0.0 · **Status:** 🟢 FROZEN · **Last Verified:** 2026-04-26

---

## Base URL

| Environment | URL |
|---|---|
| Local Development | `http://localhost:8000` |
| Production | _Your Vercel / Railway deployment URL_ |

---

## Authentication

No bearer token is required. Rate limiting is enforced per-IP via `slowapi`.

---

## Endpoint: Dual-Engine AI Route

### `POST /api/solve`

The single, unified endpoint powering both **Solver** (step-by-step tutor) and **Tester** (exam generator) modes.

---

### Headers

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | ✅ Yes |

---

### Request Body

```json
{
  "query": "string",
  "engine_mode": "solver" | "tester",
  "image_base64": "string (optional)"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | ✅ Yes | The user's academic question or topic. |
| `engine_mode` | `string` | ✅ Yes | Must be exactly `"solver"` or `"tester"`. |
| `image_base64` | `string` | ❌ No | A Base64-encoded JPEG/PNG image. When provided, routes to the **Vision Model** (`llama-3.2-90b-vision-preview`). |

---

### Response Schemas

#### When `engine_mode` = `"solver"`

Returns a single JSON object with a `response` key containing the AI's step-by-step explanation. Mathematical formulas use LaTeX delimiters (`$` for inline, `$$` for display).

```json
{
  "response": "The unit digit of $7^{105}$ is determined by the cyclic pattern of powers of 7...\n\nThe answer is $\\boxed{7}$."
}
```

| Field | Type | Description |
|---|---|---|
| `response` | `string` | The AI tutor's full explanation with LaTeX formatting. |

---

#### When `engine_mode` = `"tester"`

Returns a **raw JSON array** of exactly **3** multiple-choice question objects.

```json
[
  {
    "question": "Which law of thermodynamics states that entropy of an isolated system never decreases?",
    "options": {
      "A": "Zeroth Law",
      "B": "First Law",
      "C": "Second Law",
      "D": "Third Law"
    },
    "correct": "C",
    "explanation": "The Second Law of Thermodynamics states that the total entropy of an isolated system can never decrease over time."
  },
  {
    "question": "...",
    "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
    "correct": "B",
    "explanation": "..."
  },
  {
    "question": "...",
    "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
    "correct": "A",
    "explanation": "..."
  }
]
```

| Field | Type | Description |
|---|---|---|
| `question` | `string` | The question text. |
| `options` | `object` | Keys `A`, `B`, `C`, `D` mapping to option strings. |
| `correct` | `string` | The correct answer key (`"A"`, `"B"`, `"C"`, or `"D"`). |
| `explanation` | `string` | Brief reasoning for the correct answer. |

---

### Error Responses

#### `429 Too Many Requests` — Rate Limit Exceeded

Triggered when a single IP exceeds **15 requests per minute**.

```json
{
  "error": "Rate limit exceeded: 15 per 1 minute"
}
```

| HTTP Status | Cause | Resolution |
|---|---|---|
| `429` | More than 15 requests/min from the same IP | Wait and retry after 60 seconds. |

---

#### `422 Unprocessable Entity` — Validation Error

Returned when required fields are missing or have incorrect types.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "query"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

#### `500 / Inline Error` — LLM Failure

If the upstream Groq API fails, the endpoint still returns `200` with an error message embedded in the response body:

**Solver mode:**
```json
{
  "response": "API Error: <error details>"
}
```

**Tester mode:**
```json
[
  {
    "error": "Failed to generate valid JSON quiz: <error details>"
  }
]
```

---

## Model Routing

| Condition | Model Used |
|---|---|
| `image_base64` is **present** | `llama-3.2-90b-vision-preview` (Vision) |
| `image_base64` is **absent** | `llama-3.3-70b-versatile` (Text) |

Both models run with `temperature=0.0` for strict deterministic output.

---

## CORS Policy

The backend accepts requests from:

| Origin | Purpose |
|---|---|
| `http://localhost:3000` | Local Next.js / React dev server |
| `http://127.0.0.1:8000` | Local API testing (Swagger UI) |
| `https://*.vercel.app` | Vercel preview & production deployments |
| `*` | Wildcard fallback for flexibility |

---

## Quick Start (Frontend Fetch Examples)

### Solver Mode

```javascript
const res = await fetch("http://localhost:8000/api/solve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Explain the Schrödinger equation.",
    engine_mode: "solver"
  })
});
const data = await res.json();
console.log(data.response); // LaTeX-rich explanation
```

### Tester Mode

```javascript
const res = await fetch("http://localhost:8000/api/solve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Organic Chemistry",
    engine_mode: "tester"
  })
});
const questions = await res.json(); // Array of 3 MCQ objects
questions.forEach(q => console.log(q.question));
```

### Vision Mode (with image)

```javascript
const res = await fetch("http://localhost:8000/api/solve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Solve this problem from the image.",
    engine_mode: "solver",
    image_base64: "<base64-encoded-string>"
  })
});
const data = await res.json();
console.log(data.response);
```
