const BASE_URL = "https://scholar-model-v3.onrender.com";
const PREMIUM_STATUS_STORAGE_KEY = "addix-premium-status";
const isPremiumUser = true; // MOCKED FOR LOCAL TESTING
const SECURITY_PROTOCOL_MESSAGE = "Security Protocol: Resetting API Handshake";
const SYSTEM_OVERRIDE_TIMEOUT_MESSAGE = "System Override: API timeout detected. Stabilizing agent pipeline.";
const SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE = "System Notice: Query requires manual override. Please rephrase algebraic parameters.";
const TRI_CORE_HOLD_MESSAGE = "Scholar Engine: Computing via Tri-Core Logic...";
const COUNTDOWN_INTERVAL_MS = 60 * 1000;
const VISION_INIT_MESSAGE = "[Vision Agent]: Initializing OCR scan...";
const VISION_PROGRESS_MESSAGE = "Analyzing Physical Constraints...";
const VISION_FUZZY_WARNING = "[Vision Agent]: Text extraction fuzzy. Please verify the query below.";
const PROGRESS_STORAGE_KEY = "addix-progress-dashboard";
const CONSISTENCY_MATRIX_DAYS = 28;
const SIMULATION_COMMAND_PREFIX = "/simulate ";
const SIMULATION_POLL_INTERVAL_MS = 3000;
const MAX_TURN_CONTEXT = 3;
const API_CALL_TIMEOUT_MS = 120000;
const ENGINE_WAKE_NOTICE_DELAY_MS = 5000;
const CONNECTION_ALERT_GRACE_PERIOD_MS = 90000;
const RATE_LIMIT_COOLDOWN_SECONDS = 30;
const ACCESS_CODE = "ADDIX2026"; // Change this to your preferred code.
const ACCESS_STATUS_STORAGE_KEY = "addix-labs-access-granted";
const TRACE_PHASES = [
    { engine: "Scholar Engine", label: "Deconstructing logic..." },
    { engine: "Scholar Engine", label: "Running dimensional analysis..." },
    { engine: "Scholar Engine", label: "Verifying constraints..." },
];

const EXAM_TARGETS = {
    NSEJS: { id: "nsejs-days", fixedDays: 219, date: new Date(2026, 10, 20) },
    NMTC: { id: "nmtc-days", fixedDays: 183, date: new Date(2026, 9, 15) },
    IOQM: { id: "ioqm-days", fixedDays: 146, date: new Date(2026, 8, 8) },
    JEE: { id: "jee-days", date: new Date(2027, 0, 24) },
};

const hudGrid = document.getElementById("hudGrid");
const hudCards = Array.from(document.querySelectorAll(".hud-card"));
const chatFeed = document.getElementById("chatFeed");
const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const mathKeyButtons = Array.from(document.querySelectorAll(".math-key"));
const sendButton = document.getElementById("sendButton");
const buttonText = sendButton.querySelector(".button-text");
const terminalPanel = document.querySelector(".terminal");
const imageUploadButton = document.getElementById("imageButton") || document.getElementById("imageUploadButton");
const imageUploadInput = document.getElementById("image-upload") || document.getElementById("imageInput");
const imagePreviewShell = document.getElementById("imagePreviewShell");
const imagePreviewThumb = document.getElementById("imagePreviewThumb");
const imagePreviewRemoveButton = document.getElementById("imagePreviewRemoveButton");
const sidebarPanel = document.querySelector(".scholar-sidebar");
const systemHealthDot = document.getElementById("systemHealthDot");
const systemHealthLabel = document.getElementById("systemHealthLabel");
const statusText = document.getElementById("status-text");
const statusDot = document.getElementById("status-dot");
const examContextSelector = document.getElementById("exam-context-selector");
const engineModeToggle = document.getElementById("engineModeToggle");
const engineModeLabel = document.getElementById("engineModeLabel");
const clearChatButton = document.getElementById("clearChatButton");
const exportSessionButton = document.getElementById("exportSessionButton");
const exportFormulaSheetButton = document.getElementById("exportFormulaSheetButton");
const focusModeButton = document.getElementById("focusModeButton");
const debriefSessionButton = document.getElementById("debriefSessionButton");
const exportWeaknessReportButton = document.getElementById("exportWeaknessReportButton");
const openBlackBoxButton = document.getElementById("openBlackBoxButton");
const blackBoxModal = document.getElementById("black-box-modal");
const closeBlackBoxButton = document.getElementById("closeBlackBoxButton");
const blackBoxList = document.getElementById("blackBoxList");
const debriefModal = document.getElementById("debrief-modal");
const closeDebriefButton = document.getElementById("closeDebriefButton");
const debriefModalBody = document.getElementById("debriefModalBody");
const premiumModal = document.getElementById("premium-modal");
const closePremiumModalButton = document.getElementById("closePremiumModalButton");
const upgradeToPremiumButton = document.getElementById("upgradeToPremiumButton");
const problemsSolvedValue = document.getElementById("problemsSolvedValue");
const timeSavedValue = document.getElementById("timeSavedValue");
const currentStreakValue = document.getElementById("currentStreakValue");
const masteryBreakdown = document.getElementById("masteryBreakdown");
const marathonTimerShell = document.getElementById("marathonTimerShell");
const marathonTimerDisplay = document.getElementById("marathonTimerDisplay");
const marathonStartButton = document.getElementById("marathonStartButton");
const marathonPauseButton = document.getElementById("marathonPauseButton");
const marathonStopButton = document.getElementById("marathonStopButton");
const consistencyMatrix = document.getElementById("consistencyMatrix");
const prepRingPhysics = document.querySelector('.prep-ring-progress[data-subject="Physics"]');
const prepRingChemistry = document.querySelector('.prep-ring-progress[data-subject="Chemistry"]');
const prepRingMath = document.querySelector('.prep-ring-progress[data-subject="Math"]');
const prepRingPhysicsValue = document.getElementById("prepRingPhysicsValue");
const prepRingChemistryValue = document.getElementById("prepRingChemistryValue");
const prepRingMathValue = document.getElementById("prepRingMathValue");
const addixScholarsShell = document.getElementById("addixScholarsShell");
const mobileSidebarToggle = document.getElementById("mobileSidebarToggle");
const syllabusExplorerPanel = document.querySelector(".syllabus-explorer");
const labsGate = document.getElementById("labs-gate");
const labsGatePanel = labsGate ? labsGate.querySelector(".labs-gate-panel") : null;
const labsAccessInput = document.getElementById("labsAccessInput");
const labsVerifyButton = document.getElementById("labsVerifyButton");
const labsGateFeedback = document.getElementById("labsGateFeedback");

const PREP_RING_CIRCUMFERENCE = 188.5;
const PREP_GRADE_MAP = {
    NSEJS: { Physics: 92, Chemistry: 81, Math: 86 },
    IOQM: { Physics: 58, Chemistry: 47, Math: 95 },
    JEE: { Physics: 66, Chemistry: 63, Math: 69 },
    "JEE ADVANCED": { Physics: 66, Chemistry: 63, Math: 69 },
};

let activeExam = "NSEJS";
let sending = false;
let conversationHistory = [];
let selectedImageBase64 = "";
let selectedImagePreviewDataUrl = "";
let commandHistory = [];
let historyIndex = 0;
let activeSimulationPoller = null;
let activeSimulationTaskId = "";
let lastSimulationUpdateSignature = "";
let activeTraceTicker = null;
let activeTraceStatusStep = null;
let activeSolveStep = null;
let isTesterMode = false;
let currentStreak = 0;
let problemsSolved = 0;
let timeSaved = 0;
let warmupNoticeTimerId = null;
let statusBannerNode = null;
const frontendBootTimeMs = Date.now();
let marathonElapsedSeconds = 0;
let marathonIntervalId = null;
let progressData = loadProgressData();
let lastUserPromptForVault = "";
let sessionTurnHistory = [];
let vaultEntriesCache = [];
let vaultEntriesLoaded = false;
let appInitialized = false;
let systemHeartbeatTimerId = null;
let thinkingTickerId = null;
let activeSyllabusTopic = "";
let latestSyllabusPayload = null;
let masteryChecklistState = loadMasteryChecklistState();
const SESSION_ID = getSessionId();
const THINKING_STATUS_FRAMES = ["Processing...", "E = mc²", "Addix Brain Online..."];
const PREMIUM_QUERY_PROMPT = "ADDIX Scholars Online. Input PCM query for deterministic resolution...";
const TESTER_QUERY_PROMPT = "ADDIX Scholars [Tester]: Enter topic for problem generation...";
const MASTERY_STORAGE_KEY = "addix_mastery";

window.onerror = function globalFrontendErrorHandler(message, source, lineno, colno, error) {
    console.error("ADDIX Scholars frontend error:", { message, source, lineno, colno, error });
    recoverFromMinorInterruption();
    return true;
};

window.onunhandledrejection = function globalPromiseRejectionHandler(event) {
    const reason = event && Object.prototype.hasOwnProperty.call(event, "reason") ? event.reason : event;
    console.error("ADDIX Scholars unhandled promise rejection:", reason);
    recoverFromMinorInterruption();
    if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
    }
};

async function apiFetch(url, options = {}) {
    if (!isGateGranted()) {
        return buildSafeFetchErrorResponse();
    }

    return safeFetch(url, {
        ...options,
        headers: new Headers(options.headers || {}),
    });
}

function buildSafeFetchErrorResponse() {
    const payload = {
        error: true,
        message:
            "Reconnecting to Engine… The cloud backend may be waking up (Render free tier can take ~60s). Please try again in a moment.",
    };
    return {
        ok: false,
        status: 0,
        error: true,
        message: payload.message,
        json: async () => payload,
        text: async () => JSON.stringify(payload),
    };
}

async function safeFetch(url, options = {}) {
    const timeoutController = new AbortController();
    const externalSignal = options.signal;
    let externalAbortHandler = null;

    if (externalSignal) {
        if (externalSignal.aborted) {
            timeoutController.abort();
        } else {
            externalAbortHandler = () => {
                timeoutController.abort();
            };
            externalSignal.addEventListener("abort", externalAbortHandler, { once: true });
        }
    }

    const timeoutId = window.setTimeout(() => {
        timeoutController.abort();
    }, API_CALL_TIMEOUT_MS);
    warmupNoticeTimerId = window.setTimeout(() => {
        showEngineStatusBanner("Scholars Engine is waking up... ☕");
    }, ENGINE_WAKE_NOTICE_DELAY_MS);

    try {
        return await fetch(url, {
            ...options,
            signal: timeoutController.signal,
        });
    } catch (error) {
        console.error("safeFetch failure", error);
        return buildSafeFetchErrorResponse();
    } finally {
        window.clearTimeout(timeoutId);
        if (warmupNoticeTimerId) {
            window.clearTimeout(warmupNoticeTimerId);
            warmupNoticeTimerId = null;
        }
        hideEngineStatusBanner();
        if (externalSignal && externalAbortHandler) {
            externalSignal.removeEventListener("abort", externalAbortHandler);
        }
    }
}

function getOrCreateStatusBanner() {
    if (statusBannerNode && document.body.contains(statusBannerNode)) {
        return statusBannerNode;
    }
    const banner = document.createElement("div");
    banner.id = "engine-status-banner";
    banner.className = "engine-status-banner";
    banner.hidden = true;
    document.body.appendChild(banner);
    statusBannerNode = banner;
    return banner;
}

function showEngineStatusBanner(message) {
    const banner = getOrCreateStatusBanner();
    banner.textContent = String(message || "Scholars Engine is waking up... ☕");
    banner.hidden = false;
    banner.classList.add("is-visible");
}

function hideEngineStatusBanner() {
    const banner = getOrCreateStatusBanner();
    banner.classList.remove("is-visible");
    banner.hidden = true;
}

function setComposerBusy(isBusy) {
    const busy = Boolean(isBusy);
    if (queryInput) {
        queryInput.disabled = busy;
        queryInput.placeholder = busy
            ? "Engine computing..."
            : (isTesterMode ? TESTER_QUERY_PROMPT : PREMIUM_QUERY_PROMPT);
    }
    if (sendButton) {
        sendButton.disabled = busy;
        sendButton.setAttribute("aria-busy", busy ? "true" : "false");
    }
    if (buttonText) {
        buttonText.textContent = busy ? "Engine computing..." : "Send";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initializeAccessGateway();
});

window.addEventListener("load", () => {
    void registerServiceWorker();
});

async function initializeApp() {
    if (appInitialized) {
        return;
    }
    appInitialized = true;
    updateGlobalStatus(false);

    hydrateHudFromMarkup();
    startCountdownSync();
    bindHudInteractions();
    bindChatInteractions();
    bindRapidMathKeyboard();
    bindVisionInteractions();
    wireMultimodalUiHandlers();
    bindExamContextSelector();
    bindSyllabusChipInteractions();
    bindEngineModeToggle();
    bindClearChatButton();
    bindExportSession();
    bindFormulaSheetExport();
    bindFocusMode();
    bindDebriefSession();
    bindBlackBoxVault();
    bindPremiumExport();
    bindMobileSidebarToggle();
    bindMarathonTimer();
    initializeProgressDashboard();
    updatePremiumUiState();

    checkEngineStatus();

    await Promise.all([
        hydrateAnalyticsFromDatabase(),
        hydrateStatsFromDatabase(),
        hydrateVaultEntries(),
        verifyConnection(),
    ]);

    if (!systemHeartbeatTimerId) {
        systemHeartbeatTimerId = window.setInterval(() => {
            void verifyConnection();
        }, 5000);
    }

    ensureStoicWelcomeMessage();
    updateAnalyticsDashboard(false);
    window.requestAnimationFrame(() => {
        renderMath(document.body);
    });
    if (queryInput) {
        updateQueryPlaceholder();
        window.requestAnimationFrame(() => {
            queryInput.focus();
        });
    }

    updatePreparationGradeRings(activeExam);
    await loadSyllabusForExam(activeExam);
}

function isGateGranted() {
    try {
        return window.sessionStorage.getItem(ACCESS_STATUS_STORAGE_KEY) === "granted";
    } catch (error) {
        return false;
    }
}

function markGateGranted() {
    try {
        window.sessionStorage.setItem(ACCESS_STATUS_STORAGE_KEY, "granted");
    } catch (error) {
        // Ignore storage failures.
    }
}

