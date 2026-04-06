const isDev = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
const API_BASE = isDev ? "http://127.0.0.1:8000/api" : "/api"; // Auto-route to Vercel Serverless Functions in production

// Firebase Init
const firebaseConfig = {
  apiKey: "AIzaSyBXRvc7RgTLNVwz0_0tvpS98j3bE1PZJTc",
  projectId: "vitalmind-ad326",
};

let auth, db;
try {
  // Use Firebase from the global window object (loaded via CDN)
  if (window.firebase) {
    firebase.initializeApp(firebaseConfig);
    auth = firebase.auth();
    db = firebase.firestore();
  }
} catch (e) {
  console.warn("Firebase init failed", e);
}

let currentUid = "vitalmind_test_uid";

const THEME_KEY = "vitalmind-theme";

const output = document.getElementById("response-output");
const statusPill = document.getElementById("status-pill");
const themeToggle = document.getElementById("theme-toggle");
const themeLabel = document.getElementById("theme-label");
const macroSummary = document.getElementById("macro-summary");

const chatbotOutput = document.getElementById("chatbot-output");
const floatChatbot = document.getElementById("floating-chatbot");
const navChatBtn = document.getElementById("nav-chat-btn");
const chatCloseBtn = document.getElementById("chatbot-close-btn");
const chatPreviewContainer = document.getElementById("chat-preview-container");
const chatPreviewImg = document.getElementById("chat-preview-img");
const chatRemoveImgBtn = document.getElementById("chat-remove-image-btn");
const chatImageFile = document.getElementById("chat-image-file");

const authOverlay = document.getElementById("auth-overlay");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const navLogoutBtn = document.getElementById("nav-logout-btn");

const mealHistory = [];
let macroChart = null;
let trendChart = null;

if (navChatBtn) {
  navChatBtn.addEventListener("click", () => {
    floatChatbot.classList.add("maximized");
    document.body.style.overflow = "hidden";
  });
}

if (chatCloseBtn) {
  chatCloseBtn.addEventListener("click", () => {
    floatChatbot.classList.remove("maximized");
    document.body.style.overflow = "";
  });
}

if (chatImageFile) {
  chatImageFile.addEventListener("change", () => {
    const file = chatImageFile.files?.[0];
    if (file) {
      chatPreviewImg.src = URL.createObjectURL(file);
      chatPreviewContainer.style.display = "block";
    } else {
      chatPreviewContainer.style.display = "none";
      chatPreviewImg.src = "";
    }
  });
}

if (chatRemoveImgBtn) {
  chatRemoveImgBtn.addEventListener("click", () => {
    chatImageFile.value = "";
    chatPreviewContainer.style.display = "none";
    chatPreviewImg.src = "";
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const pass = document.getElementById("login-pass").value;
    setStatus("Authenticating", "loading");
    
    // Custom logic for test credentials requested
    if (email === "vitalmind@gmail.com" && pass === "1234") {
      try {
        if (auth) {
           const cred = await auth.signInAnonymously();
           currentUid = cred.user.uid;
        }
      } catch (err) {
         console.warn("Anon sign in failed, falling back to local UID", err);
      }
      completeLogin();
    } else {
      if (auth) {
        try {
          const cred = await auth.signInWithEmailAndPassword(email, pass);
          currentUid = cred.user.uid;
          completeLogin();
        } catch (err) {
          loginError.innerText = err.message;
          loginError.style.display = "block";
          setStatus("Idle", "ok");
        }
      } else {
        loginError.innerText = "Firebase not initialized.";
        loginError.style.display = "block";
        setStatus("Idle", "ok");
      }
    }
  });
}

function completeLogin() {
  if (loginError) loginError.style.display = "none";
  setStatus("System Online", "ok");
  if (authOverlay) {
    authOverlay.style.opacity = "0";
    setTimeout(() => authOverlay.style.display = "none", 600);
  }
  if (navLogoutBtn) navLogoutBtn.style.display = "block";
  loadFirebaseMemory();
}

