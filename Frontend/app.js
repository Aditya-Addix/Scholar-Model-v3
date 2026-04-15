const BACKEND_URL =
    (typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_BACKEND_URL)
        || "https://scholar-model-v3.vercel.app";
const IS_LOCAL_HOST = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const API_BASE_URL = IS_LOCAL_HOST
    ? "http://localhost:8000"
    : BACKEND_URL;
const SECURITY_PROTOCOL_MESSAGE = "Security Protocol: Resetting API Handshake";
const SYSTEM_OVERRIDE_TIMEOUT_MESSAGE = "System Override: API timeout detected. Stabilizing agent pipeline.";
const SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE = "System Notice: Query requires manual override. Please rephrase algebraic parameters.";
const COUNTDOWN_INTERVAL_MS = 60 * 1000;
const VISION_INIT_MESSAGE = "[Vision Agent]: Initializing OCR scan...";
const VISION_PROGRESS_MESSAGE = "Analyzing Physical Constraints...";
const VISION_FUZZY_WARNING = "[Vision Agent]: Text extraction fuzzy. Please verify the query below.";
const SESSION_STORAGE_KEY = "addix-cognitive-session";
const SIMULATION_COMMAND_PREFIX = "/simulate ";
const SIMULATION_POLL_INTERVAL_MS = 3000;

const EXAM_TARGETS = {
    NSEJS: { id: "nsejs-days", date: new Date(2026, 10, 20) },
    NMTC: { id: "nmtc-days", date: new Date(2026, 9, 15) },
    IOQM: { id: "ioqm-days", date: new Date(2026, 8, 8) },
    JEE: { id: "jee-days", date: new Date(2027, 0, 24) },
};

const hudCards = Array.from(document.querySelectorAll(".hud-card"));
const chatFeed = document.getElementById("chatFeed");
const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const sendButton = document.getElementById("sendButton");
const buttonText = sendButton.querySelector(".button-text");
const terminalPanel = document.querySelector(".terminal");
const scannerTrigger = document.getElementById("scannerTrigger");
const scannerInput = document.getElementById("scanner-input");

let activeExam = "NSEJS";
let sending = false;
let commandHistory = [];
let historyIndex = 0;
let activeSimulationPoller = null;
let activeSimulationTaskId = "";
let lastSimulationUpdateSignature = "";
const SESSION_ID = getSessionId();

document.addEventListener("DOMContentLoaded", () => {
    hydrateHudFromMarkup();
    startCountdownSync();
    bindHudInteractions();
    bindChatInteractions();
    bindVisionInteractions();
    renderMath(chatFeed);
});

function startCountdownSync() {
    updateExamCountdowns();
    window.setInterval(updateExamCountdowns, COUNTDOWN_INTERVAL_MS);
}

function hydrateHudFromMarkup() {
    hudCards.forEach((card, index) => {
        const grade = card.dataset.grade || "-";
        const progress = clamp(Number(card.dataset.progress || 0), 0, 100);
        const daysNode = card.querySelector("[data-days-label]");
        const gradeNode = card.querySelector("[data-grade-label]");
        const gradeCenter = card.querySelector("[data-grade-center]");

        card.style.setProperty("--progress", String(progress));
        if (daysNode) daysNode.textContent = "--";
        if (gradeNode) gradeNode.textContent = grade;
        if (gradeCenter) gradeCenter.textContent = grade;

        if (index === 0) {
            card.classList.add("is-active");
        }
    });
}

function updateExamCountdowns() {
    Object.values(EXAM_TARGETS).forEach((config) => {
        const daysNode = document.getElementById(config.id);
        if (!daysNode) {
            return;
        }

        const daysRemaining = calculateDaysRemaining(config.date);
        daysNode.textContent = String(daysRemaining) + "d";

        const hostCard = daysNode.closest(".hud-card");
        if (hostCard) {
            hostCard.dataset.days = daysNode.textContent;
        }
    });
}

function updateCountdowns() {
    updateExamCountdowns();
}