function setGatewayLockState(locked) {
    document.body.classList.toggle("gate-locked", Boolean(locked));

    if (labsGate) {
        labsGate.style.display = locked ? "flex" : "none";
        if (locked) {
            labsGate.removeAttribute("hidden");
        }
    }

    if (addixScholarsShell) {
        addixScholarsShell.style.display = locked ? "none" : "flex";
    }
}
function showGatewayError(message) {
    if (labsGateFeedback) {
        labsGateFeedback.textContent = String(message || "Unauthorized Access");
        labsGateFeedback.classList.add("is-error");
    }
    if (labsAccessInput) {
        labsAccessInput.setAttribute("aria-invalid", "true");
    }
}

function clearGatewayError() {
    if (labsGateFeedback) {
        labsGateFeedback.textContent = "";
        labsGateFeedback.classList.remove("is-error");
    }
    if (labsAccessInput) {
        labsAccessInput.removeAttribute("aria-invalid");
    }
}

function showMainApp() {
    setGatewayLockState(false);

    if (labsGate) {
        labsGate.style.display = "none";
        labsGate.classList.add("is-hidden");
        window.setTimeout(() => {
            labsGate.setAttribute("hidden", "hidden");
        }, 360);
    }

    if (addixScholarsShell) {
        addixScholarsShell.style.display = "flex";
    }

    if (!appInitialized) {
        void initializeApp();
    }
}

function shakeGatewayPanel() {
    if (!labsGatePanel) {
        return;
    }
    labsGatePanel.classList.remove("is-shaking");
    void labsGatePanel.offsetWidth;
    labsGatePanel.classList.add("is-shaking");
}

function verifyAccess() {
    if (!labsAccessInput) {
        showMainApp();
        return true;
    }

    const enteredCode = String(labsAccessInput.value || "");
    if (enteredCode === ACCESS_CODE) {
        markGateGranted();
        clearGatewayError();
        showMainApp();
        return true;
    }

    showGatewayError("Unauthorized Access");
    shakeGatewayPanel();
    labsAccessInput.focus();
    labsAccessInput.select();
    return false;
}

function bindAccessGateway() {
    if (labsVerifyButton) {
        labsVerifyButton.addEventListener("click", verifyAccess);
    }
    if (labsAccessInput) {
        labsAccessInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                verifyAccess();
            }
        });
        labsAccessInput.addEventListener("input", () => {
            if (labsGateFeedback && labsGateFeedback.classList.contains("is-error")) {
                clearGatewayError();
            }
        });
    }
}

function initializeAccessGateway() {
    if (!labsGate) {
        void initializeApp();
        return;
    }

    if (isGateGranted()) {
        labsGate.classList.add("is-hidden");
        labsGate.setAttribute("hidden", "hidden");
        showMainApp();
        return;
    }

    setGatewayLockState(true);
    labsGate.removeAttribute("hidden");
    labsGate.classList.remove("is-hidden");
    bindAccessGateway();
    if (labsAccessInput) {
        window.requestAnimationFrame(() => {
            labsAccessInput.focus();
        });
    }
}

async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    try {
        await navigator.serviceWorker.register("./sw.js");
    } catch (error) {
        // Keep silent in production UI; PWA should degrade gracefully.
    }
}

function closeMobileSidebar() {
    document.body.classList.remove("mobile-sidebar-open");
    if (mobileSidebarToggle) {
        mobileSidebarToggle.setAttribute("aria-expanded", "false");
        mobileSidebarToggle.setAttribute("aria-label", "Open menu");
    }
}

function openMobileSidebar() {
    document.body.classList.add("mobile-sidebar-open");
    if (mobileSidebarToggle) {
        mobileSidebarToggle.setAttribute("aria-expanded", "true");
        mobileSidebarToggle.setAttribute("aria-label", "Close menu");
    }
}

function bindMobileSidebarToggle() {
    if (!mobileSidebarToggle || !sidebarPanel) {
        return;
    }

    mobileSidebarToggle.addEventListener("click", () => {
        const nextOpen = !document.body.classList.contains("mobile-sidebar-open");
        if (nextOpen) {
            openMobileSidebar();
            return;
        }
        closeMobileSidebar();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && document.body.classList.contains("mobile-sidebar-open")) {
            closeMobileSidebar();
        }
    });

    document.addEventListener("click", (event) => {
        if (!document.body.classList.contains("mobile-sidebar-open")) {
            return;
        }
        if (!(event.target instanceof Element)) {
            return;
        }
        const clickedInsideSidebar = Boolean(event.target.closest(".scholar-sidebar"));
        const clickedToggle = Boolean(event.target.closest("#mobileSidebarToggle"));
        if (!clickedInsideSidebar && !clickedToggle) {
            closeMobileSidebar();
        }
    });
}

function updatePremiumUiState() {
    if (!exportWeaknessReportButton) {
        return;
    }

    exportWeaknessReportButton.textContent = isPremiumUser
        ? "Export Weakness Report (PDF)"
        : "🔒 Export Weakness Report (PDF)";
}

function setPrepRingProgress(ringElement, valueElement, percent) {
    if (!ringElement) {
        return;
    }

    const safePercent = clamp(Number(percent) || 0, 0, 100);
    ringElement.style.strokeDasharray = String(PREP_RING_CIRCUMFERENCE);
    ringElement.style.strokeDashoffset = String(PREP_RING_CIRCUMFERENCE * (1 - safePercent / 100));
    if (valueElement) {
        valueElement.textContent = String(Math.round(safePercent)) + "%";
    }
}

function updatePreparationGradeRings(examKey) {
    const key = String(examKey || activeExam || "NSEJS").toUpperCase();
    const examGrades = PREP_GRADE_MAP[key] || PREP_GRADE_MAP.NSEJS;
    setPrepRingProgress(prepRingPhysics, prepRingPhysicsValue, examGrades.Physics);
    setPrepRingProgress(prepRingChemistry, prepRingChemistryValue, examGrades.Chemistry);
    setPrepRingProgress(prepRingMath, prepRingMathValue, examGrades.Math);
}

function bindExamContextSelector() {
    if (!examContextSelector) {
        updatePreparationGradeRings(activeExam);
        return;
    }
    const syllabusContainer = document.getElementById("syllabus-container");

    const currentValue = String(activeExam || "NSEJS").trim();
    const matchedOption = Array.from(examContextSelector.options).find((option) => String(option.value || "").toUpperCase() === currentValue.toUpperCase());
    examContextSelector.value = matchedOption ? String(matchedOption.value || "NSEJS") : "NSEJS";
    activeExam = examContextSelector.value;
    const initialSelectedValue = String(examContextSelector.value || "").trim();
    if (initialSelectedValue.toLowerCase() === "custom") {
        if (syllabusContainer) {
            syllabusContainer.style.display = "none";
        }
        hideSyllabusExplorer();
        appendCustomDataPrompt();
    } else if (initialSelectedValue) {
        if (syllabusContainer) {
            syllabusContainer.style.display = "flex";
        }
        updateQueryPlaceholder();
        updatePreparationGradeRings(activeExam);
        void loadSyllabusForExam(activeExam);
    }

    const onExamChange = (e) => {
        const selectedValue = String(e && e.target && e.target.value ? e.target.value : "").trim();
        activeExam = selectedValue || "NSEJS";
        activeSyllabusTopic = "";

        if (selectedValue.toLowerCase() === "custom") {
            if (syllabusContainer) {
                syllabusContainer.style.display = "none";
            }
            hideSyllabusExplorer();
            appendCustomDataPrompt();
        } else if (selectedValue) {
            if (syllabusContainer) {
                syllabusContainer.style.display = "flex";
            }
            updateQueryPlaceholder();
            showSyllabusExplorer();
            updatePreparationGradeRings(activeExam);
            void loadSyllabusForExam(selectedValue);
        } else {
            if (syllabusContainer) {
                syllabusContainer.style.display = "none";
            }
            hideSyllabusExplorer();
        }

        hudCards.forEach((item) => {
            const itemExam = String(item.dataset.exam || "").toUpperCase();
            item.classList.toggle("is-active", itemExam === String(activeExam).toUpperCase());
        });
    };

    examContextSelector.addEventListener("change", onExamChange);
}

function normalizeExamForMastery(examName) {
    const normalized = String(examName || "NSEJS").trim().toUpperCase();
    if (normalized === "JEE") {
        return "JEE ADVANCED";
    }
    return normalized;
}

function getHudCardForExam(examName) {
    const examKey = normalizeExamForMastery(examName);
    return hudCards.find((card) => normalizeExamForMastery(card.dataset.exam || "") === examKey) || null;
}

function getSyllabusSlotForExam(examName) {
    const card = getHudCardForExam(examName);
    if (card) {
        return card.querySelector(".hud-card-syllabus-slot");
    }

    const activeCard = getHudCardForExam(activeExam);
    if (activeCard) {
        return activeCard.querySelector(".hud-card-syllabus-slot");
    }

    const firstSlot = document.querySelector(".hud-card-syllabus-slot");
    return firstSlot instanceof HTMLElement ? firstSlot : null;
}

function clearAllSyllabusSlots() {
    hudCards.forEach((card) => {
        card.classList.remove("has-syllabus-matrix");
    });
    document.querySelectorAll(".hud-card-syllabus-slot").forEach((slot) => {
        if (!(slot instanceof HTMLElement)) {
            return;
        }
        slot.innerHTML = "";
        slot.hidden = true;
    });
}