if (navLogoutBtn) {
  navLogoutBtn.addEventListener("click", async () => {
    if (auth) await auth.signOut();
    if (authOverlay) {
      authOverlay.style.display = "flex";
      // Force repaint
      void authOverlay.offsetWidth;
      authOverlay.style.opacity = "1";
    }
    navLogoutBtn.style.display = "none";
    mealHistory.length = 0; // clear local history
    updateCharts();
    const chatbotOutputEl = document.getElementById("chatbot-output");
    if (chatbotOutputEl) chatbotOutputEl.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding: 20px;">Ready to chat</p>`;
    setStatus("Idle", "ok");
  });
}

async function loadFirebaseMemory() {
  if (!db) return;
  try {
    const docRef = db.collection('users').doc(currentUid);
    const docSnap = await docRef.get();
    if (docSnap.exists) {
      const data = docSnap.data();
      if (data.meals && Array.isArray(data.meals)) {
        mealHistory.length = 0;
        data.meals.forEach(m => mealHistory.push(m));
        updateCharts();
      }
      if (data.chats && Array.isArray(data.chats)) {
         const chatbotOutputEl = document.getElementById("chatbot-output");
         if (chatbotOutputEl && data.chats.length > 0) {
             chatbotOutputEl.innerHTML = "";
             data.chats.forEach(chatHtml => {
                 chatbotOutputEl.innerHTML += chatHtml;
             });
             chatbotOutputEl.scrollTop = chatbotOutputEl.scrollHeight;
         }
      }
    }
  } catch(e) {
    console.error("Firestore error loading memory", e);
  }
}

async function saveFirebaseMemory() {
   if (!db || !currentUid) return;
   
   const chatbotOutputEl = document.getElementById("chatbot-output");
   const chatList = [];
   if (chatbotOutputEl && chatbotOutputEl.children) {
      // Save last 15 messages so it doesn't overflow firestore limits quickly over time
      Array.from(chatbotOutputEl.children).slice(-15).forEach(child => {
          if (child.id !== "chat-loading" && !child.innerHTML.includes("Ready to chat")) {
              chatList.push(child.outerHTML);
          }
      });
   }
   
   try {
     await db.collection('users').doc(currentUid).set({
        meals: mealHistory,
        chats: chatList
     }, {merge: true});
   } catch(e) {
     console.error("Firestore error saving memory", e);
   }
}

function applyTheme(theme) {
  const isLight = theme === "light";
  document.body.classList.toggle("theme-light", isLight);
  themeLabel.textContent = isLight ? "Light Luxe" : "Dark Luxe";

  if (macroChart && trendChart) {
    updateCharts();
  }
}

function getThemeTokens() {
  return {
    text: "#ffffff",
    grid: "rgba(255, 255, 255, 0.08)",
    calories: "#f59e0b",
    protein: "#10b981",
    carbs: "#a855f7",
    fat: "#ef4444"
  };
}

function initializeTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored === "light" ? "light" : "dark");

  themeToggle.addEventListener("click", () => {
    const next = document.body.classList.contains("theme-light") ? "dark" : "light";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  });
}

function registerMeal(meal) {
  if (!meal || typeof meal !== "object") {
    return;
  }

  mealHistory.push({
    name: meal.name || `Meal ${mealHistory.length + 1}`,
    calories: Number(meal.calories || 0),
    protein: Number(meal.protein || 0),
    carbs: Number(meal.carbs || 0),
    fat: Number(meal.fat || 0)
  });

  updateCharts();
  saveFirebaseMemory();
}

function buildChartData() {
  const totals = mealHistory.reduce(
    (acc, meal) => {
      acc.calories += meal.calories;
      acc.protein += meal.protein;
      acc.carbs += meal.carbs;
      acc.fat += meal.fat;
      return acc;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 }
  );

  return {
    totals,
    labels: mealHistory.map((_, index) => `M${index + 1}`),
    caloriesSeries: mealHistory.map((meal) => meal.calories),
    proteinSeries: mealHistory.map((meal) => meal.protein)
  };
}