function calculateDaysRemaining(targetDate) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const target = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate());
    const dayMs = 24 * 60 * 60 * 1000;
    const diffMs = target.getTime() - today.getTime();
    return Math.max(0, Math.ceil(diffMs / dayMs));
}

function bindHudInteractions() {
    hudCards.forEach((card) => {
        card.addEventListener("click", () => {
            activeExam = card.dataset.exam || "NSEJS";
            hudCards.forEach((item) => item.classList.remove("is-active"));
            card.classList.add("is-active");
        });
    });
}

function bindChatInteractions() {
    queryForm.addEventListener("submit", (event) => {
        event.preventDefault();
        sendQuery();
    });

    queryInput.addEventListener("keydown", (event) => {
        if (event.key === "ArrowUp") {
            event.preventDefault();
            navigateHistory(-1);
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            navigateHistory(1);
            return;
        }

        if (event.key === "Enter") {
            event.preventDefault();
            sendQuery();
        }
    });
}

function bindVisionInteractions() {
    if (!scannerTrigger || !scannerInput) {
        return;
    }

    scannerTrigger.addEventListener("click", () => {
        scannerInput.click();
    });

    scannerInput.addEventListener("change", async () => {
        const hasFile = scannerInput.files && scannerInput.files.length > 0;
        if (!hasFile) {
            return;
        }
        const selectedFile = scannerInput.files[0];
        appendVisionStep(VISION_INIT_MESSAGE);
        const progressStep = appendVisionProgressStep(VISION_PROGRESS_MESSAGE);

        scannerTrigger.classList.remove("scanning-pulse");
        if (terminalPanel) {
            terminalPanel.classList.remove("is-scanning");
            void terminalPanel.offsetWidth;
            terminalPanel.classList.add("is-scanning");
        }
        void scannerTrigger.offsetWidth;
        scannerTrigger.classList.add("scanning-pulse");

        try {
            updateVisionProgress(progressStep, 25, VISION_PROGRESS_MESSAGE);
            const imageBase64 = await fileToBase64(selectedFile);
            updateVisionProgress(progressStep, 55, VISION_PROGRESS_MESSAGE);

            const payload = await fetchOcr(imageBase64, activeExam);
            updateVisionProgress(progressStep, 100, "Analyzing Physical Constraints... Complete.");

            const cleanedQuery = typeof payload.cleaned_query === "string" ? payload.cleaned_query.trim() : "";
            if (cleanedQuery) {
                queryInput.value = cleanedQuery;
                queryInput.focus();
            }

            if (payload.warning) {
                appendVisionStep(payload.warning);
            } else if (payload.confidence < 60) {
                appendVisionStep(VISION_FUZZY_WARNING);
            }
        } catch (error) {
            const message = error && error.message ? String(error.message) : "Vision Agent failed to process image.";
            appendErrorStep(message);
            updateVisionProgress(progressStep, 100, "Vision analysis aborted.");
        }

        window.setTimeout(() => {
            scannerTrigger.classList.remove("scanning-pulse");
            if (terminalPanel) {
                terminalPanel.classList.remove("is-scanning");
            }
        }, 1400);

        scannerInput.value = "";
    });
}