function buildTopicMasteryStorageKey(topicName) {
    const slug = String(topicName || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
    return slug ? "addix_mastery_" + slug : "";
}

function readTopicMasteryFlag(topicName) {
    const key = buildTopicMasteryStorageKey(topicName);
    if (!key) {
        return false;
    }
    try {
        return String(window.localStorage.getItem(key) || "").trim().toLowerCase() === "true";
    } catch (error) {
        return false;
    }
}

function writeTopicMasteryFlag(topicName, isCompleted) {
    const key = buildTopicMasteryStorageKey(topicName);
    if (!key) {
        return;
    }
    try {
        window.localStorage.setItem(key, Boolean(isCompleted) ? "true" : "false");
    } catch (error) {
        // Ignore local storage write failures.
    }
}

function loadMasteryChecklistState() {
    try {
        const raw = String(window.localStorage.getItem(MASTERY_STORAGE_KEY) || "").trim();
        if (!raw) {
            return {};
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return {};
        }
        return parsed;
    } catch (error) {
        return {};
    }
}

function saveMasteryChecklistState() {
    try {
        window.localStorage.setItem(MASTERY_STORAGE_KEY, JSON.stringify(masteryChecklistState || {}));
    } catch (error) {
        // Ignore local storage write failures.
    }
}

function isTopicCompleted(examName, topicName) {
    const examKey = normalizeExamForMastery(examName);
    const topicKey = String(topicName || "").trim().toLowerCase();
    if (!examKey || !topicKey) {
        return false;
    }
    const examMap = masteryChecklistState && typeof masteryChecklistState === "object"
        ? masteryChecklistState[examKey]
        : null;
    if (!examMap || typeof examMap !== "object") {
        return readTopicMasteryFlag(topicName);
    }
    return Boolean(examMap[topicKey]) || readTopicMasteryFlag(topicName);
}

function setTopicCompleted(examName, topicName, isCompleted) {
    const examKey = normalizeExamForMastery(examName);
    const topicKey = String(topicName || "").trim().toLowerCase();
    if (!examKey || !topicKey) {
        return;
    }
    const nextState = {
        ...(masteryChecklistState && typeof masteryChecklistState === "object" ? masteryChecklistState : {}),
    };
    const examState = {
        ...(nextState[examKey] && typeof nextState[examKey] === "object" ? nextState[examKey] : {}),
    };
    examState[topicKey] = Boolean(isCompleted);
    nextState[examKey] = examState;
    masteryChecklistState = nextState;
    saveMasteryChecklistState();
    writeTopicMasteryFlag(topicName, isCompleted);
}

function applyChipCompletionUi(chipButton, isCompleted) {
    if (!chipButton) {
        return;
    }
    chipButton.classList.toggle("mastered", Boolean(isCompleted));
    chipButton.classList.toggle("is-complete", Boolean(isCompleted));
    const checkNode = chipButton.querySelector(".syllabus-chip-check");
    if (checkNode) {
        checkNode.textContent = Boolean(isCompleted) ? "✔" : "";
    }
}

function findRenderedTopicName(rawTopicName) {
    const desired = String(rawTopicName || "").trim().toLowerCase();
    if (!desired) {
        return "";
    }
    const activeSlot = getSyllabusSlotForExam(activeExam);
    const activeSlotChips = activeSlot
        ? Array.from(activeSlot.querySelectorAll(".syllabus-chip-button[data-syllabus-topic]"))
        : [];
    const chips = activeSlotChips.length
        ? activeSlotChips
        : Array.from(document.querySelectorAll(".hud-card-syllabus-slot .syllabus-chip-button[data-syllabus-topic]"));
    const exact = chips.find((chip) => String(chip.dataset.syllabusTopic || "").trim().toLowerCase() === desired);
    if (exact) {
        return String(exact.dataset.syllabusTopic || "").trim();
    }
    const fuzzy = chips.find((chip) => {
        const rendered = String(chip.dataset.syllabusTopic || "").trim().toLowerCase();
        return rendered.includes(desired) || desired.includes(rendered);
    });
    return fuzzy ? String(fuzzy.dataset.syllabusTopic || "").trim() : "";
}

function cssEscape(value) {
    return String(value || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function markTopicComplete(topicName, examName = activeExam) {
    const resolvedTopic = findRenderedTopicName(topicName) || String(topicName || "").trim();
    if (!resolvedTopic) {
        return;
    }
    const resolvedExam = String(examName || activeExam || "NSEJS").trim() || "NSEJS";
    setTopicCompleted(resolvedExam, resolvedTopic, true);
    const selector =
        '.hud-card-syllabus-slot .syllabus-chip-button[data-syllabus-topic="' + cssEscape(resolvedTopic) + '"]' +
        '[data-syllabus-exam="' + cssEscape(resolvedExam) + '"]';
    document.querySelectorAll(selector).forEach((chipNode) => {
        if (chipNode instanceof HTMLElement) {
            applyChipCompletionUi(chipNode, true);
        }
    });
}

function detectCompletedTopicFromUserText(text) {
    const normalized = String(text || "").trim();
    if (!normalized) {
        return "";
    }
    const match = normalized.match(/i\s*am\s*done\s*with\s+([a-z0-9\s+\-&,()]+)/i);
    return match && match[1] ? String(match[1]).trim() : "";
}

function detectCompletedTopicFromAiText(text) {
    const normalized = String(text || "").trim();
    if (!normalized) {
        return "";
    }
    const patterns = [
        /mastery\s*(?:achieved|completed|unlocked)\s*:\s*([^\n\.]+)/i,
        /you(?:\s*have|\'ve)\s*(?:mastered|completed)\s+([^\n\.]+)/i,
    ];
    for (const pattern of patterns) {
        const match = normalized.match(pattern);
        if (match && match[1]) {
            return String(match[1]).trim();
        }
    }
    return "";
}

function normalizeSyllabusPayload(payload) {
    if (payload && typeof payload === "object" && !Array.isArray(payload)) {
        const syllabus = Array.isArray(payload.syllabus)
            ? payload.syllabus.filter((item) => typeof item === "string" && item.trim())
            : [];
        const physics = Array.isArray(payload.Physics) ? payload.Physics : [];
        const chemistry = Array.isArray(payload.Chemistry) ? payload.Chemistry : [];
        const math = Array.isArray(payload.Math) ? payload.Math : [];
        return {
            syllabus,
            Physics: physics.filter((item) => typeof item === "string" && item.trim()),
            Chemistry: chemistry.filter((item) => typeof item === "string" && item.trim()),
            Math: math.filter((item) => typeof item === "string" && item.trim()),
        };
    }

    return {
        syllabus: [],
        Physics: [],
        Chemistry: [],
        Math: [],
    };
}



function renderSyllabusSections(payload, isLoading = false, examName = activeExam) {
    const safeExam = String(examName || activeExam || "NSEJS").trim() || "NSEJS";
    const targetCard = getHudCardForExam(safeExam) || getHudCardForExam(activeExam) || hudCards[0] || null;
    const targetSlot = getSyllabusSlotForExam(safeExam);
    if (!targetCard || !targetSlot) {
        return;
    }

    clearAllSyllabusSlots();
    targetSlot.classList.add("syllabus-container");

    if (isLoading) {
        targetCard.classList.add("has-syllabus-matrix");
        targetSlot.hidden = false;
        targetSlot.innerHTML =
            '<div class="syllabus-category"><h4>PHYSICS</h4><div class="syllabus-chip-row"><span class="syllabus-chip syllabus-chapter-item">Loading Syllabus...</span></div></div>' +
            '<div class="syllabus-category"><h4>CHEMISTRY</h4><div class="syllabus-chip-row"><span class="syllabus-chip syllabus-chapter-item">Loading Syllabus...</span></div></div>' +
            '<div class="syllabus-category"><h4>MATH</h4><div class="syllabus-chip-row"><span class="syllabus-chip syllabus-chapter-item">Loading Syllabus...</span></div></div>';
        return;
    }

    const normalized = normalizeSyllabusPayload(payload);
    latestSyllabusPayload = normalized;
    const genericChips = normalized.syllabus;
    const physicsChips = normalized.Physics;
    const chemistryChips = normalized.Chemistry;
    const mathChips = normalized.Math;

    const buildGroup = (heading, chips) => {
        const renderedChips = chips.map((chip) => {
            const topic = String(chip || "").trim();
            if (!topic) {
                return "";
            }
            const activeClass = topic.toLowerCase() === activeSyllabusTopic.toLowerCase()
                ? " is-active"
                : "";
            const mastered = isTopicCompleted(safeExam, topic);
            const completeClass = mastered ? " mastered is-complete" : "";
            const checkMark = mastered ? "✔" : "";
            return '<button type="button" class="syllabus-chip syllabus-chip-button syllabus-chapter-item' + activeClass + completeClass + '" data-syllabus-topic="' + escapeHtml(topic) + '" data-syllabus-exam="' + escapeHtml(safeExam) + '"><span class="syllabus-chip-check" aria-hidden="true">' + checkMark + '</span><span class="syllabus-chip-text">' + escapeHtml(topic) + '</span></button>';
        }).join("");
        return '<div class="syllabus-category"><h4>' + heading + '</h4><div class="syllabus-chip-row">' + renderedChips + '</div></div>';
    };

    targetCard.classList.add("has-syllabus-matrix");
    targetSlot.hidden = false;
    if (genericChips.length) {
        targetSlot.innerHTML = buildGroup(safeExam + " SYLLABUS", genericChips);
        return;
    }
    if (!physicsChips.length && !chemistryChips.length && !mathChips.length) {
        targetSlot.innerHTML = '<div class="syllabus-category"><h4>SYLLABUS</h4><div class="syllabus-chip-row"><span class="syllabus-chip syllabus-chapter-item">No syllabus topics returned by API.</span></div></div>';
        return;
    }

    targetSlot.innerHTML =
        buildGroup("PHYSICS", physicsChips) +
        buildGroup("CHEMISTRY", chemistryChips) +
        buildGroup("MATH", mathChips);
}

function showSyllabusExplorer() {
    if (!syllabusExplorerPanel) {
        return;
    }
    syllabusExplorerPanel.hidden = false;
    syllabusExplorerPanel.style.display = "flex";
}

function hideSyllabusExplorer() {
    clearAllSyllabusSlots();
    if (!syllabusExplorerPanel) {
        return;
    }
    syllabusExplorerPanel.style.display = "none";
    syllabusExplorerPanel.hidden = true;
}

function isCustomExamSelection(selectElement) {
    if (!selectElement) {
        return false;
    }

    const selectedValue = String(selectElement.value || "").trim().toLowerCase();
    return selectedValue === "custom";
}

function appendCustomDataPrompt() {
    const html =
        '<article class="message system-step custom-data-step">' +
            '<p class="message-line"><span class="agent-label">[ADDIX System]:</span> Please type or paste your custom syllabus topics below to initialize the custom matrix.</p>' +
        '</article>';
    appendMessage(html);

    if (queryInput) {
        queryInput.placeholder = "Please type or paste your custom syllabus topics below to initialize the custom matrix.";
        queryInput.focus();
    }
}

function bindSyllabusChipInteractions() {
    if (!hudGrid) {
        return;
    }

    hudGrid.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const chipButton = event.target.closest(".syllabus-chip-button[data-syllabus-topic]");
        if (!(chipButton instanceof HTMLElement)) {
            return;
        }

        const topic = String(chipButton.dataset.syllabusTopic || "").trim();
        if (!topic) {
            return;
        }

        setActiveSyllabusChip(chipButton);
        const examValue = String(chipButton.dataset.syllabusExam || activeExam || "NSEJS").trim() || "NSEJS";
        const currentlyComplete = chipButton.classList.contains("is-complete");
        const nextComplete = !currentlyComplete;
        setTopicCompleted(examValue, topic, nextComplete);
        applyChipCompletionUi(chipButton, nextComplete);
    });
}

function setActiveSyllabusChip(activeButton) {
    document.querySelectorAll(".hud-card-syllabus-slot .syllabus-chip-button.is-active").forEach((node) => {
        node.classList.remove("is-active");
    });
    if (activeButton) {
        activeButton.classList.add("is-active");
        activeSyllabusTopic = String(activeButton.dataset.syllabusTopic || "").trim();
    }
}

function appendPyqBootstrapMessage(topic) {
    const html =
        '<article class="message system-step pyq-bootstrap-step">' +
            '<p class="message-line"><span class="agent-label">[ADDIX Scholars]:</span> Initializing PYQ Matrix for ' + escapeHtml(topic) + '...</p>' +
        '</article>';
    appendMessage(html);
}

function appendPyqVariantMessage(markdownText, topic, exam) {
    const htmlContent = renderMarkdownContent(String(markdownText || ""));
    const html =
        '<article class="message final-step mentor-structured pyq-variant-step">' +
            '<div class="message-engine-trace">PYQ Variant Engine · ' + escapeHtml(exam) + ' · ' + escapeHtml(topic) + '</div>' +
            '<div class="agent-row">' +
                '<span class="agent-pulse"></span>' +
                '<span class="agent-label">[ADDIX Mentor]:</span>' +
                '<div class="message-line mentor-guidance-line" data-ai-response></div>' +
            '</div>' +
        '</article>';
    const element = appendMessage(html);
    const messageDiv = element ? element.querySelector("[data-ai-response]") : null;
    if (messageDiv) {
        messageDiv.innerHTML = htmlContent;
        if (typeof renderMathInElement === "function") {
            renderMathInElement(messageDiv, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false }
                ],
                throwOnError: false,
                errorCallback: function katexRenderFallback(message, error) {
                    console.warn("KaTeX render fallback:", message, error);
                }
            });
        }
        void renderDiagrams(messageDiv);
    }
}

function buildApiHeaders() {
    return new Headers({ "Content-Type": "application/json" });
}

async function triggerPyqVariantGeneration(topic, chipButton) {
    const safeTopic = String(topic || "").trim();
    if (!safeTopic) {
        return;
    }

    const examContext = examContextSelector && typeof examContextSelector.value === "string" && examContextSelector.value.trim()
        ? examContextSelector.value.trim()
        : String(activeExam || "NSEJS");

    setActiveSyllabusChip(chipButton);
    appendPyqBootstrapMessage(safeTopic);
    pushConversationMessage("assistant", "Initializing PYQ Matrix for " + safeTopic + "...");
    pushConversationMessage("user", "Generate PYQ variants for " + safeTopic + " in " + examContext + ".");

    let response;
    try {
        response = await safeFetch(BASE_URL + "/api/pyq/generate", {
            method: "POST",
            headers: buildApiHeaders(),
            body: JSON.stringify({ exam: examContext, topic: safeTopic }),
        });
    } catch (error) {
        appendErrorStep("PYQ Matrix request failed. Please retry.");
        return;
    }

    if (!response || !response.ok) {
        const failureText = response ? await response.text().catch(() => "") : "";
        renderSystemAlertBubble(buildSystemAlertMessage(response ? response.status : 500, failureText));
        return;
    }

    const payload = await response.json().catch(() => ({}));
    const generatedText = typeof payload.generated_text === "string" && payload.generated_text.trim()
        ? payload.generated_text.trim()
        : "**[ OFFICIAL PYQ ]**\\nNo PYQ could be generated at this moment.";

    appendPyqVariantMessage(generatedText, safeTopic, examContext);
    pushConversationMessage("assistant", generatedText);
}

async function loadSyllabusForExam(examName) {
    const safeExamName = String(examName || "NSEJS").trim() || "NSEJS";
    const targetSlot = getSyllabusSlotForExam(safeExamName);
    if (!targetSlot) {
        return;
    }
    showSyllabusExplorer();
    renderSyllabusSections(null, true, safeExamName);

    try {
        const payload = await fetchSyllabus(safeExamName);
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
            throw new Error("syllabus-object-required");
        }
        if (payload.error || !payload.syllabus) {
            throw new Error("syllabus-payload-missing");
        }
        renderSyllabusSections(payload, false, safeExamName);
    } catch (error) {
        console.error("Failed to load syllabus for exam:", safeExamName, error);
        targetSlot.classList.add("syllabus-container");
        targetSlot.hidden = false;
        targetSlot.innerHTML =
            '<div class="syllabus-category">' +
                '<h4 style="color:#ff4d5f;margin-bottom:8px;">CONNECTION ERROR</h4>' +
                '<p style="color:#a0aec0;font-size:0.8rem;margin-bottom:12px;">Could not load the ' + safeExamName + ' syllabus. Check your connection.</p>' +
                '<button class="syllabus-retry-btn" style="' +
                    'background:rgba(0,255,255,0.08);' +
                    'border:1px solid rgba(0,255,255,0.35);' +
                    'color:#00ffff;' +
                    'padding:8px 18px;' +
                    'border-radius:8px;' +
                    'font-size:0.78rem;' +
                    'letter-spacing:0.06em;' +
                    'text-transform:uppercase;' +
                    'cursor:pointer;' +
                    'transition:background 150ms ease;' +
                    '" onclick="loadSyllabusForExam(' + JSON.stringify(safeExamName) + ')">↺ Retry</button>' +
            '</div>';
    }
}

async function fetchSyllabus(exam) {
    const safeExam = String(exam || "NSEJS").trim() || "NSEJS";
    const encodedExam = encodeURIComponent(safeExam);
    const syllabusUrl = BASE_URL + "/api/syllabus/" + encodedExam;

    try {
        const response = await safeFetch(syllabusUrl, {
            method: "GET",
            headers: buildApiHeaders(),
        });

        if (response && response.error) {
            console.error("[SyllabusFetch] Bridge failure", { exam: safeExam, url: syllabusUrl });
            throw new Error("syllabus-bridge-failed");
        }
        if (!response || !response.ok) {
            const statusCode = response ? response.status : "no response";
            console.error("[SyllabusFetch] HTTP failure", { exam: safeExam, url: syllabusUrl, status: statusCode });
            const statusError = new Error("syllabus-fetch-failed: " + statusCode);
            statusError.statusCode = statusCode;
            throw statusError;
        }
        const data = await response.json();
        if (!data || typeof data !== "object" || Array.isArray(data)) {
            throw new Error("syllabus-payload-invalid");
        }
        return data;
    } catch (error) {
        const statusCode = error && error.statusCode ? error.statusCode : "unknown";
        console.error("[SyllabusFetch] Catch", { exam: safeExam, url: syllabusUrl, status: statusCode, error });
        throw error;
    }
}

function updateQueryPlaceholder() {
    if (!queryInput) {
        return;
    }
    queryInput.placeholder = isTesterMode ? TESTER_QUERY_PROMPT : PREMIUM_QUERY_PROMPT;
}

function updateEngineModeUiState() {
    if (engineModeLabel) {
        engineModeLabel.textContent = isTesterMode ? "TESTER" : "SOLVER";
    }
    document.body.classList.toggle("tester-mode", isTesterMode);
    updateQueryPlaceholder();
}

function ensureStoicWelcomeMessage() {
    if (!chatFeed || chatFeed.querySelector(".message")) {
        return;
    }

    const html =
        '<article class="message system-step">' +
            '<p class="message-line"><span class="agent-label">System:</span> ' + PREMIUM_QUERY_PROMPT + '</p>' +
        '</article>';

    appendMessage(html);
}

function getDateKey(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
}

function createEmptyProgressData() {
    return { topics: { Physics: 0, Math: 0, Chem: 0 } };
}

function loadProgressData() {
    return createEmptyProgressData();
}