function updateCharts() {
  const tokens = getThemeTokens();
  const { totals, labels, caloriesSeries, proteinSeries } = buildChartData();

  macroChart.data.datasets[0].data = [totals.protein, totals.carbs, totals.fat];
  macroChart.data.datasets[0].backgroundColor = [tokens.protein, tokens.carbs, tokens.fat];

  trendChart.data.labels = labels;
  trendChart.data.datasets[0].data = caloriesSeries;
  trendChart.data.datasets[1].data = proteinSeries;

  trendChart.data.datasets[0].borderColor = tokens.calories;
  trendChart.data.datasets[0].backgroundColor = `${tokens.calories}33`;
  trendChart.data.datasets[1].borderColor = tokens.protein;
  trendChart.data.datasets[1].backgroundColor = `${tokens.protein}33`;

  macroChart.options.plugins.legend.labels.color = tokens.text;
  macroChart.options.plugins.tooltip.titleColor = tokens.text;
  trendChart.options.plugins.legend.labels.color = tokens.text;
  trendChart.options.scales.x.grid.color = tokens.grid;
  trendChart.options.scales.y.grid.color = tokens.grid;
  trendChart.options.scales.x.ticks.color = tokens.text;
  trendChart.options.scales.y.ticks.color = tokens.text;

  const calories = Math.round(totals.calories);
  const protein = Math.round(totals.protein);
  macroSummary.textContent = `${mealHistory.length} meals | ${calories} kcal | ${protein}g protein`;

  macroChart.update();
  trendChart.update();
}

function initializeCharts() {
  const tokens = getThemeTokens();
  const macroCtx = document.getElementById("macro-chart");
  const trendCtx = document.getElementById("trend-chart");

  macroChart = new Chart(macroCtx, {
    type: "doughnut",
    data: {
      labels: ["Protein", "Carbs", "Fat"],
      datasets: [
        {
          data: [0, 0, 0],
          borderWidth: 0,
          backgroundColor: [tokens.protein, tokens.carbs, tokens.fat]
        }
      ]
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: tokens.text,
            boxWidth: 10,
            padding: 18
          }
        }
      }
    }
  });

  trendChart = new Chart(trendCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Calories",
          data: [],
          borderColor: tokens.calories,
          backgroundColor: `${tokens.calories}33`,
          borderWidth: 2.3,
          tension: 0.32,
          fill: true,
          pointRadius: 3
        },
        {
          label: "Protein (g)",
          data: [],
          borderColor: tokens.protein,
          backgroundColor: `${tokens.protein}33`,
          borderWidth: 2.3,
          tension: 0.32,
          fill: true,
          pointRadius: 3
        }
      ]
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: tokens.text
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: tokens.grid
          },
          ticks: {
            color: tokens.text
          }
        },
        y: {
          grid: {
            color: tokens.grid
          },
          ticks: {
            color: tokens.text
          }
        }
      }
    }
  });
}