async function sendQuery() {
    if (sending) {
        return;
    }

    const rawQuery = queryInput.value.trim();
    if (!rawQuery) {
        return;
    }

    rememberCommand(rawQuery);

    if (rawQuery.toLowerCase() === "clear") {
        clearTerminalFeed();
        queryInput.value = "";
        return;
    }

    if (rawQuery.toLowerCase() === "status") {
        await showSystemStatus();
        queryInput.value = "";
        return;
    }

    const isSimulationCommand = rawQuery.startsWith(SIMULATION_COMMAND_PREFIX);
    const simulationQuery = isSimulationCommand
        ? rawQuery.slice(SIMULATION_COMMAND_PREFIX.length).trim()
        : "";
    if (isSimulationCommand && !simulationQuery) {
        appendErrorStep("Simulation command requires a prompt. Example: /simulate optimal trajectory of a 5kg mass");
        queryInput.value = "";
        return;
    }

    sending = true;
    setButtonThinking(true);

    appendUserStep(rawQuery);
    queryInput.value = "";
    let solvingStep = null;

    try {
        if (isSimulationCommand) {
            const payload = await fetchSimulation(simulationQuery);
            const taskId = typeof payload.task_id === "string" ? payload.task_id.trim() : "";
            if (!taskId) {
                throw new Error("simulate-failed");
            }
            appendSimulationStartStep(taskId);
            beginSimulationPolling(taskId);
        } else {
            solvingStep = appendSolvingStep();
            const payload = await fetchSolve(rawQuery, activeExam);
            const finalAnswer = typeof payload.final_answer === "string"
                ? payload.final_answer.trim()
                : "No deterministic answer was returned by the backend.";
            const safeFinalAnswer = normalizeTerminalSecurityMessage(finalAnswer);
            replaceSolvingWithFinal(solvingStep, safeFinalAnswer);
        }
    } catch (error) {
        const errorText = error && error.message ? String(error.message) : "";
        const emitError = (message) => {
            if (solvingStep) {
                replaceSolvingWithError(solvingStep, message);
            } else {
                appendErrorStep(message);
            }
        };
        if (isSystemOverrideMessage(errorText)) {
            emitError(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        } else if (isSystemNoticeMessage(errorText)) {
            replaceSolvingWithFinal(solvingStep, SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE);
        } else if (isSecurityErrorMessage(errorText)) {
            emitError(SECURITY_PROTOCOL_MESSAGE);
        } else {
            emitError("Scholar Engine: Reconnecting to Tri-Core...");
        }
    } finally {
        setButtonThinking(false);
        sending = false;
        queryInput.focus();
    }
}

async function fetchSolve(studentQuery, targetExam) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 25000);

    try {
        const response = await fetch(`${BACKEND_URL}/api/solve`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify({
                student_query: studentQuery,
                target_exam: targetExam,
                session_id: SESSION_ID,
            }),
            signal: controller.signal,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.final_answer || payload?.detail || "solve-failed");
        }
        return payload;
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new Error(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function fetchSimulation(studentQuery) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 15000);

    try {
        const response = await fetch(API_BASE_URL + "/api/simulate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify({
                student_query: studentQuery,
            }),
            signal: controller.signal,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.detail || "simulate-failed");
        }
        return payload;
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new Error(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function fetchSimulationStatus(taskId) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 15000);

    try {
        const response = await fetch(API_BASE_URL + "/api/status/" + encodeURIComponent(taskId), {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
            signal: controller.signal,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.detail || "status-failed");
        }
        return payload;
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new Error(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function beginSimulationPolling(taskId) {
    stopSimulationPolling();
    activeSimulationTaskId = taskId;
    lastSimulationUpdateSignature = "";

    const pollStatus = async () => {
        try {
            const payload = await fetchSimulationStatus(taskId);
            handleSimulationStatusPayload(payload);
        } catch (error) {
            const message = error && error.message ? String(error.message) : "Simulation status check failed.";
            appendErrorStep("Simulation monitor interrupted: " + message);
            stopSimulationPolling();
        }
    };

    void pollStatus();
    activeSimulationPoller = window.setInterval(() => {
        void pollStatus();
    }, SIMULATION_POLL_INTERVAL_MS);
}

function stopSimulationPolling() {
    if (activeSimulationPoller) {
        window.clearInterval(activeSimulationPoller);
    }
    activeSimulationPoller = null;
    activeSimulationTaskId = "";
    lastSimulationUpdateSignature = "";
}

function handleSimulationStatusPayload(payload) {
    const taskId = typeof payload?.task_id === "string" ? payload.task_id : activeSimulationTaskId;
    const status = typeof payload?.status === "string" ? payload.status : "Simulating";
    const percent = typeof payload?.percent === "string" ? payload.percent : "0%";
    const progress = typeof payload?.progress === "string" ? payload.progress : "Awaiting update";
    const finalResult = typeof payload?.final_result === "string" ? payload.final_result.trim() : "";

    const signature = [status, percent, progress].join("|");
    if (signature !== lastSimulationUpdateSignature) {
        appendSimulationUpdateStep(percent, progress);
        lastSimulationUpdateSignature = signature;
    }

    if (status === "Completed") {
        stopSimulationPolling();
        const safeFinal = normalizeTerminalSecurityMessage(finalResult || "Simulation completed without a final result.");
        appendAgentStep(
            "final-step",
            "[Final Simulation Result]",
            safeFinal,
            formatWolframAsLatex(safeFinal)
        );
        return;
    }

    if (status === "Failed") {
        stopSimulationPolling();
        appendErrorStep("Simulation task #" + taskId + " failed.");
    }
}

async function fetchOcr(imageBase64, targetExam) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 40000);

    try {
        const response = await fetch(API_BASE_URL + "/api/ocr", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify({
                image_base64: imageBase64,
                target_exam: targetExam,
                session_id: SESSION_ID,
            }),
            signal: controller.signal,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.detail || payload?.final_answer || "ocr-failed");
        }
        return payload;
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new Error(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function fetchSystemStatus() {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 15000);

    try {
        const response = await fetch(API_BASE_URL + "/api/system-status", {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
            signal: controller.signal,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.detail || "status-failed");
        }
        return payload;
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new Error(SYSTEM_OVERRIDE_TIMEOUT_MESSAGE);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function showSystemStatus() {
    appendUserStep("status");
    const statusStep = appendAgentStep(
        "system-step",
        "System Monitor",
        "Running subsystem diagnostics...",
        "\\text{Checking Wolfram and database health}"
    );

    try {
        const payload = await fetchSystemStatus();
        const wolframStatus = payload?.wolfram_status || "unknown";
        const databaseStatus = payload?.database_status || "unknown";
        const historyRecords = Number.isFinite(payload?.history_records) ? payload.history_records : "-";
        const statusCopy = "Wolfram: " + wolframStatus + " | DB: " + databaseStatus + " | Logs: " + historyRecords;
        updateAgentStep(statusStep, statusCopy, formatWolframAsLatex(statusCopy));
    } catch (error) {
        const message = error && error.message ? String(error.message) : "Status check failed.";
        updateAgentStep(statusStep, "Status unavailable: " + message, formatWolframAsLatex(message));
    }
}

function appendUserStep(query) {
    const timestamp = "[" + formatClock(new Date()) + "]";
    const safeQuery = escapeHtml(query);
    const html =
        '<article class="message user-step">' +
            '<p class="message-line"><span class="timestamp">' + timestamp + '</span> ' +
            '<span class="agent-label">User:</span> ' + safeQuery + '</p>' +
        '</article>';

    appendMessage(html);
}

function appendSolvingStep() {
    const html =
        '<article class="message loading-step">' +
            '<div class="agent-row">' +
                '<span class="agent-pulse"></span>' +
                '<p class="message-line"><span class="agent-label">[System]:</span> Computing deterministic result...</p>' +
            '</div>' +
        '</article>';

    return appendMessage(html);
}

function appendSimulationStartStep(taskId) {
    const html =
        '<article class="message loading-step simulation-step">' +
            '<div class="agent-row">' +
                '<span class="agent-pulse"></span>' +
                '<p class="message-line"><span class="agent-label">[Deep Engine]:</span> Simulation Task #' + escapeHtml(taskId) + ' started. Agents are running in the background...</p>' +
            '</div>' +
        '</article>';

    appendMessage(html);
}

function appendSimulationUpdateStep(percent, progress) {
    const html =
        '<article class="message agent-step simulation-update-step">' +
            '<p class="message-line"><span class="agent-label">[Update]:</span> ' + escapeHtml(percent) + ' - ' + escapeHtml(progress) + '</p>' +
        '</article>';

    appendMessage(html);
}

function replaceSolvingWithFinal(stepElement, finalAnswer) {
    const safeAnswer = escapeHtml(finalAnswer);
    const safeEquation = escapeHtml(formatWolframAsLatex(finalAnswer));

    if (!stepElement) {
        appendAgentStep(
            "final-step",
            "[Final Answer]",
            finalAnswer,
            formatWolframAsLatex(finalAnswer)
        );
        return;
    }

    stepElement.classList.remove("loading-step");
    stepElement.classList.add("final-step");
    stepElement.innerHTML =
        '<div class="agent-row">' +
            '<span class="agent-pulse"></span>' +
            '<span class="agent-label">[Final Answer]:</span>' +
            '<span class="message-line">' + safeAnswer + '</span>' +
        '</div>' +
        '<div class="math-block">$$' + safeEquation + '$$</div>';

    renderMath(stepElement);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function replaceSolvingWithError(stepElement, copy) {
    const safeCopy = escapeHtml(copy);
    if (!stepElement) {
        appendErrorStep(copy);
        return;
    }

    stepElement.classList.remove("loading-step");
    stepElement.classList.add("error-step");
    stepElement.innerHTML =
        '<p class="message-line"><span class="agent-label">[Final Answer]:</span> ' + safeCopy + '</p>';
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function appendVisionStep(copy) {
    const html =
        '<article class="message vision-step">' +
            '<p class="message-line">' + escapeHtml(copy) + '</p>' +
        '</article>';

    appendMessage(html);
}

function appendVisionProgressStep(label) {
    const html =
        '<article class="message vision-progress-step">' +
            '<p class="message-line" data-vision-label>' + escapeHtml(label) + '</p>' +
            '<div class="vision-progress-track" aria-hidden="true">' +
                '<span class="vision-progress-fill" data-vision-progress></span>' +
            '</div>' +
        '</article>';

    return appendMessage(html);
}

function updateVisionProgress(stepElement, percent, label) {
    if (!stepElement) {
        return;
    }
    const fillNode = stepElement.querySelector("[data-vision-progress]");
    const labelNode = stepElement.querySelector("[data-vision-label]");
    const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
    if (fillNode) {
        fillNode.style.width = safePercent + "%";
    }
    if (labelNode && label) {
        labelNode.textContent = label;
    }
}

function appendAgentStep(stepClass, label, copy, equation) {
    const safeCopy = escapeHtml(copy);
    const safeEquation = escapeHtml(equation);

    const html =
        '<article class="message agent-step ' + stepClass + '">' +
            '<div class="agent-row">' +
                '<span class="agent-pulse"></span>' +
                '<span class="agent-label">' + label + ':</span>' +
                '<span class="message-line" data-agent-copy>' + safeCopy + '</span>' +
            '</div>' +
            '<div class="math-block" data-agent-equation>$$' + safeEquation + '$$</div>' +
        '</article>';

    return appendMessage(html, { shouldRenderMath: true });
}

function updateAgentStep(stepElement, copy, equation) {
    if (!stepElement) {
        return;
    }

    const copyNode = stepElement.querySelector("[data-agent-copy]");
    const equationNode = stepElement.querySelector("[data-agent-equation]");

    if (copyNode) {
        copyNode.textContent = copy;
    }
    if (equationNode) {
        equationNode.textContent = "$$" + equation + "$$";
    }

    renderMath(stepElement);
}

function appendErrorStep(copy) {
    const html =
        '<article class="message error-step">' +
            '<p class="message-line"><span class="agent-label">ADDIX Logic:</span> ' +
            escapeHtml(copy) + '</p>' +
        '</article>';

    appendMessage(html);
}

function appendMessage(html, options = {}) {
    const shouldRenderMath = Boolean(options.shouldRenderMath);
    chatFeed.insertAdjacentHTML("beforeend", html);
    const latest = chatFeed.lastElementChild;
    if (shouldRenderMath) {
        renderMath(latest);
    }
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return latest;
}

function setButtonThinking(isThinking) {
    sendButton.disabled = isThinking;
    sendButton.classList.toggle("is-thinking", isThinking);
    buttonText.textContent = isThinking ? "Solving..." : "Send Query";
}

function rememberCommand(query) {
    const normalized = String(query || "").trim();
    if (!normalized) {
        return;
    }
    const last = commandHistory[commandHistory.length - 1];
    if (last !== normalized) {
        commandHistory.push(normalized);
    }
    historyIndex = commandHistory.length;
}

function navigateHistory(direction) {
    if (!commandHistory.length) {
        return;
    }

    const nextIndex = historyIndex + direction;
    historyIndex = clamp(nextIndex, 0, commandHistory.length);

    if (historyIndex === commandHistory.length) {
        queryInput.value = "";
    } else {
        queryInput.value = commandHistory[historyIndex] || "";
    }

    queryInput.setSelectionRange(queryInput.value.length, queryInput.value.length);
}

function clearTerminalFeed() {
    chatFeed.innerHTML = "";
}

function inferSymbolicEquation(query) {
    const q = query.toLowerCase();

    if (q.includes("integral") || q.includes("integrate")) {
        return "\\int f(x)\\,dx";
    }
    if (q.includes("derivative") || q.includes("differentiate")) {
        return "\\frac{d}{dx}f(x)";
    }
    if (q.includes("limit")) {
        return "\\lim_{x \\to a} f(x)";
    }
    if (q.includes("projectile") || q.includes("range") || q.includes("angle")) {
        return "R = \\frac{u^2\\sin 2\\theta}{g}";
    }
    if (q.includes("acceleration") || q.includes("velocity") || q.includes("distance")) {
        return "s = ut + \\frac{1}{2}at^2";
    }
    if (q.includes("quadratic") || q.includes("roots")) {
        return "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}";
    }
    if (q.includes("current") || q.includes("voltage") || q.includes("resistance")) {
        return "V = IR";
    }
    return "\\text{Formula derived from query context}";
}

function inferNumericalPreview(query) {
    const q = query.toLowerCase();

    if (q.includes("acceleration") || q.includes("velocity") || q.includes("distance")) {
        return "a = \\frac{v-u}{t},\\quad v^2 = u^2 + 2as";
    }
    if (q.includes("projectile") || q.includes("range")) {
        return "x(t)=u\\cos\\theta\\cdot t,\\quad y(t)=u\\sin\\theta\\cdot t-\\frac{1}{2}gt^2";
    }
    if (q.includes("mole") || q.includes("chem")) {
        return "n = \\frac{m}{M},\\quad C = \\frac{n}{V}";
    }
    return "\\text{Substitute knowns and isolate target variable}";
}

function extractFirstLatex(text) {
    const matchBlock = text.match(/\$\$([^$]+)\$\$/);
    if (matchBlock && matchBlock[1]) {
        return matchBlock[1].trim();
    }
    const matchInline = text.match(/\$([^$]+)\$/);
    if (matchInline && matchInline[1]) {
        return matchInline[1].trim();
    }
    return "";
}

function extractPrimaryFormula(payload, rawQuery, finalAnswer) {
    const trace = Array.isArray(payload?.logic_trace)
        ? payload.logic_trace
        : (Array.isArray(payload?.explanation_trace) ? payload.explanation_trace : []);
    const symbolicStep = trace.find((step) => {
        return step && step.agent_type === "Symbolic" && typeof step.math_latex === "string" && step.math_latex.trim();
    });

    if (symbolicStep && symbolicStep.math_latex && isLikelyFormula(symbolicStep.math_latex)) {
        return symbolicStep.math_latex.trim();
    }

    const fromAnswer = extractFirstLatex(finalAnswer);
    if (fromAnswer) {
        return fromAnswer;
    }

    return inferSymbolicEquation(rawQuery);
}

function extractDeterministicComputation(payload, rawQuery, finalAnswer) {
    const trace = Array.isArray(payload?.logic_trace)
        ? payload.logic_trace
        : (Array.isArray(payload?.explanation_trace) ? payload.explanation_trace : []);
    const executionStep = trace.find((step) => {
        return step && (step.title === "Wolfram Execution" || step.title === "Cache Retrieval");
    });
    const validationStep = trace.find((step) => step && step.title === "Result Validation");

    const sequence = [];
    sequence.push("Input: " + rawQuery);
    if (executionStep && executionStep.description) {
        sequence.push(executionStep.description.replace(/\n+/g, " -> "));
    } else {
        sequence.push("Wolfram deterministic execution completed.");
    }
    if (validationStep && validationStep.description) {
        sequence.push(validationStep.description.replace(/\n+/g, " -> "));
    } else {
        sequence.push("Deterministic response validation completed.");
    }
    sequence.push("Output: " + finalAnswer);

    return formatWolframAsLatex(sequence.join(" -> "));
}

function isLikelyFormula(candidate) {
    const sample = String(candidate || "").trim();
    if (!sample || sample.length > 160) {
        return false;
    }
    const containsMathSignal = /[=+\-*/^]|\\frac|\\int|\\lim|\\sqrt|\\sum|\\to|_\{|\^\{/.test(sample);
    if (containsMathSignal) {
        return true;
    }
    const wordCount = sample.split(/\s+/).length;
    return wordCount <= 6;
}

function isSystemOverrideMessage(text) {
    const normalized = String(text || "").toLowerCase();
    return normalized.includes("system override") || normalized.includes("timeout");
}

function isSecurityErrorMessage(text) {
    const normalized = String(text || "").toLowerCase();
    return (
        normalized.includes("403")
        || normalized.includes("401")
        || normalized.includes("forbidden")
        || normalized.includes("unauthorized")
        || normalized.includes("appid")
        || normalized.includes("handshake")
        || normalized.includes("security protocol")
    );
}

function isSystemNoticeMessage(text) {
    const normalized = String(text || "").toLowerCase();
    return normalized.includes("system notice") && normalized.includes("manual override");
}

function normalizeTerminalSecurityMessage(text) {
    const normalized = String(text || "").trim();
    if (isSecurityErrorMessage(normalized)) {
        return SECURITY_PROTOCOL_MESSAGE;
    }
    return normalized || "No deterministic answer was returned by the backend.";
}

function formatWolframAsLatex(answerText) {
    const raw = String(answerText || "").trim();
    if (!raw) {
        return "\\text{No\\ deterministic\\ result}";
    }

    const extracted = extractFirstLatex(raw);
    if (extracted) {
        return extracted;
    }

    const escaped = raw
        .replace(/\\/g, "\\\\")
        .replace(/{/g, "\\{")
        .replace(/}/g, "\\}")
        .replace(/%/g, "\\%")
        .replace(/#/g, "\\#")
        .replace(/\$/g, "\\$")
        .replace(/&/g, "\\&")
        .replace(/_/g, "\\_")
        .replace(/\^/g, "\\^{}")
        .replace(/~/g, "\\~{}");

    return "\\text{" + escaped.replace(/ /g, "\\ ") + "}";
}

function renderMath(scope) {
    if (!scope || typeof window.renderMathInElement !== "function") {
        return;
    }

    window.renderMathInElement(scope, {
        delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "\\(", right: "\\)", display: false },
            { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
    });
}

function formatClock(date) {
    return date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
    });
}

function sleep(ms) {
    return new Promise((resolve) => {
        setTimeout(resolve, ms);
    });
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function getSessionId() {
    try {
        const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
        if (existing && existing.trim()) {
            return existing;
        }
        const created = "session-" + Math.random().toString(36).slice(2, 10);
        window.localStorage.setItem(SESSION_STORAGE_KEY, created);
        return created;
    } catch (error) {
        return "session-default";
    }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = typeof reader.result === "string" ? reader.result : "";
            const payload = result.includes(",") ? result.split(",", 2)[1] : result;
            if (!payload) {
                reject(new Error("Image conversion failed."));
                return;
            }
            resolve(payload);
        };
        reader.onerror = () => {
            reject(new Error("Image conversion failed."));
        };
        reader.readAsDataURL(file);
    });
}

function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => {
        const map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        };
        return map[char] || char;
    });
}

window.sendQuery = sendQuery;
window.updateExamCountdowns = updateExamCountdowns;
window.updateCountdowns = updateCountdowns;