function saveProgressData() {
    // Progress is persisted through backend analytics endpoints.
}

async function fetchAnalyticsSnapshot() {
    const response = await apiFetch(BASE_URL + "/api/analytics", { method: "GET" });
    if (!response.ok) {
        throw new Error("analytics-fetch-failed");
    }
    return await response.json();
}

async function fetchUserStatsSnapshot() {
    const response = await apiFetch(BASE_URL + "/api/stats", { method: "GET" });
    if (!response.ok) {
        throw new Error("stats-fetch-failed");
    }
    return await response.json();
}

async function hydrateStatsFromDatabase() {
    try {
        const payload = await fetchUserStatsSnapshot();
        currentStreak = Math.max(0, Math.floor(Number(payload?.current_streak) || 0));
        const solvedCount = Math.max(0, Math.floor(Number(payload?.total_solved) || 0));
        problemsSolved = solvedCount;
        timeSaved = solvedCount * 12;
        updateAnalyticsDashboard(false);
    } catch (error) {
        // Keep current UI values when stats service is temporarily unavailable.
    }
}

async function syncAnalyticsDelta(dateKey, deltas) {
    try {
        await apiFetch(BASE_URL + "/api/analytics/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date: dateKey,
                problems_delta: Number(deltas.problems || 0),
                physics_delta: Number(deltas.physics || 0),
                math_delta: Number(deltas.math || 0),
            }),
        });
    } catch (error) {
        // Keep UI responsive when analytics sync is temporarily unavailable.
    }
}

async function hydrateAnalyticsFromDatabase() {
    try {
        const payload = await fetchAnalyticsSnapshot();
        const items = Array.isArray(payload?.items) ? payload.items : [];
        const totals = payload?.totals && typeof payload.totals === "object" ? payload.totals : {};

        const nextProgress = createEmptyProgressData();
        items.forEach((item) => {
            const dateKey = String(item?.date || "").trim();
            if (!/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) {
                return;
            }
            const solved = Math.max(0, Math.floor(Number(item?.problems_solved) || 0));
            nextProgress[dateKey] = solved;
        });

        nextProgress.topics.Physics = Math.max(0, Math.floor(Number(totals?.physics_count) || 0));
        nextProgress.topics.Math = Math.max(0, Math.floor(Number(totals?.math_count) || 0));
        nextProgress.topics.Chem = 0;

        progressData = nextProgress;
        problemsSolved = Math.max(0, Math.floor(Number(totals?.problems_solved) || 0));
        timeSaved = problemsSolved * 12;

        refreshProgressDashboard();
    } catch (error) {
        // Keep in-memory defaults when backend sync is unavailable.
    }
}

function getConsistencyIntensityClass(count) {
    if (count >= 16) {
        return "consistency-high";
    }
    if (count >= 6) {
        return "consistency-medium";
    }
    if (count >= 1) {
        return "consistency-low";
    }
    return "consistency-empty";
}

function getDailyCount(dateKey) {
    return Math.max(0, Math.floor(Number(progressData[dateKey]) || 0));
}

function normalizeTopicTags(topics) {
    if (!Array.isArray(topics)) {
        return [];
    }

    const normalized = [];
    topics.forEach((topic) => {
        const text = String(topic || "").trim();
        if (!text) {
            return;
        }
        if (normalized.some((item) => item.toLowerCase() === text.toLowerCase())) {
            return;
        }
        normalized.push(text);
    });
    return normalized.slice(0, 4);
}

function renderTopicTags(topics) {
    const normalized = normalizeTopicTags(topics);
    if (!normalized.length) {
        return "";
    }

    return (
        '<div class="topic-tags">' +
            normalized.map((topic) => '<span class="topic-tag">' + escapeHtml(topic) + '</span>').join("") +
        '</div>'
    );
}

function initializeProgressDashboard() {
    if (consistencyMatrix) {
        consistencyMatrix.innerHTML = "";
        const today = new Date();
        const cells = [];

        for (let offset = CONSISTENCY_MATRIX_DAYS - 1; offset >= 0; offset -= 1) {
            const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset);
            const dateKey = getDateKey(date);
            const count = getDailyCount(dateKey);
            const cell = document.createElement("div");
            cell.className = "consistency-cell " + getConsistencyIntensityClass(count);
            cell.dataset.date = dateKey;
            cell.dataset.count = String(count);
            cell.title = dateKey + ": " + String(count) + " problem" + (count === 1 ? "" : "s");
            cells.push(cell);
        }

        cells.forEach((cell) => {
            consistencyMatrix.appendChild(cell);
        });
    }

    renderMasteryBreakdown();
}

function refreshProgressDashboard() {
    if (consistencyMatrix) {
        const cells = Array.from(consistencyMatrix.querySelectorAll(".consistency-cell"));
        cells.forEach((cell) => {
            const dateKey = cell.dataset.date || "";
            const count = getDailyCount(dateKey);
            cell.dataset.count = String(count);
            cell.classList.remove("consistency-empty", "consistency-low", "consistency-medium", "consistency-high");
            cell.classList.add(getConsistencyIntensityClass(count));
            cell.title = dateKey + ": " + String(count) + " problem" + (count === 1 ? "" : "s");
        });
    }

    renderMasteryBreakdown();
}

function incrementProgressForToday(topics) {
    const normalizedTopics = normalizeTopicTags(topics);
    if (!normalizedTopics.length) {
        return;
    }

    const todayKey = getDateKey(new Date());
    const currentCount = getDailyCount(todayKey);
    progressData[todayKey] = currentCount + 1;

    const subjectSet = new Set();
    normalizedTopics.forEach((topic) => {
        const subject = classifyTopicToSubject(topic);
        if (subject) {
            subjectSet.add(subject);
        }
    });

    subjectSet.forEach((subject) => {
        progressData.topics[subject] = Math.max(0, Math.floor(Number(progressData.topics[subject]) || 0)) + 1;
    });

    saveProgressData();
    refreshProgressDashboard();

    void syncAnalyticsDelta(todayKey, {
        problems: 1,
        physics: subjectSet.has("Physics") ? 1 : 0,
        math: subjectSet.has("Math") ? 1 : 0,
    });
}

function renderMasteryBreakdown() {
    if (!masteryBreakdown) {
        return;
    }

    const subjects = ["Physics", "Chem", "Math"];
    const totals = subjects.map((subject) => Math.max(0, Math.floor(Number(progressData.topics?.[subject]) || 0)));
    const highest = Math.max(...totals, 0);
    const maxForScaling = Math.max(highest, 1);

    masteryBreakdown.innerHTML = "";

    subjects.forEach((subject, index) => {
        const total = totals[index];
        const percentage = total > 0 ? Math.max(8, Math.round((total / maxForScaling) * 100)) : 0;
        const item = document.createElement("div");
        item.className = "mastery-item" + (total > 0 && total === highest ? " is-top" : "");

        const label = document.createElement("p");
        label.className = "mastery-label";
        label.textContent = subject;

        const track = document.createElement("div");
        track.className = "mastery-track";

        const fill = document.createElement("div");
        fill.className = "mastery-fill";
        fill.style.setProperty("--mastery-height", percentage + "%");
        fill.style.height = percentage + "%";

        track.appendChild(fill);

        const value = document.createElement("p");
        value.className = "mastery-value";
        value.textContent = String(total);

        item.appendChild(label);
        item.appendChild(track);
        item.appendChild(value);
        masteryBreakdown.appendChild(item);
    });
}

function classifyTopicToSubject(topic) {
    const normalized = String(topic || "").trim().toLowerCase();
    if (!normalized) {
        return "";
    }
    if (normalized.includes("chem")) {
        return "Chem";
    }
    if (normalized.includes("physics") || normalized.includes("mechanics") || normalized.includes("motion") || normalized.includes("energy") || normalized.includes("force") || normalized.includes("optics") || normalized.includes("thermo") || normalized.includes("electro") || normalized.includes("waves") || normalized.includes("grav")) {
        return "Physics";
    }
    if (normalized.includes("math") || normalized.includes("algebra") || normalized.includes("geometry") || normalized.includes("trigon") || normalized.includes("number theory") || normalized.includes("combinator") || normalized.includes("calculus") || normalized.includes("inequal") || normalized.includes("equation")) {
        return "Math";
    }
    return "Math";
}

function formatMarathonTime(totalSeconds) {

    function normalizeTopicTags(topics) {
        if (!Array.isArray(topics)) {
            return [];
        }

        const normalized = [];
        topics.forEach((topic) => {
            const text = String(topic || "").trim();
            if (!text) {
                return;
            }
            if (normalized.some((item) => item.toLowerCase() === text.toLowerCase())) {
                return;
            }
            normalized.push(text);
        });
        return normalized.slice(0, 4);
    }

    function renderTopicTags(topics) {
        const normalized = normalizeTopicTags(topics);
        if (!normalized.length) {
            return "";
        }

        return (
            '<div class="topic-tags">' +
                normalized.map((topic) => '<span class="topic-tag">' + escapeHtml(topic) + '</span>').join("") +
            '</div>'
        );
    }
    const safeSeconds = Math.max(0, Number(totalSeconds) || 0);
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;
    return [hours, minutes, seconds]
        .map((value) => String(value).padStart(2, "0"))
        .join(":");
}

function updateMarathonDisplay() {
    if (marathonTimerDisplay) {
        marathonTimerDisplay.textContent = formatMarathonTime(marathonElapsedSeconds);
    }
}

function bindMarathonTimer() {
    updateMarathonDisplay();

    if (!marathonStartButton || !marathonPauseButton || !marathonStopButton) {
        return;
    }

    marathonStartButton.addEventListener("click", () => {
        if (marathonIntervalId) {
            return;
        }
        marathonIntervalId = window.setInterval(() => {
            marathonElapsedSeconds += 1;
            updateMarathonDisplay();
        }, 1000);
        if (marathonTimerShell) {
            marathonTimerShell.classList.add("is-running");
        }
    });

    marathonPauseButton.addEventListener("click", () => {
        if (marathonIntervalId) {
            window.clearInterval(marathonIntervalId);
            marathonIntervalId = null;
        }
        if (marathonTimerShell) {
            marathonTimerShell.classList.remove("is-running");
        }
    });

    marathonStopButton.addEventListener("click", () => {
        stopMarathonTimer();
    });
}

function stopMarathonTimer() {
    if (marathonIntervalId) {
        window.clearInterval(marathonIntervalId);
        marathonIntervalId = null;
    }
    marathonElapsedSeconds = 0;
    updateMarathonDisplay();
    if (marathonTimerShell) {
        marathonTimerShell.classList.remove("is-running");
    }
}

function updateAnalyticsDashboard(shouldAnimate = true) {
    if (problemsSolvedValue) {
        problemsSolvedValue.textContent = String(problemsSolved);
        if (shouldAnimate) {
            problemsSolvedValue.classList.remove("pop");
            void problemsSolvedValue.offsetWidth;
            problemsSolvedValue.classList.add("pop");
        }
    }

    if (timeSavedValue) {
        timeSavedValue.textContent = String(timeSaved) + " mins";
        if (shouldAnimate) {
            timeSavedValue.classList.remove("pop");
            void timeSavedValue.offsetWidth;
            timeSavedValue.classList.add("pop");
        }
    }

    if (currentStreakValue) {
        const lockSuffix = currentStreak > 5 ? " 🔒" : "";
        currentStreakValue.textContent = "🔥 " + String(currentStreak) + lockSuffix;
        currentStreakValue.classList.toggle("is-locked", currentStreak > 5 && !isPremiumUser);
    }
}

function openPremiumModal() {
    if (!premiumModal) {
        return;
    }
    premiumModal.classList.add("is-open");
    premiumModal.setAttribute("aria-hidden", "false");
}

function closePremiumModal() {
    if (!premiumModal) {
        return;
    }
    premiumModal.classList.remove("is-open");
    premiumModal.setAttribute("aria-hidden", "true");
}

function showToast(message, kind = "success") {
    const toast = document.createElement("div");
    toast.textContent = String(message || "").trim();
    toast.style.position = "fixed";
    toast.style.right = "20px";
    toast.style.bottom = "20px";
    toast.style.padding = "12px 16px";
    toast.style.borderRadius = "10px";
    toast.style.background = kind === "success" ? "#0a0a0a" : "#7f1d1d";
    toast.style.color = "#ffffff";
    toast.style.fontWeight = "600";
    toast.style.zIndex = "9999";
    toast.style.boxShadow = "0 10px 24px rgba(0, 0, 0, 0.25)";
    document.body.appendChild(toast);
    window.setTimeout(() => {
        toast.remove();
    }, 2400);
}

function recoverFromMinorInterruption() {
    try {
        sending = false;
        removeComputingState();
        activeSolveStep = null;
        activeTraceStatusStep = null;
        if (activeTraceTicker) {
            stopTraceStatusTicker(activeTraceTicker, null, "ADDIX Scholars", "Recovering...");
            activeTraceTicker = null;
        }

        if (queryInput) {
            queryInput.disabled = false;
            queryInput.value = "";
            queryInput.blur();
            window.requestAnimationFrame(() => {
                queryInput.focus();
            });
        }

        if (sendButton) {
            sendButton.disabled = false;
        }
        setButtonThinking(false);
        showToast("[ADDIX Scholars System]: Recovering from minor interruption...", "error");
    } catch (recoveryError) {
        console.error("ADDIX Scholars recovery handler failed:", recoveryError);
    }
}

async function downloadWeaknessReportPdf() {
    const response = await apiFetch(BASE_URL + "/api/export/blackbox", {
        method: "GET",
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || "Failed to export weakness report.");
    }

    const blob = await response.blob();
    const fileUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    link.href = fileUrl;
    link.download = "addix_weakness_report_" + timestamp + ".pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(fileUrl);
}

async function downloadCheatSheet() {
    const topic = String(activeSyllabusTopic || "").trim();
    if (!topic) {
        appendErrorStep("Select a syllabus topic before exporting a formula sheet.");
        return;
    }

    const response = await apiFetch(BASE_URL + "/api/export-pdf/" + encodeURIComponent(topic), {
        method: "GET",
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || "Failed to export formula sheet.");
    }

    const blob = await response.blob();
    const fileUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeTopic = topic.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "Topic";
    link.href = fileUrl;
    link.download = "ADDIX_" + safeTopic + "_CheatSheet.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(fileUrl);
}