function setStatus(text, mode = "idle") {
  statusPill.textContent = text;

  if (mode === "loading") {
    statusPill.style.background = "rgba(209, 166, 95, 0.18)";
    statusPill.style.borderColor = "rgba(209, 166, 95, 0.45)";
    statusPill.style.color = "#fae4bb";
    return;
  }

  if (mode === "error") {
    statusPill.style.background = "rgba(220, 111, 111, 0.2)";
    statusPill.style.borderColor = "rgba(220, 111, 111, 0.45)";
    statusPill.style.color = "#ffdede";
    return;
  }

  statusPill.style.background = "rgba(135, 197, 154, 0.18)";
  statusPill.style.borderColor = "rgba(135, 197, 154, 0.45)";
  statusPill.style.color = "#d8f1df";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function metricItem(label, value) {
  return `
    <div class="metric">
      <span class="metric-label">${escapeHtml(label)}</span>
      <span class="metric-value">${escapeHtml(value)}</span>
    </div>
  `;
}

function renderMealCard(meal, title = "Meal Details") {
  const safeMeal = meal || {};
  const previewBlock = safeMeal.photo_preview
    ? `
      <div class="response-photo">
        <img src="${escapeHtml(safeMeal.photo_preview)}" alt="${escapeHtml(safeMeal.name || "Meal photo")}" />
      </div>
    `
    : "";

  return `
    <div class="response-title-row">
      <h3 class="response-title">${escapeHtml(title)}</h3>
      <span class="response-pill">Meal</span>
    </div>
    <p class="response-description">${escapeHtml(safeMeal.name || "Unnamed meal")}</p>
    <div class="metric-grid">
      ${metricItem("Calories", `${Number(safeMeal.calories || 0)} kcal`)}
      ${metricItem("Protein", `${Number(safeMeal.protein || 0)} g`)}
      ${metricItem("Carbs", `${Number(safeMeal.carbs || 0)} g`)}
      ${metricItem("Fat", `${Number(safeMeal.fat || 0)} g`)}
    </div>
    ${previewBlock}
  `;
}

function renderSuggestions(suggestions) {
  if (!Array.isArray(suggestions) || suggestions.length === 0) {
    return "<p class=\"response-description\">No suggestions available for this response.</p>";
  }

  return `
    <div class="suggestion-list">
      ${suggestions
        .map((item) => {
          const priority = String(item.priority || "low").toLowerCase();
          return `
            <article class="suggestion-card">
              <div class="suggestion-head">
                <h4>${escapeHtml(item.title || "Suggestion")}</h4>
                <span class="priority-pill ${escapeHtml(priority)}">${escapeHtml(priority)}</span>
              </div>
              <p><strong>Insight:</strong> ${escapeHtml(item.insight || "-")}</p>
              <p><strong>Action:</strong> ${escapeHtml(item.action || "-")}</p>
              <p><strong>Reason:</strong> ${escapeHtml(item.reason || "-")}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function tryParseAiSuggestions(rawResponse) {
  if (!rawResponse || typeof rawResponse !== "string") {
    return null;
  }

  const trimmed = rawResponse.trim();

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && Array.isArray(parsed.suggestions)) {
      return parsed.suggestions;
    }
  } catch (_error) {
    // Keep trying fallback parsers.
  }

  const jsonMatch = trimmed.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]);
      if (parsed && Array.isArray(parsed.suggestions)) {
        return parsed.suggestions;
      }
    } catch (_error) {
      // Ignore and continue to line parsing.
    }
  }

  return null;
}

function renderAiResponse(rawResponse) {
  const aiSuggestions = tryParseAiSuggestions(rawResponse);
  if (aiSuggestions) {
    const normalized = aiSuggestions.map((item) => ({
      title: item.title || "AI Suggestion",
      insight: item.insight || item.description || "-",
      action: item.action || "-",
      reason: item.reason || "-",
      priority: item.priority || "medium"
    }));
    return renderSuggestions(normalized);
  }

  const lines = String(rawResponse)
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*\d.\s]+/, "").trim())
    .filter(Boolean);

  if (lines.length > 1) {
    return `
      <ol class="simple-list">
        ${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
      </ol>
    `;
  }

  return `<p class="response-description">${escapeHtml(String(rawResponse))}</p>`;
}

function getProfilePayload() {
  const ageRaw = document.getElementById("user-age").value.trim();
  const bmiRaw = document.getElementById("user-bmi").value.trim();
  const goal = document.getElementById("user-goal").value;

  return {
    age: ageRaw ? Number(ageRaw) : null,
    bmi: bmiRaw ? Number(bmiRaw) : null,
    goal: goal || "stay_fit"
  };
}

