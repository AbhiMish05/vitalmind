const API_BASE = "http://127.0.0.1:8000";
const THEME_KEY = "vitalmind-theme";

const output = document.getElementById("response-output");
const statusPill = document.getElementById("status-pill");
const themeToggle = document.getElementById("theme-toggle");
const themeLabel = document.getElementById("theme-label");
const macroSummary = document.getElementById("macro-summary");

const mealHistory = [];
let macroChart = null;
let trendChart = null;

function applyTheme(theme) {
  const isLight = theme === "light";
  document.body.classList.toggle("theme-light", isLight);
  themeLabel.textContent = isLight ? "Light Luxe" : "Dark Luxe";

  if (macroChart && trendChart) {
    updateCharts();
  }
}

function getThemeTokens() {
  const light = document.body.classList.contains("theme-light");

  if (light) {
    return {
      text: "#2b2a2e",
      grid: "rgba(43, 42, 46, 0.18)",
      calories: "#b06a2f",
      protein: "#2f7c5d",
      carbs: "#8b5db9",
      fat: "#b74d62"
    };
  }

  return {
    text: "#e9edf2",
    grid: "rgba(233, 237, 242, 0.15)",
    calories: "#d39f53",
    protein: "#6fc88f",
    carbs: "#8e6bd1",
    fat: "#d36b78"
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
    } else if (data.prediction_mode === "vision_ollama_direct") {
      modeTag = "Ollama Vision";
    } else if (data.prediction_mode === "vision_plus_ollama") {
      modeTag = "AI Vision + Ollama";
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
    name: document.getElementById("food-photo-name").value.trim() || "Photo Logged Meal",
    calories: Number(document.getElementById("food-photo-calories").value || 0),
    protein: Number(document.getElementById("food-photo-protein").value || 0),
    carbs: Number(document.getElementById("food-photo-carbs").value || 0),
    fat: Number(document.getElementById("food-photo-fat").value || 0)
  };

  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", payload.name);
  formData.append("calories", String(payload.calories));
  formData.append("protein", String(payload.protein));
  formData.append("carbs", String(payload.carbs));
  formData.append("fat", String(payload.fat));

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

document.getElementById("reset-meals").addEventListener("click", async () => {
  const reset = await request("/food/reset", {
    method: "POST"
  });

  if (reset) {
    mealHistory.length = 0;
    updateCharts();
  }
});

initializeTheme();
initializeCharts();
updateCharts();