function bindFormulaSheetExport() {
    if (!exportFormulaSheetButton) {
        return;
    }

    exportFormulaSheetButton.addEventListener("click", async () => {
        exportFormulaSheetButton.disabled = true;
        try {
            await downloadCheatSheet();
        } catch (error) {
            const message = error && error.message ? String(error.message) : "Export failed.";
            appendErrorStep("Formula sheet export failed: " + message);
        } finally {
            exportFormulaSheetButton.disabled = false;
        }
    });
}

function bindPremiumExport() {
    if (exportWeaknessReportButton) {
        exportWeaknessReportButton.addEventListener("click", async () => {
            try {
                await downloadWeaknessReportPdf();
            } catch (error) {
                const message = error && error.message ? String(error.message) : "Export failed.";
                appendErrorStep("Weakness report export failed: " + message);
            }
        });
    }

    if (closePremiumModalButton) {
        closePremiumModalButton.addEventListener("click", () => {
            closePremiumModal();
        });
    }

    if (upgradeToPremiumButton) {
        upgradeToPremiumButton.addEventListener("click", async () => {
            upgradeToPremiumButton.disabled = true;
            try {
                await downloadWeaknessReportPdf();
                closePremiumModal();
                showToast("Premium features unlocked for local testing.", "success");
            } catch (error) {
                const message = error && error.message ? String(error.message) : "Unable to export report.";
                showToast(message, "error");
            } finally {
                upgradeToPremiumButton.disabled = false;
            }
        });
    }

    if (premiumModal) {
        premiumModal.addEventListener("click", (event) => {
            if (event.target === premiumModal) {
                closePremiumModal();
            }
        });
    }
}

function trackSuccessfulSolve() {
    problemsSolved += 1;
    timeSaved += 12;
    if (currentStreak <= 0) {
        currentStreak = 1;
    }
    updateAnalyticsDashboard(true);
}

function updateGlobalStatus(isOnline) {
    const online = Boolean(isOnline);
    const nextText = online ? "[ ONLINE ]" : "[ OFFLINE ]";

    [statusText, systemHealthLabel].forEach((node) => {
        if (!node) {
            return;
        }
        node.textContent = nextText;
        node.classList.toggle("status-online", online);
        node.classList.toggle("status-offline", !online);
        node.classList.remove("status-limited");
    });

    [statusDot, systemHealthDot].forEach((node) => {
        if (!node) {
            return;
        }
        node.classList.toggle("status-online", online);
        node.classList.toggle("status-offline", !online);
        node.classList.remove("status-limited");
    });
}

async function verifyConnection() {
    try {
        const response = await apiFetch(BASE_URL + "/api/vault", {
            method: "GET",
        });
        const isOnline = Boolean(response && response.ok);
        updateGlobalStatus(isOnline);
        return isOnline;
    } catch (error) {
        updateGlobalStatus(false);
        return false;
    }
}

async function checkSystemHealth() {
    return verifyConnection();
}

function checkEngineStatus() {
    void safeFetch(BASE_URL + "/health", {
        method: "GET",
        headers: new Headers({ Accept: "application/json" }),
    }).catch(() => {
        // Warm-up probe is best-effort and should never break UX.
    });
}

function bindClearChatButton() {
    if (!clearChatButton) {
        return;
    }
    clearChatButton.addEventListener("click", () => {
        clearTerminalFeed();
        conversationHistory = [];
        lastUserPromptForVault = "";
        appendMessage(
            '<article class="message system-step"><p class="message-line"><span class="agent-label">System:</span> Chat cleared. Solver standing by.</p></article>'
        );
    });
}

function bindExportSession() {
    if (!exportSessionButton) {
        return;
    }
    exportSessionButton.addEventListener("click", () => {
        void compileSession();
    });
}

function bindDebriefSession() {
    if (debriefSessionButton) {
        debriefSessionButton.addEventListener("click", () => {
            void requestSessionDebrief();
        });
    }

    if (closeDebriefButton) {
        closeDebriefButton.addEventListener("click", () => {
            closeDebriefModalPanel();
        });
    }

    if (debriefModal) {
        debriefModal.addEventListener("click", (event) => {
            if (event.target === debriefModal) {
                closeDebriefModalPanel();
            }
        });
    }
}

function openDebriefModal() {
    if (!debriefModal) {
        return;
    }
    debriefModal.classList.add("is-open");
    debriefModal.setAttribute("aria-hidden", "false");
}

function closeDebriefModalPanel() {
    if (!debriefModal) {
        return;
    }
    debriefModal.classList.remove("is-open");
    debriefModal.setAttribute("aria-hidden", "true");
}

function normalizeDebriefText(value) {
    if (Array.isArray(value)) {
        return value.map((item) => String(item || "").trim()).filter(Boolean).join("\n");
    }
    return String(value || "").trim();
}

function renderDebriefModal(data) {
    if (!debriefModalBody) {
        return;
    }

    const logicGaps = normalizeDebriefText(data?.logic_gaps) || "No clear weaknesses were identified.";
    const gritAssessment = normalizeDebriefText(data?.grit_assessment) || "No assessment available.";
    const closingDirective = normalizeDebriefText(data?.closing_directive) || "Rest, then return sharper.";
    const gritScoreMatch = gritAssessment.match(/\b(100|[1-9]?\d)\b/);
    const gritScore = gritScoreMatch ? Math.max(0, Math.min(100, Number(gritScoreMatch[1]) || 0)) : 72;

    const renderCard = (title, body, className) => {
        const lines = body.split(/\n+/).map((line) => line.trim()).filter(Boolean);
        const content = lines.length > 1
            ? '<ul class="debrief-list">' + lines.map((line) => '<li>' + escapeHtml(line) + '</li>').join("") + '</ul>'
            : '<p class="debrief-copy">' + escapeHtml(lines[0] || body) + '</p>';
        return (
            '<article class="debrief-card ' + className + '">' +
                '<p class="debrief-card-label">' + escapeHtml(title) + '</p>' +
                content +
            '</article>'
        );
    };

    const gritMeterMarkup =
        '<div class="grit-meter-shell" aria-label="Grit score ' + String(gritScore) + '">' +
            '<div class="grit-meter-track">' +
                '<div class="grit-meter-fill' + (gritScore > 90 ? ' is-elite' : '') + '" style="height:' + String(gritScore) + '%"></div>' +
            '</div>' +
            '<p class="grit-meter-score">' + String(gritScore) + '</p>' +
        '</div>';

    debriefModalBody.innerHTML =
        renderCard("Logic Gaps", logicGaps, "is-gap") +
        ('<article class="debrief-card is-grit">' +
            '<p class="debrief-card-label">Grit Assessment</p>' +
            '<div class="grit-meter-layout">' +
                gritMeterMarkup +
                '<p class="debrief-copy">' + escapeHtml(gritAssessment) + '</p>' +
            '</div>' +
        '</article>') +
        renderCard("Closing Directive", closingDirective, "is-closing");
}

function renderDebriefError(message) {
    if (!debriefModalBody) {
        return;
    }
    debriefModalBody.innerHTML = '<p class="debrief-error">' + escapeHtml(String(message || "Debrief failed.")) + '</p>';
}

async function requestSessionDebrief() {
    if (!debriefSessionButton) {
        return;
    }

    debriefSessionButton.disabled = true;
    openDebriefModal();
    if (debriefModalBody) {
        debriefModalBody.innerHTML = '<p class="debrief-loading">Reviewing the tape...</p>';
    }

    try {
        const response = await apiFetch(BASE_URL + "/api/debrief", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(conversationHistory),
        });

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload?.detail || "Debrief generation failed.");
        }

        const payload = await response.json();
        renderDebriefModal(payload);
    } catch (error) {
        renderDebriefError(error && error.message ? error.message : "Debrief generation failed.");
    } finally {
        debriefSessionButton.disabled = false;
    }
}

function toggleZenMode(forceState) {
    const nextState = typeof forceState === "boolean"
        ? forceState
        : !document.body.classList.contains("zen-mode");

    document.body.classList.toggle("zen-mode", nextState);
    if (focusModeButton) {
        focusModeButton.classList.toggle("is-active", nextState);
        focusModeButton.setAttribute("aria-pressed", String(nextState));
    }
}

function bindFocusMode() {
    if (focusModeButton) {
        focusModeButton.addEventListener("click", () => {
            toggleZenMode();
        });
        focusModeButton.setAttribute("aria-pressed", "false");
    }

    document.addEventListener("keydown", (event) => {
        const isSlash = event.code === "Slash" || event.key === "/";
        const hasModifier = event.ctrlKey || event.metaKey;
        if (!isSlash || !hasModifier || event.altKey) {
            return;
        }
        event.preventDefault();
        toggleZenMode();
    });
}

async function loadVaultEntries() {
    const response = await apiFetch(BASE_URL + "/api/vault", { method: "GET" });
    if (!response.ok) {
        throw new Error("vault-fetch-failed");
    }
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    return items
        .map((item) => normalizeVaultItem(item))
        .filter((item) => item.id && item.question);
}

function normalizeVaultItem(item) {
    return {
        id: String(item?.id || ""),
        question: String(item?.question_text || item?.question || "").trim(),
        tags: Array.isArray(item?.concept_tags)
            ? item.concept_tags.map((tag) => String(tag || "").trim()).filter(Boolean).slice(0, 8)
            : [],
        saved_at: String(item?.date_added || item?.saved_at || ""),
    };
}

async function hydrateVaultEntries() {
    try {
        vaultEntriesCache = await loadVaultEntries();
        vaultEntriesLoaded = true;
    } catch (error) {
        vaultEntriesCache = [];
        vaultEntriesLoaded = true;
    }
}

function buildVaultSaveButtonMarkup(sourceQuery) {
    const safeSourceQuery = escapeHtml(String(sourceQuery || "").trim());
    return '<button class="vault-save-button" type="button" data-vault-query="' + safeSourceQuery + '">💾 Save to Vault</button>';
}

function extractVaultTagsFromMessage(messageElement) {
    if (!messageElement) {
        return [];
    }
    const tags = Array.from(messageElement.querySelectorAll(".topic-tag"))
        .map((tagNode) => String(tagNode.textContent || "").trim())
        .filter(Boolean);
    return tags.filter((tag, index) => tags.findIndex((item) => item.toLowerCase() === tag.toLowerCase()) === index).slice(0, 8);
}

function setVaultButtonSavedState(button) {
    if (!button) {
        return;
    }
    button.classList.add("is-saved");
    button.textContent = "✔ Saved";
    button.disabled = true;
}

async function saveMessageToVault(button) {
    if (!button) {
        return;
    }

    try {
        const messageElement = button.closest(".message");
        const question = String(button.dataset.vaultQuery || lastUserPromptForVault || "").trim();
        if (!question) {
            appendErrorStep("Vault Save Failed: user prompt not found.");
            return;
        }

        const tags = extractVaultTagsFromMessage(messageElement);
        const entries = vaultEntriesLoaded ? vaultEntriesCache : await loadVaultEntries();
        const duplicate = entries.find((item) => item.question.toLowerCase() === question.toLowerCase());
        if (duplicate) {
            setVaultButtonSavedState(button);
            return;
        }

        const createResponse = await apiFetch(BASE_URL + "/api/vault", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question_text: question,
                concept_tags: tags,
            }),
        });
        if (!createResponse.ok) {
            appendErrorStep("Vault Save Failed: backend persistence unavailable.");
            return;
        }

        const savedItem = normalizeVaultItem(await createResponse.json());
        if (savedItem.id && savedItem.question) {
            vaultEntriesCache = [savedItem, ...entries.filter((item) => item.id !== savedItem.id && item.question.toLowerCase() !== savedItem.question.toLowerCase())];
        }

        setVaultButtonSavedState(button);

        if (blackBoxModal && blackBoxModal.classList.contains("is-open")) {
            await renderBlackBoxModal();
        }
    } catch (error) {
        appendErrorStep("Vault Save Failed: backend persistence unavailable.");
    }
}

async function renderBlackBoxModal() {
    if (!blackBoxList) {
        return;
    }

    let entries = [];
    try {
        if (!vaultEntriesLoaded) {
            await hydrateVaultEntries();
        }
        entries = vaultEntriesCache;
    } catch (error) {
        blackBoxList.innerHTML = '<p class="black-box-empty">Vault unavailable. Please retry in a moment.</p>';
        return;
    }
    if (!entries.length) {
        blackBoxList.innerHTML = '<p class="black-box-empty">No mistakes captured yet. Save hard problems from AI responses to build your vault.</p>';
        return;
    }

    const markup = entries.map((entry) => {
        const tagMarkup = Array.isArray(entry.tags) && entry.tags.length
            ? '<div class="black-box-tags">' + entry.tags.map((tag) => '<span class="black-box-tag">' + escapeHtml(tag) + '</span>').join("") + '</div>'
            : '<div class="black-box-tags"><span class="black-box-tag">UNLABELED</span></div>';

        return (
            '<article class="black-box-item">' +
                '<p class="black-box-question">' + escapeHtml(entry.question) + '</p>' +
                tagMarkup +
                '<button class="black-box-delete" type="button" data-vault-id="' + escapeHtml(entry.id) + '">Delete/Resolve</button>' +
            '</article>'
        );
    }).join("");

    blackBoxList.innerHTML = markup;
}

function openBlackBoxModal() {
    if (!blackBoxModal) {
        return;
    }
    void renderBlackBoxModal();
    blackBoxModal.classList.add("is-open");
    blackBoxModal.setAttribute("aria-hidden", "false");
}

function closeBlackBoxModalPanel() {
    if (!blackBoxModal) {
        return;
    }
    blackBoxModal.classList.remove("is-open");
    blackBoxModal.setAttribute("aria-hidden", "true");
}

async function deleteVaultEntry(entryId) {
    const id = String(entryId || "").trim();
    if (!id) {
        return;
    }
    const response = await apiFetch(BASE_URL + "/api/vault/" + encodeURIComponent(id), {
        method: "DELETE",
    });
    if (!response.ok) {
        appendErrorStep("Vault delete failed.");
        return;
    }
    vaultEntriesCache = vaultEntriesCache.filter((item) => item.id !== id);
    await renderBlackBoxModal();
}