function showOutput(data) {
  if (!data || typeof data !== "object") {
    output.innerHTML = `
      <div class="response-empty">
        <h3>No data</h3>
        <p>Response was empty.</p>
      </div>
    `;
    return;
  }

  if (data.error) {
    output.innerHTML = `
      <div class="response-title-row">
        <h3 class="response-title">Request Failed</h3>
        <span class="response-pill">Error</span>
      </div>
      <p class="response-description">${escapeHtml(data.error)}</p>
      ${data.details ? `<p class="response-description"><strong>Details:</strong> ${escapeHtml(data.details)}</p>` : ""}
      ${data.hint ? `<p class="response-description"><strong>Hint:</strong> ${escapeHtml(data.hint)}</p>` : ""}
    `;
    return;
  }

  if (data.meal) {
    let modeTag = "OCR";
    if (data.prediction_mode === "visual_estimation" || data.prediction_mode === "vision_local_fast") {
      modeTag = "AI Vision";
    } else if (data.prediction_mode === "vision_qwen_direct") {
      modeTag = "Qwen Vision";
    } else if (data.prediction_mode === "hybrid_ocr_vision") {
      modeTag = "Hybrid OCR + Vision";
    }
    output.innerHTML = `
      <div class="response-title-row">
        <h3 class="response-title">${escapeHtml(data.message || "Image Analysis Complete")}</h3>
        <span class="response-pill">${escapeHtml(modeTag)}</span>
      </div>
      ${data.note ? `<p class="response-description">${escapeHtml(data.note)}</p>` : ""}
      ${data.food_profile ? `<p class="response-description"><strong>Detected profile:</strong> ${escapeHtml(data.food_profile)}</p>` : ""}
      ${renderMealCard(data.meal, "Extracted Nutrition")}
    `;
    return;
  }

  const hasMacros =
    Object.prototype.hasOwnProperty.call(data, "calories") &&
    Object.prototype.hasOwnProperty.call(data, "protein") &&
    Object.prototype.hasOwnProperty.call(data, "carbs") &&
    Object.prototype.hasOwnProperty.call(data, "fat") &&
    Object.prototype.hasOwnProperty.call(data, "name");

  if (hasMacros) {
    output.innerHTML = renderMealCard(data, "Food Lookup Result");
    return;
  }

  if (Object.prototype.hasOwnProperty.call(data, "health_score")) {
    const profile = data.profile || {};
    const range = Array.isArray(profile.calorie_target_range)
      ? `${profile.calorie_target_range[0]}-${profile.calorie_target_range[1]} kcal`
      : "-";

    output.innerHTML = `
      <div class="response-title-row">
        <h3 class="response-title">Daily Insights</h3>
        <span class="response-pill">Score ${escapeHtml(data.health_score)}</span>
      </div>
      ${data.generated_by ? `<p class="response-description">Generated by ${escapeHtml(data.generated_by)}</p>` : ""}
      <div class="metric-grid">
        ${metricItem("Health Score", data.health_score)}
        ${metricItem("Total Calories", `${Number(data.total_calories || 0)} kcal`)}
        ${metricItem("Total Protein", `${Number(data.total_protein || 0)} g`)}
        ${metricItem("Meals", Number(data.meal_count || 0))}
      </div>
      <div class="metric-grid">
        ${metricItem("Goal", String(profile.goal || "stay_fit").replace("_", " "))}
        ${metricItem("Age", profile.age ?? "-")}
        ${metricItem("BMI", profile.bmi ?? "-")}
        ${metricItem("Calorie Target", range)}
      </div>
      ${
        data.ai && data.response
          ? renderAiResponse(data.response)
          : renderSuggestions(data.suggestions)
      }
    `;
    return;
  }

  if (data.message) {
    output.innerHTML = `
      <div class="response-title-row">
        <h3 class="response-title">Success</h3>
        <span class="response-pill">Info</span>
      </div>
      <p class="response-description">${escapeHtml(data.message)}</p>
    `;
    return;
  }

  output.innerHTML = `
    <div class="response-title-row">
      <h3 class="response-title">Response</h3>
      <span class="response-pill">Raw</span>
    </div>
    <pre class="raw-fallback">${escapeHtml(JSON.stringify(data, null, 2))}</pre>
  `;
}

