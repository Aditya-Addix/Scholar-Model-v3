const ADMIN_BACKEND_URL = "http://127.0.0.1:8000";
const AUTH_TOKEN_STORAGE_KEY = "addix-auth-token";
const AUTH_USER_EMAIL_STORAGE_KEY = "addix-user-email";
const SCHOLAR_FRONTEND_SECRET = typeof window.SCHOLAR_FRONTEND_SECRET === "string" && window.SCHOLAR_FRONTEND_SECRET.trim()
    ? window.SCHOLAR_FRONTEND_SECRET.trim()
    : "CHANGE_ME_BEFORE_PROD";

const kpiTotalUsers = document.getElementById("kpiTotalUsers");
const kpiPremiumUsers = document.getElementById("kpiPremiumUsers");
const kpiQuestionsSolved = document.getElementById("kpiQuestionsSolved");
const kpiBlackBoxToday = document.getElementById("kpiBlackBoxToday");
const adminStatus = document.getElementById("adminStatus");
const volumeChart = document.getElementById("volumeChart");

function buildAuthHeaders() {
    const headers = new Headers();
    headers.set("X-Scholar-Auth", SCHOLAR_FRONTEND_SECRET);

    const token = String(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "").trim();
    if (token) {
        headers.set("Authorization", "Bearer " + token);
    }

    const userEmail = String(window.localStorage.getItem(AUTH_USER_EMAIL_STORAGE_KEY) || "").trim().toLowerCase();
    if (userEmail) {
        headers.set("X-User-Email", userEmail);
    }

    return headers;
}

function setStatus(message) {
    if (adminStatus) {
        adminStatus.textContent = String(message || "").trim();
    }
}

function formatCount(value) {
    return Number(value || 0).toLocaleString("en-IN");
}

async function fetchTelemetry() {
    const response = await fetch(ADMIN_BACKEND_URL + "/api/admin/telemetry", {
        method: "GET",
        headers: buildAuthHeaders(),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload?.detail || "Telemetry request failed.");
    }

    return payload;
}

function renderKpis(payload) {
    if (kpiTotalUsers) {
        kpiTotalUsers.textContent = formatCount(payload?.total_registered_users);
    }
    if (kpiPremiumUsers) {
        kpiPremiumUsers.textContent = formatCount(payload?.total_premium_subscribers);
    }
    if (kpiQuestionsSolved) {
        kpiQuestionsSolved.textContent = formatCount(payload?.total_questions_solved);
    }
    if (kpiBlackBoxToday) {
        kpiBlackBoxToday.textContent = formatCount(payload?.total_black_box_entries_today);
    }
}

function initializeVolumeChart() {
    if (!volumeChart) {
        return [];
    }

    const bars = [];
    volumeChart.innerHTML = "";

    for (let i = 0; i < 20; i += 1) {
        const bar = document.createElement("span");
        bar.className = "volume-bar";
        bar.style.height = String(18 + Math.floor(Math.random() * 75)) + "%";
        volumeChart.appendChild(bar);
        bars.push(bar);
    }

    return bars;
}

function tickVolumeChart(bars) {
    if (!Array.isArray(bars) || !bars.length) {
        return;
    }

    bars.forEach((bar) => {
        const nextHeight = 14 + Math.floor(Math.random() * 82);
        bar.style.height = String(nextHeight) + "%";
    });
}

async function bootAdminDashboard() {
    const bars = initializeVolumeChart();

    try {
        setStatus("Collecting live founder telemetry...");
        const telemetry = await fetchTelemetry();
        renderKpis(telemetry);
        setStatus("Telemetry live. Last refresh: " + new Date().toLocaleTimeString());
    } catch (error) {
        const message = error && error.message ? String(error.message) : "Telemetry unavailable.";
        setStatus("Access denied or backend unavailable: " + message);
    }

    window.setInterval(() => {
        tickVolumeChart(bars);
    }, 1300);

    window.setInterval(async () => {
        try {
            const telemetry = await fetchTelemetry();
            renderKpis(telemetry);
            setStatus("Telemetry live. Last refresh: " + new Date().toLocaleTimeString());
        } catch (error) {
            const message = error && error.message ? String(error.message) : "Telemetry refresh failed.";
            setStatus("Telemetry refresh issue: " + message);
        }
    }, 15000);
}

window.addEventListener("DOMContentLoaded", () => {
    void bootAdminDashboard();
});