function bindBlackBoxVault() {
    if (openBlackBoxButton) {
        openBlackBoxButton.addEventListener("click", () => {
            openBlackBoxModal();
        });
    }

    if (closeBlackBoxButton) {
        closeBlackBoxButton.addEventListener("click", () => {
            closeBlackBoxModalPanel();
        });
    }

    if (blackBoxModal) {
        blackBoxModal.addEventListener("click", (event) => {
            if (event.target === blackBoxModal) {
                closeBlackBoxModalPanel();
            }
        });
    }

    if (blackBoxList) {
        blackBoxList.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const deleteButton = event.target.closest(".black-box-delete");
            if (!deleteButton) {
                return;
            }
            void deleteVaultEntry(deleteButton.dataset.vaultId || "");
        });
    }
}

function compileSession() {
    const compiledBlocks = [];

    conversationHistory.forEach((entry) => {
        const payload = entry && typeof entry === "object" ? entry.data : null;
        const explanations = Array.isArray(payload?.explanation) ? payload.explanation : [];

        explanations.forEach((line) => {
            const text = String(line || "").trim();
            if (!text) {
                return;
            }
            const isVerification = text.includes("[VERIFICATION]");
            const hasMath = text.includes("$$");
            if (isVerification || hasMath) {
                compiledBlocks.push(text);
            }
        });
    });

    const compiledHtml = buildSessionExportHtml(compiledBlocks);
    const printWindow = window.open("", "_blank", "noopener,noreferrer,width=980,height=1100");
    if (!printWindow) {
        appendErrorStep("Export unavailable: popup blocked by the browser.");
        return "";
    }

    printWindow.document.open();
    printWindow.document.write(compiledHtml);
    printWindow.document.close();
    printWindow.focus();

    const triggerPrint = () => {
        try {
            printWindow.print();
        } catch (error) {
            // Ignore print failures from blocked dialogs.
        }
    };

    if (printWindow.document.readyState === "complete") {
        window.setTimeout(triggerPrint, 250);
    } else {
        printWindow.addEventListener("load", () => {
            window.setTimeout(triggerPrint, 250);
        }, { once: true });
    }

    return compiledHtml;
}

function buildSessionExportHtml(blocks) {
    const safeBlocks = Array.isArray(blocks) ? blocks : [];
    const renderedBlocks = safeBlocks.length
        ? safeBlocks.map((block) => {
            const normalized = escapeHtml(block).replace(/\$\$(.*?)\$\$/g, "<span class=\"export-math\">$$$1$$</span>");
            return '<section class="export-block">' + normalized + '</section>';
        }).join("")
        : '<p class="export-empty">No verification steps or math snippets were found in this session.</p>';

    return (
        '<!doctype html>' +
        '<html lang="en"><head><meta charset="utf-8">' +
        '<meta name="viewport" content="width=device-width, initial-scale=1">' +
        '<title>ADDIX Scholars Cheat Sheet</title>' +
        '<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.js"></script>' +
        '<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/contrib/auto-render.min.js"></script>' +
        '<style>' +
        'body{margin:0;font-family:Inter,Arial,sans-serif;background:#f5f7fb;color:#111827;}' +
        '.page{max-width:900px;margin:0 auto;padding:40px 28px 56px;}' +
        '.header{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:28px;border-bottom:1px solid #d8dee9;padding-bottom:14px;}' +
        '.kicker{text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:#6b7280;margin:0 0 6px;}' +
        'h1{margin:0;font-size:28px;line-height:1.1;}' +
        '.meta{margin:0;color:#6b7280;font-size:13px;}' +
        '.export-block{margin:0 0 16px;padding:16px 18px;border:1px solid #dbe2ec;border-radius:14px;background:#fff;box-shadow:0 6px 24px rgba(15,23,42,.04);white-space:pre-wrap;line-height:1.6;}' +
        '.export-math{font-family:"JetBrains Mono",Consolas,monospace;color:#0f766e;font-weight:600;}' +
        '.export-empty{padding:16px 18px;border:1px dashed #cbd5e1;border-radius:14px;color:#475569;background:#fff;}' +
        '@media print{body{background:#fff;}.page{padding:0;max-width:none;}.header{margin-bottom:20px;}.export-block{break-inside:avoid;box-shadow:none;}}' +
        '</style></head><body>' +
        '<main class="page">' +
        '<header class="header"><div><p class="kicker">Cheat Sheet</p><h1>ADDIX Scholars Session Export</h1></div><p class="meta">Verification and math excerpts compiled from the current session.</p></header>' +
        renderedBlocks +
        '</main>' +
        '<script>' +
        'window.addEventListener("load", function(){' +
        'if (typeof window.renderMathInElement === "function") {' +
        'window.renderMathInElement(document.body,{delimiters:[{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false},{left:"\\(",right:"\\)",display:false},{left:"\\[",right:"\\]",display:true}],throwOnError:false,errorCallback:function(message,error){console.warn("KaTeX render fallback:",message,error);}});' +
        '}' +
        '});' +
        '</script>' +
        '</body></html>'
    );
}

function bindEngineModeToggle() {
    if (!engineModeToggle) {
        updateEngineModeUiState();
        return;
    }

    isTesterMode = Boolean(engineModeToggle.checked);
    updateEngineModeUiState();
    engineModeToggle.addEventListener("change", () => {
        isTesterMode = Boolean(engineModeToggle.checked);
        updateEngineModeUiState();
    });
}

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

        const daysRemaining = typeof config.fixedDays === "number"
            ? config.fixedDays
            : calculateDaysRemaining(config.date);
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

            if (examContextSelector) {
                const selectedKey = normalizeExamForMastery(activeExam);
                const matchedOption = Array.from(examContextSelector.options).find(
                    (option) => normalizeExamForMastery(option.value || "") === selectedKey
                );
                if (matchedOption) {
                    examContextSelector.value = String(matchedOption.value || "NSEJS");
                }
            }
            updatePreparationGradeRings(activeExam);
            if (!isCustomExamSelection(examContextSelector)) {
                showSyllabusExplorer();
                void loadSyllabusForExam(activeExam);
            }
        });
    });
}

function bindChatInteractions() {
    queryForm.addEventListener("submit", (event) => {
        event.preventDefault();
        void sendMessage();
    });

    if (sendButton) {
        sendButton.addEventListener("click", (event) => {
            event.preventDefault();
            void sendMessage();
        });
    }

    chatFeed.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const saveButton = event.target.closest(".vault-save-button");
        if (!saveButton) {
            return;
        }
        void saveMessageToVault(saveButton);
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

        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void sendMessage();
        }
    });
}

function bindRapidMathKeyboard() {
    if (!queryInput || !mathKeyButtons.length) {
        return;
    }

    mathKeyButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const symbol = String(button.dataset.symbol || "");
            if (!symbol) {
                queryInput.focus();
                return;
            }

            const start = queryInput.selectionStart ?? queryInput.value.length;
            const end = queryInput.selectionEnd ?? queryInput.value.length;
            const value = queryInput.value;
            queryInput.value = value.slice(0, start) + symbol + value.slice(end);

            const nextCaret = start + symbol.length;
            queryInput.focus();
            queryInput.setSelectionRange(nextCaret, nextCaret);
        });
    });
}

function bindVisionInteractions() {
    if (!imageUploadButton || !imageUploadInput) {
        return;
    }

    imageUploadButton.addEventListener("click", () => {
        imageUploadInput.click();
    });

    imageUploadInput.addEventListener("change", async () => {
        const hasFile = imageUploadInput.files && imageUploadInput.files.length > 0;
        if (!hasFile) {
            clearSelectedImage();
            return;
        }
        try {
            const selectedFile = imageUploadInput.files[0];
            setImageUploadLoading(true);
            appendVisionStep(VISION_INIT_MESSAGE);
            const imagePayload = await readImagePayload(selectedFile);
            selectedImageBase64 = imagePayload.dataUrl;
            selectedImagePreviewDataUrl = imagePayload.dataUrl;
            renderImagePreview(selectedFile.name, selectedImagePreviewDataUrl);
            if (queryInput) {
                queryInput.focus();
            }

            appendVisionStep("[Vision Agent]: Image attached. Send the prompt with the thumbnail or continue typing.");
        } catch (error) {
            const message = error && error.message ? String(error.message) : "Vision Agent failed to process image.";
            appendErrorStep(message);
            clearSelectedImage();
        } finally {
            setImageUploadLoading(false);
        }
    });

    if (imagePreviewRemoveButton) {
        imagePreviewRemoveButton.addEventListener("click", () => {
            clearSelectedImage();
            if (queryInput) {
                queryInput.focus();
            }
        });
    }
}

function setImageUploadLoading(isLoading) {
    if (!imageUploadButton) {
        return;
    }

    imageUploadButton.classList.toggle("is-uploading", Boolean(isLoading));
    imageUploadButton.classList.toggle("scanning-pulse", Boolean(isLoading));
    imageUploadButton.disabled = Boolean(isLoading);
    imageUploadButton.setAttribute("aria-busy", isLoading ? "true" : "false");
}

function wireMultimodalUiHandlers() {
    const pdfUploadButton = document.getElementById("btn-upload-pdf");
    const pdfUploadInput = document.getElementById("pdf-upload");
    const generateCheatSheetButton = document.getElementById("generateCheatSheetButton");

    if (pdfUploadButton && pdfUploadInput) {
        pdfUploadButton.addEventListener("click", () => {
            pdfUploadInput.click();
        });

        pdfUploadInput.addEventListener("change", async () => {
            const hasFile = pdfUploadInput.files && pdfUploadInput.files.length > 0;
            if (!hasFile) {
                return;
            }
            try {
                const selectedFile = pdfUploadInput.files[0];
                setPdfUploadLoading(true);
                appendSystemStep("[PDF Agent]: Processing document...");
                
                const formData = new FormData();
                formData.append("file", selectedFile);
                
                const response = await safeFetch(BASE_URL + "/api/document/ingest", {
                    method: "POST",
                    headers: buildApiHeaders(),
                    body: formData
                });

                if (!response || !response.ok) {
                    throw new Error("PDF ingestion failed");
                }
                
                const result = await response.json();
                appendSystemStep("[PDF Agent]: Document loaded. " + (result.message || "Ready for analysis."));
            } catch (error) {
                const message = error && error.message ? String(error.message) : "PDF Agent failed to ingest document.";
                appendErrorStep(message);
            } finally {
                setPdfUploadLoading(false);
                pdfUploadInput.value = "";
            }
        });
    }

    if (generateCheatSheetButton) {
        generateCheatSheetButton.addEventListener("click", async () => {
            if (!activeSyllabusTopic || !activeExam) {
                appendErrorStep("Please select a topic from the syllabus first.");
                return;
            }
            try {
                appendSystemStep("[Cheat Sheet Agent]: Generating for " + escapeHtml(activeSyllabusTopic) + "...");
                const response = await safeFetch(BASE_URL + "/api/generate/cheatsheet", {
                    method: "POST",
                    headers: buildApiHeaders(),
                    body: JSON.stringify({
                        exam: activeExam,
                        topic: activeSyllabusTopic
                    })
                });
                
                if (!response || !response.ok) {
                    throw new Error("Cheat sheet generation failed");
                }
                
                const result = await response.json();
                const cheatSheetMarkdown = result.cheatsheet || "";
                appendAgentStep("final-step", "[Cheat Sheet]", cheatSheetMarkdown);
            } catch (error) {
                const message = error && error.message ? String(error.message) : "Failed to generate cheat sheet.";
                appendErrorStep(message);
            }
        });
    }
}

function setPdfUploadLoading(isLoading) {
    const pdfUploadButton = document.getElementById("btn-upload-pdf");
    if (!pdfUploadButton) {
        return;
    }
    pdfUploadButton.classList.toggle("is-uploading", Boolean(isLoading));
    pdfUploadButton.disabled = Boolean(isLoading);
    pdfUploadButton.setAttribute("aria-busy", isLoading ? "true" : "false");
}

async function sendQuery() {
    return sendMessage();
}

async function sendMessage(userText) {
    if (sending) {
        return;
    }

    const rawQuery = typeof userText === "string" ? userText.trim() : queryInput.value.trim();
    const doneTopicFromUserText = detectCompletedTopicFromUserText(rawQuery);
    if (doneTopicFromUserText) {
        markTopicComplete(doneTopicFromUserText);
    }
    if (!rawQuery && !selectedImageBase64) {
        return;
    }

    rememberCommand(rawQuery);
    queryInput.value = "";

    if (rawQuery.toLowerCase() === "clear") {
        clearTerminalFeed();
        conversationHistory = [];
        clearSelectedImage();
        return;
    }

    if (rawQuery.toLowerCase() === "status") {
        await showSystemStatus();
        return;
    }

    const isSimulationCommand = rawQuery.startsWith(SIMULATION_COMMAND_PREFIX);
    const simulationQuery = isSimulationCommand
        ? rawQuery.slice(SIMULATION_COMMAND_PREFIX.length).trim()
        : "";
    if (isSimulationCommand && !simulationQuery) {
        appendErrorStep("Simulation command requires a prompt. Example: /simulate optimal trajectory of a 5kg mass");
        return;
    }

    sending = true;
    setButtonThinking(true);
    setComposerBusy(true);

    const visibleUserQuery = rawQuery || (selectedImageBase64 ? "Please analyze the attached image and solve the problem." : "");
    if (visibleUserQuery) {
        appendUserStep(visibleUserQuery);
        pushConversationMessage("user", visibleUserQuery);
        lastUserPromptForVault = visibleUserQuery;
        scrollChatToBottom();
    }
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
            activeSolveStep = solvingStep;
            activeTraceStatusStep = appendTraceStatusStep(TRACE_PHASES[0].engine, TRACE_PHASES[0].label);
            activeTraceTicker = startTraceStatusTicker(activeTraceStatusStep);
            await sendQueryToBackend(visibleUserQuery);
        }
    } catch (error) {
        console.error(error);
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
                replaceSolvingWithFinal(solvingStep, SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE, formatWolframAsLatex(SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE), "Failsafe Triggered", [], { enableVaultSave: false });
        } else if (isSecurityErrorMessage(errorText)) {
            emitError(SECURITY_PROTOCOL_MESSAGE);
        } else {
            emitError("System Error: " + (errorText || "Scholar Engine: Reconnecting to Tri-Core..."));
        }
    } finally {
        if (activeTraceTicker) {
            stopTraceStatusTicker(activeTraceTicker, null, "Scholar", "Trace stopped.");
            activeTraceTicker = null;
        }
        activeTraceStatusStep = null;
        activeSolveStep = null;
        removeComputingState();
        sending = false;
        setComposerBusy(false);
        clearSelectedImage();
        queryInput.focus();
    }
}