function renderChatbotOutput(data) {
  if (!data || data.error) {
    showOutput(data || { error: "Chatbot failed" });
    return;
  }

  function toReadableAiText(rawValue) {
    const rawText = String(rawValue || "").trim();
    if (!rawText) {
      return "No AI response available.";
    }

    try {
      const parsed = JSON.parse(rawText);
      if (parsed && typeof parsed === "object") {
        const lines = [];
        Object.entries(parsed).forEach(([key, value]) => {
          const prettyKey = key.replace(/_/g, " ");
          if (value && typeof value === "object") {
            lines.push(`${prettyKey}: ${JSON.stringify(value)}`);
          } else {
            lines.push(`${prettyKey}: ${String(value)}`);
          }
        });
        return lines.join("\n");
      }
    } catch (_error) {
      // Keep plain text fallback.
    }

    return rawText
      .replace(/\s{2,}/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  const cleanedAssistantText = String(data.response || "No response")
    .replace(/free api was unavailable, so a local nutrition estimate was used\.?/gi, "")
    .replace(/qwen key is missing, so fallback image nutrition prediction was used\.?/gi, "")
    .replace(/qwen key is missing, so free openfoodfacts data was used\.?/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim() || "Here is your nutrition analysis.";

  const nutrition = data.nutrition_estimate;
  let originalReadable = toReadableAiText(data.response || "");
  if (String(data.model || "").startsWith("free-") || String(data.model || "").startsWith("local-")) {
    originalReadable = "";
  }
  const qualityTag = nutrition
    ? (Number(nutrition.protein || 0) >= 20 ? "high-protein option" : "moderate-protein option")
    : "no nutrition estimate available";

  const kcalHint = nutrition
    ? (Number(nutrition.calories || 0) <= 220 ? "light meal range" : Number(nutrition.calories || 0) <= 500 ? "balanced meal range" : "heavy meal range")
    : "";

  const nutritionSummary = nutrition
    ? `${nutrition.calories} kcal, ${nutrition.protein}g protein, ${nutrition.carbs}g carbs, ${nutrition.fat}g fat`
    : "";

  const readableResponse = [cleanedAssistantText, data.details ? data.details : "", data.model ? data.model : ""]
    .filter(Boolean)
    .join(" • ");

  const chatbotOutputEl = document.getElementById("chatbot-output");
  if (chatbotOutputEl) {
    chatbotOutputEl.innerHTML = `
      <div class="chatbot-result" style="margin-bottom: 12px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 12px;">
        <span class="text-xs" style="color: #a855f7; display:block; margin-bottom:4px; font-weight:600;">AI Assistant</span>
        <p>${escapeHtml(readableResponse)}</p>
        ${
          nutrition
            ? `
              <p style="margin-top:8px;">${escapeHtml(nutritionSummary)} • ${escapeHtml(`${qualityTag}${kcalHint ? ` • ${kcalHint}` : ""}`)}</p>
            `
            : ""
        }
        ${originalReadable ? `<pre class="raw-fallback" style="margin-top:8px;">${escapeHtml(originalReadable)}</pre>` : ""}
      </div>
    `;
    // Scroll to bottom
    chatbotOutputEl.scrollTop = chatbotOutputEl.scrollHeight;
    saveFirebaseMemory();
  }
}

async function request(path, options = {}) {
  setStatus("Processing", "loading");

  try {
    const response = await fetch(`${API_BASE}${path}`, options);
    const data = await response.json();

    if (!response.ok) {
      setStatus("Failed", "error");
      showOutput(data);
      return null;
    }

    setStatus("Success", "ok");
    showOutput(data);
    return data;
  } catch (error) {
    setStatus("Network Error", "error");
    showOutput({
      error: "Request failed",
      details: error.message,
      hint: "Make sure backend is running on http://127.0.0.1:8000"
    });
    return null;
  }
}

document.getElementById("manual-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    name: document.getElementById("meal-name").value.trim(),
    calories: Number(document.getElementById("calories").value || 0),
    protein: Number(document.getElementById("protein").value || 0),
    carbs: Number(document.getElementById("carbs").value || 0),
    fat: Number(document.getElementById("fat").value || 0)
  };

  const logged = await request("/food/log", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (logged) {
    registerMeal(payload);
  }
});

document.getElementById("image-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const fileInput = document.getElementById("food-image");
  const file = fileInput.files?.[0];

  if (!file) {
    setStatus("No File", "error");
    showOutput({ error: "Please select an image first" });
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  const scan = await request("/food/image", {
    method: "POST",
    body: formData
  });

  if (scan && scan.meal) {
    registerMeal(scan.meal);
  }
});

document.getElementById("food-photo-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const fileInput = document.getElementById("food-photo-file");
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("No File", "error");
    showOutput({ error: "Please select a food image first" });
    return;
  }

  const payload = {
    name: document.getElementById("food-photo-name").value.trim() || "Photo Logged Meal"
  };

  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", payload.name);

  const result = await request("/food/photo-log", {
    method: "POST",
    body: formData
  });

  if (result && result.meal) {
    const preview = URL.createObjectURL(file);
    result.meal.photo_preview = preview;
    showOutput(result);
    registerMeal(result.meal);
  }
});

