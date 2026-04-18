# ðŸ† ADDIX Scholars - Automated Benchmark Results

### Question 1
**Query:** A car is traveling at a constant speed of 72 km/h. It maintains this speed for exactly 12.5 minutes. Calculate the total distance covered in meters.

**Status:** âœ… Success (3.33s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** Students most often lose marks by skipping unit conversion before substitution; always convert to SI first.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=3.32s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=velocity expected=m/s derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 2
**Query:** A ball is thrown vertically upwards with a velocity of 20 m/s from the top of a tower 25m high. How long will it take for the ball to hit the ground? (Use g = 10 m/sÂ²)

**Status:** âœ… Success (2.20s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=2.19s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=velocity expected=m/s derived=symbolic (consistent)
- [CORE PRINCIPLE] Kinematics from first principles: x(t)=u cos(theta)t, y(t)=u sin(theta)t - (1/2)gt^2 | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Kinematics from first principles: x(t)=u cos(theta)t, y(t)=u sin(theta)t - (1/2)gt^2; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 3
**Query:** Find the derivative of x^3 * sin(x) with respect to x.

**Status:** âœ… Success (1.66s)
**LaTeX Result:**
```latex
$\frac{d}{dx} (x^3 \sin(x)) = 3x^2 \sin(x) + x^3 \cos(x)$
```
**Final Answer:** $\frac{d}{dx} (x^3 \sin(x)) = 3x^2 \sin(x) + x^3 \cos(x)$
**Student Tip:** The most frequent mistake is algebraic simplification drift; rewrite each intermediate expression before the next rule.
**Trace:** logic=Groq-Llama3-70B, math=Groq-Llama3-70B, latency=1.65s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] First-principles differential calculus using product/chain/power rules | route=Groq edge low-latency.
- [EXECUTION] Resolved through low-latency edge model for fast formula/unit lookup.

---

### Question 4
**Query:** A 5kg block rests on a frictionless table. It is pulled by a force of 50N at an angle of 30 degrees above the horizontal. Calculate its horizontal acceleration.

**Status:** âœ… Success (3.15s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** A common error is mixing sin(theta) and cos(theta) components; resolve horizontal and vertical parts separately.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=3.14s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=force expected=kg*m/s^2 derived=symbolic (consistent)
- [CORE PRINCIPLE] Newtonian kinematics: v=u+at and s=ut+(1/2)at^2 | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Newtonian kinematics: v=u+at and s=ut+(1/2)at^2; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 5
**Query:** ADDIX Labs - Gold Standard Test Bank

**Status:** âœ… Success (0.43s)
**LaTeX Result:**
```latex
\text{\$\ \\boxed\{0\}\ \$}
```
**Final Answer:** $ \boxed{0} $
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=Groq-Llama3-70B, math=Groq-Llama3-70B, latency=0.43s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=Groq edge low-latency.
- [EXECUTION] Resolved through low-latency edge model for fast formula/unit lookup.

---

### Question 6
**Query:** ------------------------------------

**Status:** âœ… Success (0.27s)
**LaTeX Result:**
```latex
0
```
**Final Answer:** 0
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=Groq-Llama3-70B, math=Groq-Llama3-70B, latency=0.25s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=Groq edge low-latency.
- [EXECUTION] Resolved through low-latency edge model for fast formula/unit lookup.

---

### Question 7
**Query:** Case 1 (NSEP 2025 - Physics - Q28):

**Status:** âœ… Success (7.62s)
**LaTeX Result:**
```latex
\text{System requires more constrained variables to solve.}
```
**Final Answer:** \text{System requires more constrained variables to solve.}
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=7.61s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained \text{System requires more constrained variables to solve.}.

---

### Question 8
**Query:** Knowing that the acceleration due to gravity on the Earth surface is g and the radius of the Earth is R, a small body of mass m falls on the Earth from a height h = R/5 above the Earth's surface. During the freefall, the potential energy of the falling body decreases by:

**Status:** âœ… Success (2.48s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** A recurring mistake is using total force instead of component force along the motion axis.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=2.47s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=acceleration expected=m/s^2 derived=symbolic (consistent)
- [CORE PRINCIPLE] Newtonian kinematics: v=u+at and s=ut+(1/2)at^2 | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Newtonian kinematics: v=u+at and s=ut+(1/2)at^2; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 9
**Query:** Case 2 (NSEC 2025 - Chemistry - Q4):

**Status:** âœ… Success (9.80s)
**LaTeX Result:**
```latex
\text{System requires more constrained variables to solve.}
```
**Final Answer:** \text{System requires more constrained variables to solve.}
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=9.79s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained \text{System requires more constrained variables to solve.}.

---

### Question 10
**Query:** In the spacecrafts of NASA, the oxygen required for the astronauts is obtained from the following chemical reaction:

**Status:** âœ… Success (2.41s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=2.40s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 11
**Query:** KClO3(s) + Fe(s) -> O2(g) + KCl(s) + FeO(s)

**Status:** âœ… Success (7.18s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=7.17s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 12
**Query:** The requirement of O2 per astronaut per day is 500 L as measured at 1 atm and 300 K. The minimum mass of KClO3 (Molar mass of KClO3 = 122.5 g/mol) needed for two astronauts to be in the spacecraft for ten days in a space mission is:

**Status:** âœ… Success (2.14s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** Students most often lose marks by skipping unit conversion before substitution; always convert to SI first.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=2.13s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---

### Question 13
**Query:** Case 3 (M1/IOQM 2025 - Math Olympiad - Q4):

**Status:** âœ… Success (7.29s)
**LaTeX Result:**
```latex
\text{System requires more constrained variables to solve.}
```
**Final Answer:** \text{System requires more constrained variables to solve.}
**Student Tip:** Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=7.28s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Number theory invariants and modular arithmetic constraints | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Number theory invariants and modular arithmetic constraints; substituted SI-normalized values, simplified algebra, and obtained \text{System requires more constrained variables to solve.}.

---

### Question 14
**Query:** How many isosceles integer-sided triangles are there with perimeter 23?

**Status:** âœ… Success (2.21s)
**LaTeX Result:**
```latex
\text{Symbolic\ Solver:\ No\ deterministic\ result\ available\ for\ this\ specific\ query.}
```
**Final Answer:** Symbolic Solver: No deterministic result available for this specific query.
**Student Tip:** A common error is mixing sin(theta) and cos(theta) components; resolve horizontal and vertical parts separately.
**Trace:** logic=DeepSeek-R1, math=WolframAlpha+SymPy, latency=2.20s
**Tri-Core Explanation Steps:**
- [UNIT SETUP] No explicit dimensional quantities found; treated as symbolic or pure numeric expression. | target=target expected=symbolic derived=symbolic (consistent)
- [CORE PRINCIPLE] Deterministic symbolic derivation from governing physical/mathematical laws | route=DeepSeek-R1 -> WolframAlpha+SymPy.
- [EXECUTION] Applied Deterministic symbolic derivation from governing physical/mathematical laws; substituted SI-normalized values, simplified algebra, and obtained Symbolic Solver: No deterministic result available for this specific query..

---