async function sendQueryToBackend(userText) {
    if (typeof userText !== "string") {
        await sendMessage();
        return;
    }

    // 1. Gather UI States
    const examContextNode = document.getElementById("exam-context-selector");
    const examContext = examContextNode && typeof examContextNode.value === "string" && examContextNode.value.trim()
        ? examContextNode.value
        : activeExam;
    const testerModeEnabled = Boolean(engineModeToggle ? engineModeToggle.checked : isTesterMode);
    const currentImageBase64 = selectedImageBase64 || null;
    const BACKEND_URL = BASE_URL + "/api/solve";

    // 2. Build payload with frontend state.
    const payload = {
        prompt: userText || (selectedImageBase64 ? "Please analyze the attached image and solve the problem." : ""),
        messages: buildBackendConversationHistory(),
        socratic_mode: false,
        is_tester_mode: testerModeEnabled,
        exam_context: examContext,
        image_base64: currentImageBase64,
    };

    let response;

    try {
        // 3. Fire the request with a plain JSON payload.
        response = await safeFetch(BACKEND_URL, {
            method: "POST",
            headers: new Headers({ "Content-Type": "application/json" }),
            body: JSON.stringify(payload),
        });
    } catch (error) {
        console.log("API Bridge Failed:", error);
        return;
    }

    if (response && response.error) {
        const payload = await response.json().catch(() => ({
            error: true,
            message:
                "Reconnecting to Engine… The cloud backend may be waking up (Render free tier can take ~60s). Please try again in a moment.",
        }));
        renderEngineReconnectNotice(
            String(
                payload.message ||
                    "Reconnecting to Engine… The cloud backend may be waking up. Please try again in a moment.",
            ),
        );
        return;
    }

    try {
    if (!response.ok) {
        const rawText = await response.text();
        let parsedError = null;
        try {
            parsedError = JSON.parse(rawText);
        } catch (error) {
            parsedError = null;
        }
        if (String(parsedError?.error || "") === "rate_limit") {
            renderRateLimitCountdown(RATE_LIMIT_COOLDOWN_SECONDS);
            return;
        }
        renderSystemAlertBubble(buildSystemAlertMessage(response.status, rawText));
        return;
    }

        if (!response.body || typeof response.body.getReader !== "function") {
            throw new Error("Streaming not supported by this browser.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let streamBuffer = "";
        let finalPayload = null;

        const processSseEvent = (rawEvent) => {
            const lines = String(rawEvent || "").split("\n");
            let eventName = "message";
            const dataLines = [];

            lines.forEach((line) => {
                if (line.startsWith("event:")) {
                    eventName = line.slice(6).trim();
                } else if (line.startsWith("data:")) {
                    dataLines.push(line.slice(5).trim());
                }
            });

            const dataText = dataLines.join("\n").trim();
            if (!dataText) {
                return;
            }

            let parsed = null;
            try {
                parsed = JSON.parse(dataText);
            } catch (error) {
                return;
            }

            if (eventName === "thought") {
                appendThoughtDelta(activeSolveStep, String(parsed.text || ""));
                return;
            }
            if (eventName === "result") {
                finalPayload = parsed;
            }
        };

        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                break;
            }

            streamBuffer += decoder.decode(value, { stream: true });
            const events = streamBuffer.split("\n\n");
            streamBuffer = events.pop() || "";
            events.forEach(processSseEvent);
        }

        if (streamBuffer.trim()) {
            processSseEvent(streamBuffer);
        }

        if (!finalPayload || typeof finalPayload !== "object") {
            throw new Error("No final streamed result received from backend.");
        }
        if (String(finalPayload.error || "") === "rate_limit") {
            renderRateLimitCountdown(RATE_LIMIT_COOLDOWN_SECONDS);
            return;
        }

        // Push the AI response to memory.
        conversationHistory.push({
            role: "assistant",
            content: String(finalPayload.result || ""),
            data: finalPayload,
        });

        // 4. Render primary guidance, logic cards, and topic badges.
        renderAIResponse(finalPayload, userText);

    } catch (error) {
        console.error("API Bridge Failed:", error);
        const fallbackMessage = error && error.message ? String(error.message) : "Unexpected bridge failure.";
        const lower = fallbackMessage.toLowerCase();
        if (lower.includes("failed to fetch") || lower.includes("networkerror") || lower.includes("load failed")) {
            renderEngineReconnectNotice(
                "Reconnecting to Engine… Network request did not complete. If the backend was asleep, wait a minute and send again.",
            );
        } else {
            renderSystemAlertBubble("System Alert: " + fallbackMessage);
        }
    } finally {
        // Clean up visual activity state.
        removeComputingAnimation();
        clearImageUploadState();
    }
}

async function sendMessageToEngine(userText) {
    return sendQueryToBackend(userText);
}

function appendThoughtDelta(stepElement, deltaText) {
    if (!stepElement) {
        return;
    }

    const thoughtShell = stepElement.querySelector("[data-thought-box]");
    const thoughtCopy = stepElement.querySelector("[data-thought-copy]");
    if (!thoughtShell || !thoughtCopy) {
        return;
    }

    const chunk = String(deltaText || "");
    if (!chunk.trim()) {
        return;
    }

    thoughtShell.hidden = false;
    thoughtCopy.textContent = thoughtCopy.textContent + chunk;
    scrollChatToBottom();
}

function renderAIResponse(data, userText) {
    const topics = normalizeTopicTags(data?.topics);
    const logicSteps = Array.isArray(data?.explanation)
        ? data.explanation
            .filter((step) => typeof step === "string" && step.trim())
            .map((step) => sanitizeMathEscapesOutsideCodeBlocks(String(step || "")))
        : [];
    const rawResult = typeof data?.result === "string"
        ? data.result
        : "";
    const finalAnswer = typeof rawResult === "string" && rawResult.trim()
        ? rawResult.trim()
        : "No deterministic answer was returned by the backend.";
    const safeFinalAnswer = normalizeTerminalSecurityMessage(finalAnswer);
    const doneTopicFromAi = detectCompletedTopicFromAiText(safeFinalAnswer);
    if (doneTopicFromAi) {
        markTopicComplete(doneTopicFromAi);
    }
    const baseEngineTrace = typeof data?.engine_trace === "string" && data.engine_trace.trim()
        ? data.engine_trace.trim()
        : "Llama 3.3 70B + SymPy";
    const symbolicVerificationLabel = data?.symbolic_verification_active
        ? " | Symbolic Verification: Active (SymPy)"
        : "";
    const engineTrace = /Symbolic Verification: Active \(SymPy\)/.test(baseEngineTrace)
        ? baseEngineTrace
        : baseEngineTrace + symbolicVerificationLabel;

    if (activeTraceTicker) {
        stopTraceStatusTicker(activeTraceTicker, activeTraceStatusStep, engineTrace, "Response finalized.");
        activeTraceTicker = null;
    }

    replaceSolvingWithFinal(activeSolveStep, safeFinalAnswer, "", engineTrace, topics, {
        sourceQuery: userText,
        logicSteps: logicSteps,
    });
    if (!isTesterMode) {
        trackSuccessfulSolve();
        incrementProgressForToday(topics);
    }

    rememberTurnContext(userText, safeFinalAnswer);
    activeSolveStep = null;
    activeTraceStatusStep = null;
}

function renderErrorInChat(message) {
    const text = String(message || "System Error: Unknown bridge failure.");
    if (activeTraceTicker) {
        stopTraceStatusTicker(activeTraceTicker, activeTraceStatusStep, "Bridge", "Failed.");
        activeTraceTicker = null;
    }
    if (activeSolveStep) {
        replaceSolvingWithError(activeSolveStep, text);
    } else {
        appendErrorStep(text);
    }
    activeSolveStep = null;
    activeTraceStatusStep = null;
}

function buildSystemAlertMessage(statusCode, rawBody) {
    const status = Number(statusCode) || 500;
    const text = String(rawBody || "").trim();
    if (status === 402) {
        return "System Alert: Billing balance exhausted (402). Recharge compute credits and retry.";
    }
    if (status >= 500) {
        return "System Alert: Backend failsafe triggered (" + String(status) + "). " + (text || "Please retry.");
    }
    return "System Alert: Backend request failed (" + String(status) + "). " + (text || "Please retry.");
}

function renderEngineReconnectNotice(message) {
    const text = String(
        message ||
            "Reconnecting to Engine… The cloud backend may be waking up. Please try again in a moment.",
    );
    if (activeTraceTicker) {
        stopTraceStatusTicker(activeTraceTicker, activeTraceStatusStep, "Engine", "Reconnecting…");
        activeTraceTicker = null;
    }

    if (activeSolveStep) {
        activeSolveStep.classList.remove("loading-step", "error-step");
        activeSolveStep.classList.add("engine-reconnect-notice", "system-alert-step");
        activeSolveStep.innerHTML =
            '<p class="message-line"><span class="agent-label">[Engine]:</span> ' + escapeHtml(text) + "</p>";
        if (chatFeed) {
            chatFeed.scrollTop = chatFeed.scrollHeight;
        }
        return;
    }

    const html =
        '<article class="message engine-reconnect-notice system-alert-step">' +
            '<p class="message-line"><span class="agent-label">[Engine]:</span> ' +
            escapeHtml(text) +
            "</p>" +
        "</article>";
    appendMessage(html);
}

function renderSystemAlertBubble(message) {
    const text = String(message || "System Alert: Unknown bridge failure.");
    const inGraceWindow = Date.now() - frontendBootTimeMs < CONNECTION_ALERT_GRACE_PERIOD_MS;
    const looksLikeConnectionFailure = /connection failed|failed to fetch|networkerror|load failed/i.test(text);
    if (inGraceWindow && looksLikeConnectionFailure) {
        renderEngineReconnectNotice(
            "ADDIX Engine is waking up from hibernation... (30-60s remaining)",
        );
        return;
    }
    if (activeTraceTicker) {
        stopTraceStatusTicker(activeTraceTicker, activeTraceStatusStep, "System Alert", "Intervention required.");
        activeTraceTicker = null;
    }

    if (activeSolveStep) {
        activeSolveStep.classList.remove("loading-step");
        activeSolveStep.classList.add("error-step", "system-alert-step");
        activeSolveStep.innerHTML =
            '<p class="message-line"><span class="agent-label">[System Alert]:</span> ' + escapeHtml(text) + '</p>';
        chatFeed.scrollTop = chatFeed.scrollHeight;
        return;
    }

    const html =
        '<article class="message error-step system-alert-step">' +
            '<p class="message-line"><span class="agent-label">[System Alert]:</span> ' + escapeHtml(text) + '</p>' +
        '</article>';
    appendMessage(html);
}

function renderRateLimitCountdown(seconds = RATE_LIMIT_COOLDOWN_SECONDS) {
    let remainingSeconds = Math.max(0, Number(seconds) || RATE_LIMIT_COOLDOWN_SECONDS);
    const updateMessage = () =>
        "Engine is cooling down. Please try in " + String(remainingSeconds) + " seconds.";

    if (activeSolveStep) {
        activeSolveStep.classList.remove("loading-step", "error-step");
        activeSolveStep.classList.add("engine-reconnect-notice", "system-alert-step");
        activeSolveStep.innerHTML =
            '<p class="message-line"><span class="agent-label">[Rate Limit]:</span> ' + escapeHtml(updateMessage()) + "</p>";
        scrollChatToBottom();
    } else {
        appendMessage(
            '<article class="message engine-reconnect-notice system-alert-step">' +
                '<p class="message-line"><span class="agent-label">[Rate Limit]:</span> ' +
                escapeHtml(updateMessage()) +
                "</p>" +
            "</article>",
        );
    }

    const countdownId = window.setInterval(() => {
        remainingSeconds -= 1;
        if (remainingSeconds <= 0) {
            window.clearInterval(countdownId);
            return;
        }
        if (activeSolveStep) {
            activeSolveStep.innerHTML =
                '<p class="message-line"><span class="agent-label">[Rate Limit]:</span> ' +
                escapeHtml(updateMessage()) +
                "</p>";
        }
    }, 1000);
}

function removeComputingAnimation() {
    removeComputingState();
}

function clearImageUploadState() {
    clearSelectedImage();
}

function pushConversationMessage(role, content) {
    const safeRole = role === "assistant" ? "assistant" : "user";
    const safeContent = typeof content === "string" ? content.trim() : "";
    if (!safeContent) {
        return;
    }

    conversationHistory.push({ role: safeRole, content: safeContent });
    if (conversationHistory.length > 14) {
        conversationHistory = conversationHistory.slice(-14);
    }
}

function buildBackendConversationHistory() {
    return conversationHistory.map((entry) => ({
        role: String(entry?.role || "user"),
        content: String(entry?.content || ""),
    }));
}

function clearSelectedImage() {
    selectedImageBase64 = "";
    selectedImagePreviewDataUrl = "";
    if (imageUploadInput) {
        imageUploadInput.value = "";
    }
    if (imagePreviewThumb) {
        imagePreviewThumb.removeAttribute("src");
    }
    if (imagePreviewShell) {
        imagePreviewShell.classList.remove("active");
        imagePreviewShell.hidden = true;
    }
}

function renderImagePreview(fileName, dataUrl) {
    if (!imagePreviewShell || !imagePreviewThumb) {
        return;
    }

    imagePreviewThumb.src = dataUrl;
    imagePreviewThumb.alt = fileName ? "Preview of " + fileName : "Uploaded problem preview";
    imagePreviewShell.classList.add("active");
    imagePreviewShell.hidden = false;
}