document.getElementById("chatbot-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const text = document.getElementById("chat-message").value.trim();
  const fileInput = document.getElementById("chat-image-file");
  const uploadedFile = fileInput.files?.[0] || null;

  const formData = new FormData();
  formData.append("message", text || "Please analyze this image");

  // Show user message in chat
  const chatbotOutputEl = document.getElementById("chatbot-output");
  if (chatbotOutputEl) {
    if (chatbotOutputEl.innerHTML.includes("Ready to chat")) {
      chatbotOutputEl.innerHTML = "";
    }
    chatbotOutputEl.innerHTML += `
      <div style="margin-bottom: 12px; padding: 12px; background: rgba(43, 42, 46, 0.5); border-radius: 12px; align-self: flex-end;">
        <span class="text-xs" style="color: #9CA3AF; display:block; margin-bottom:4px; font-weight:600;">You</span>
        <p>${escapeHtml(text || "Uploaded an image for analysis")}</p>
        ${uploadedFile ? `<div class="chat-image-preview" style="display:block; margin-top:8px; opacity:0.8;"><img src="${chatPreviewImg.src}" /></div>` : ""}
      </div>
    `;
    chatbotOutputEl.innerHTML += `<div id="chat-loading" style="color: #a855f7; font-size:0.875rem; margin-bottom:12px;">AI is thinking...</div>`;
    chatbotOutputEl.scrollTop = chatbotOutputEl.scrollHeight;
    saveFirebaseMemory();
  }

  // Clear preview and input fields
  if (chatImageFile) chatImageFile.value = "";
  if (chatPreviewContainer) chatPreviewContainer.style.display = "none";
  if (chatPreviewImg) chatPreviewImg.src = "";
  document.getElementById("chat-message").value = "";

  if (uploadedFile) {
    formData.append("file", uploadedFile);
  }

  setStatus("Processing", "loading");
  try {
    const response = await fetch(`${API_BASE}/chatbot/message`, {
      method: "POST",
      body: formData
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus("Failed", "error");
      showOutput(data);
      return;
    }

    // Remove loading indicator
    const loadingEl = document.getElementById("chat-loading");
    if (loadingEl) loadingEl.remove();

    setStatus("Success", "ok");
    renderChatbotOutput(data);
  } catch (error) {
    const loadingEl = document.getElementById("chat-loading");
    if (loadingEl) loadingEl.remove();

    setStatus("Network Error", "error");
    showOutput({ error: "Chat request failed", details: error.message });
  }
});

document.getElementById("get-insights").addEventListener("click", async () => {
  const profilePayload = getProfilePayload();
  await request("/insights/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(profilePayload)
  });
});

document.getElementById("reset-meals").addEventListener("click", () => {
  if (confirm("Reset all meal data?")) {
    mealHistory.length = 0;
    updateCharts();
    saveFirebaseMemory();
  }
});

initializeTheme();
initializeCharts();
updateCharts();