async function fetchSimulation(studentQuery) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 15000);

    try {
        const response = await apiFetch(BASE_URL + "/api/simulate", {
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
        const response = await apiFetch(BASE_URL + "/api/status/" + encodeURIComponent(taskId), {
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
            formatWolframAsLatex(safeFinal),
            { sourceQuery: lastUserPromptForVault }
        );
        return;
    }

    if (status === "Failed") {
        stopSimulationPolling();
        appendErrorStep("Simulation task #" + taskId + " failed.");
    }
}

async function fetchUploadedImageText(file) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
        controller.abort();
    }, 40000);

    try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await apiFetch(BASE_URL + "/api/upload-image", {
            method: "POST",
            body: formData,
            signal: controller.signal,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.detail || "upload-image-failed");
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
        const response = await apiFetch(BASE_URL + "/api/system-status", {
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
        "\\text{Checking Wolfram and database health}",
        { enableVaultSave: false }
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
                '<p class="message-line"><span class="agent-label">[System]:</span> Deconstructing logic...</p>' +
            '</div>' +
            '<div class="thought-stream-box" data-thought-box hidden>' +
                '<p class="thought-stream-label">Working Notes</p>' +
                '<pre class="thought-stream-copy" data-thought-copy></pre>' +
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

function stripStepPrefix(text) {
    return String(text || "")
        .replace(/^STEP\s*\d+\s*\[[^\]]+\]\s*:\s*/i, "")
        .trim();
}

function formatExplanationAsLatex(stepText) {
    const stripped = stripStepPrefix(stepText);
    const extracted = extractFirstLatex(stripped);
    if (extracted) {
        return extracted;
    }

    if (isLikelyFormula(stripped)) {
        return stripped
            .replace(/×/g, "\\cdot ")
            .replace(/\*/g, " \\cdot ");
    }

    return formatWolframAsLatex(stripped);
}

function buildLogicCardsMarkup(explanation) {
    const steps = Array.isArray(explanation)
        ? explanation.filter((step) => typeof step === "string" && step.trim())
        : [];

    if (!steps.length) {
        return "";
    }

    const cards = steps.map((step, index) => {
        const original = String(step || "").trim();
        const stripped = stripStepPrefix(original) || original;
        const looksMathy = Boolean(extractFirstLatex(stripped)) || isLikelyFormula(stripped);
        const mathMarkup = looksMathy
            ? '<div class="math-block logic-card-math">$$' + escapeHtml(formatExplanationAsLatex(stripped)) + '$$</div>'
            : "";

        return (
            '<article class="logic-card">' +
                '<span class="logic-card-number">' + String(index + 1) + '</span>' +
                '<div class="logic-card-body">' +
                    '<p class="logic-card-text">' + escapeHtml(stripped) + '</p>' +
                    mathMarkup +
                '</div>' +
            '</article>'
        );
    }).join("");

    return '<section class="logic-card-stack">' + cards + '</section>';
}

function renderMarkdownContent(text) {
    const rawText = String(text || "");
    if (typeof window.marked !== "undefined" && window.marked && typeof window.marked.parse === "function") {
        return window.marked.parse(rawText);
    }

    return escapeHtml(rawText).replace(/\n/g, "<br>");
}

async function renderDiagrams(element) {
    if (typeof mermaid === "undefined" || !mermaid) {
        return;
    }
    
    const mermaidBlocks = element.querySelectorAll("pre code.language-mermaid");
    for (const block of mermaidBlocks) {
        const mermaidCode = block.textContent || "";
        const container = document.createElement("div");
        container.className = "mermaid-diagram-container";
        
        try {
            const svg = await mermaid.render("mermaid-" + Math.random().toString(36).substr(2, 9), mermaidCode);
            container.innerHTML = svg.svg;
            block.parentElement.parentElement.replaceWith(container);
        } catch (error) {
            console.warn("Mermaid diagram render failed:", error);
        }
    }
}

function replaceSolvingWithFinal(stepElement, finalAnswer, equationOverride, engineTrace, topics = [], options = {}) {
    const safeEngineTrace = escapeHtml(engineTrace || "Llama 3.3 70B + SymPy");
    const topicMarkup = renderTopicTags(topics);
    const logicMarkup = buildLogicCardsMarkup(options.logicSteps);
    const sourceQuery = String(options.sourceQuery || lastUserPromptForVault || "").trim();
    const saveButtonMarkup = options.enableVaultSave === false ? "" : buildVaultSaveButtonMarkup(sourceQuery);
    const aiResponseText = String(finalAnswer || "");

    if (!stepElement) {
        appendAgentStep(
            "final-step",
            "[Final Answer]",
            finalAnswer,
            formatWolframAsLatex(finalAnswer),
            { engineTrace: engineTrace, topics: topics, sourceQuery: sourceQuery, enableVaultSave: options.enableVaultSave }
        );
        return;
    }

    stepElement.classList.remove("loading-step");
    stepElement.classList.add("final-step", "mentor-structured");
    stepElement.dataset.vaultQuery = sourceQuery;
    stepElement.innerHTML =
        '<div class="message-engine-trace">' + safeEngineTrace + '</div>' +
        '<div class="agent-row">' +
            '<span class="agent-pulse"></span>' +
            '<span class="agent-label">[ADDIX Mentor]:</span>' +
            '<div class="message-line mentor-guidance-line" data-ai-response></div>' +
        '</div>' +
        logicMarkup +
        topicMarkup;

    stepElement.innerHTML +=
        saveButtonMarkup;

    const messageDiv = stepElement.querySelector("[data-ai-response]");
    if (messageDiv) {
        const htmlContent = renderMarkdownContent(aiResponseText);
        messageDiv.innerHTML = htmlContent;
        if (typeof renderMathInElement === "function") {
            renderMathInElement(messageDiv, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false }
                ],
                throwOnError: false,
                errorCallback: function katexRenderFallback(message, error) {
                    console.warn("KaTeX render fallback:", message, error);
                }
            });
        }
        void renderDiagrams(messageDiv);
    }
    scrollChatToBottom();
    window.requestAnimationFrame(() => {
        scrollChatToBottom();
    });
}

function appendTraceStatusStep(engine, label) {
    const html =
        '<article class="message trace-status-step">' +
            '<p class="message-line"><span class="agent-label">Trace Status:</span> ' +
            '<span class="trace-engine" data-trace-engine>' + escapeHtml(engine) + '</span> · ' +
            '<span data-trace-label>' + escapeHtml(label) + '</span></p>' +
        '</article>';
    return appendMessage(html);
}

function updateTraceStatusStep(stepElement, engine, label) {
    if (!stepElement) {
        return;
    }
    const engineNode = stepElement.querySelector("[data-trace-engine]");
    const labelNode = stepElement.querySelector("[data-trace-label]");
    if (engineNode) {
        engineNode.textContent = engine;
    }
    if (labelNode) {
        labelNode.textContent = label;
    }
}

function startTraceStatusTicker(stepElement) {
    let index = 0;
    const timerId = window.setInterval(() => {
        index = (index + 1) % TRACE_PHASES.length;
        const phase = TRACE_PHASES[index];
        updateTraceStatusStep(stepElement, phase.engine, phase.label);
    }, 850);
    return { id: timerId, stepElement };
}

function stopTraceStatusTicker(ticker, fallbackStepElement, engine, label) {
    if (!ticker) {
        if (fallbackStepElement) {
            updateTraceStatusStep(fallbackStepElement, engine, label);
        }
        return;
    }
    window.clearInterval(ticker.id);
    updateTraceStatusStep(ticker.stepElement || fallbackStepElement, engine, label);
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
    scrollChatToBottom();
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

function appendAgentStep(stepClass, label, copy, equation, options = {}) {
    const mentorLabel = "[ADDIX Mentor]";
    const safeEngineTrace = typeof options.engineTrace === "string" && options.engineTrace.trim()
        ? escapeHtml(options.engineTrace.trim())
        : "";
    const sourceQuery = String(options.sourceQuery || lastUserPromptForVault || "").trim();
    const topicMarkup = renderTopicTags(options.topics);
    const saveButtonMarkup = options.enableVaultSave === false ? "" : buildVaultSaveButtonMarkup(sourceQuery);

    const html =
        '<article class="message agent-step ' + stepClass + '" data-vault-query="' + escapeHtml(sourceQuery) + '">' +
            '<div class="agent-row">' +
                '<span class="agent-pulse"></span>' +
                '<span class="agent-label">' + mentorLabel + ':</span>' +
                '<span class="message-line" data-agent-copy></span>' +
            '</div>' +
            topicMarkup +
            (safeEngineTrace ? '<div class="engine-badge">' + safeEngineTrace + '</div>' : '') +
            saveButtonMarkup +
        '</article>';

    const element = appendMessage(html, { shouldRenderMath: false });
    updateAgentStep(element, copy, equation);
    return element;
}

function updateAgentStep(stepElement, copy, equation) {
    if (!stepElement) {
        return;
    }

    const copyNode = stepElement.querySelector("[data-agent-copy]");
    if (copyNode) {
        copyNode.innerHTML = renderMarkdownContent(copy);
    }

    renderMath(stepElement);
}

function appendErrorStep(copy) {
    const html =
        '<article class="message error-step">' +
            '<p class="message-line"><span class="agent-label">[ADDIX Mentor]:</span> ' +
            escapeHtml(copy) + '</p>' +
        '</article>';

    appendMessage(html);
}

function appendMessage(html, options = {}) {
    const shouldRenderMath = Boolean(options.shouldRenderMath);
    chatFeed.insertAdjacentHTML("beforeend", html);
    const newChatBubbleElement = chatFeed.lastElementChild;
    if (shouldRenderMath) {
        renderMath(newChatBubbleElement);
    }
    scrollChatToBottom();
    window.requestAnimationFrame(() => {
        scrollChatToBottom();
    });
    return newChatBubbleElement;
}

function scrollChatToBottom() {
    if (!chatFeed) {
        return;
    }
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function setButtonThinking(isThinking) {
    sendButton.disabled = isThinking;
    sendButton.classList.toggle("is-thinking", isThinking);
    if (sidebarPanel) {
        sidebarPanel.classList.toggle("is-solving", isThinking);
    }

    if (!buttonText) {
        return;
    }

    if (isThinking) {
        let frameIndex = 0;
        buttonText.classList.add("equation-thinking");
        buttonText.textContent = THINKING_STATUS_FRAMES[frameIndex];
        if (thinkingTickerId) {
            window.clearInterval(thinkingTickerId);
        }
        thinkingTickerId = window.setInterval(() => {
            frameIndex = (frameIndex + 1) % THINKING_STATUS_FRAMES.length;
            buttonText.textContent = THINKING_STATUS_FRAMES[frameIndex];
        }, 640);
        return;
    }

    if (thinkingTickerId) {
        window.clearInterval(thinkingTickerId);
        thinkingTickerId = null;
    }
    buttonText.classList.remove("equation-thinking");
    buttonText.textContent = "Send Query";
}

function removeComputingState() {
    setButtonThinking(false);
}

function loadTurnContext() {
    return sessionTurnHistory.filter((item) => item && typeof item.q === "string" && typeof item.a === "string").slice(-MAX_TURN_CONTEXT);
}

function rememberTurnContext(query, answer) {
    const q = String(query || "").trim();
    const a = String(answer || "").trim();
    if (!q || !a) {
        return;
    }
    sessionTurnHistory.push({ q, a, ts: Date.now() });
    sessionTurnHistory = sessionTurnHistory.slice(-MAX_TURN_CONTEXT);
}

function buildContextualQuery(currentQuery) {
    const query = String(currentQuery || "").trim();
    if (!query) {
        return "";
    }
    const turns = loadTurnContext();
    if (!turns.length) {
        return query;
    }
    const contextLines = turns
        .slice(-MAX_TURN_CONTEXT)
        .map((turn, index) => "Turn " + String(index + 1) + " Q: " + turn.q + " | A: " + turn.a);
    return query + "\n\nRecent context (last 3 turns): " + contextLines.join(" || ");
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
    const explanation = Array.isArray(payload?.explanation) ? payload.explanation : [];
    const setupStep = explanation.find((step) => typeof step === "string" && step.toLowerCase().includes("step 2 [concept]"));

    if (setupStep && isLikelyFormula(setupStep)) {
        return setupStep.trim();
    }

    const fromAnswer = extractFirstLatex(finalAnswer);
    if (fromAnswer) {
        return fromAnswer;
    }

    return inferSymbolicEquation(rawQuery);
}

function extractDeterministicComputation(payload, rawQuery, finalAnswer) {
    const explanation = Array.isArray(payload?.explanation) ? payload.explanation : [];
    const executionStep = explanation.find((step) => typeof step === "string" && step.toLowerCase().includes("step 3 [execution]"));
    const setupStep = explanation.find((step) => typeof step === "string" && step.toLowerCase().includes("step 1 [setup]"));

    const sequence = [];
    sequence.push("Input: " + rawQuery);
    if (setupStep) {
        sequence.push(setupStep.replace(/\n+/g, " -> "));
    }
    if (executionStep) {
        sequence.push(executionStep.replace(/\n+/g, " -> "));
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

function sanitizeMathEscapesOutsideCodeBlocks(text) {
    const source = String(text || "");
    if (!source.includes("\\\\")) {
        return source;
    }

    return source
        .split(/(```[\s\S]*?```)/g)
        .map((segment) => {
            if (segment.startsWith("```") && segment.endsWith("```")) {
                return segment;
            }
            return segment.replace(/\\\\/g, "\\");
        })
        .join("");
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
            {left: "$$", right: "$$", display: true},
            {left: "$", right: "$", display: false},
            {left: "\\(", right: "\\)", display: false},
            {left: "\\[", right: "\\]", display: true}
        ],
        throwOnError: false,
        errorCallback: function katexRenderFallback(message, error) {
            console.warn("KaTeX render fallback:", message, error);
        }
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
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return "session-" + crypto.randomUUID();
    }
    return "session-" + Math.random().toString(36).slice(2, 10);
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

function readImagePayload(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = typeof reader.result === "string" ? reader.result : "";
            if (!result) {
                reject(new Error("Image conversion failed."));
                return;
            }
            const base64 = result.includes(",") ? result.split(",", 2)[1] : result;
            if (!base64) {
                reject(new Error("Image conversion failed."));
                return;
            }
            resolve({ dataUrl: result, base64: base64 });
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

document.addEventListener("DOMContentLoaded", () => {
    const mathDiv = document.getElementById("initial-system-math") || document.querySelector(".system-message");

    const katexInterval = setInterval(() => {
        if (typeof window.katex !== 'undefined' || typeof window.renderMathInElement !== 'undefined') {
            clearInterval(katexInterval);

            if (typeof renderMathInElement === 'function') {
                renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '\\[', right: '\\]', display: true}
                    ],
                    throwOnError: false,
                    errorCallback: function katexRenderFallback(message, error) {
                        console.warn("KaTeX render fallback:", message, error);
                    }
                });
            } else if (mathDiv) {
                window.katex.render("E = mc^2", mathDiv, { displayMode: true });
            }
        }
    }, 100);
});

window.sendQuery = sendQuery;
window.updateExamCountdowns = updateExamCountdowns;
window.updateCountdowns = updateCountdowns;
