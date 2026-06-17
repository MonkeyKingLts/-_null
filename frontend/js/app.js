const API_BASE = "";

const SENTIMENT_LABELS = {
  positive: "正面",
  neutral: "中性",
  negative: "负面",
};

let sentimentChart;
let productChart;
let trendChart;

function $(selector) {
  return document.querySelector(selector);
}

function formatScore(score) {
  return Number(score).toFixed(4);
}

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, options);
  if (!response.ok) {
    let detail = "请求失败";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

function switchSection(sectionId) {
  document.querySelectorAll(".section").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  document.getElementById(sectionId).classList.add("active");
  document.querySelector(`[data-section="${sectionId}"]`).classList.add("active");

  const titles = {
    dashboard: "数据概览",
    analyze: "单条分析",
    batch: "批量导入",
    reviews: "评论管理",
    keywords: "关键词洞察",
  };
  $("#page-title").textContent = titles[sectionId] || "电商评论情感分析平台";

  if (sectionId === "dashboard") loadDashboard();
  if (sectionId === "reviews") loadReviews();
  if (sectionId === "keywords") loadKeywords();
}

function renderStatCards(stats) {
  $("#stat-cards").innerHTML = `
    <div class="card"><h3>评论总数</h3><div class="value">${stats.total}</div></div>
    <div class="card positive"><h3>正面评论</h3><div class="value">${stats.positive}</div></div>
    <div class="card neutral"><h3>中性评论</h3><div class="value">${stats.neutral}</div></div>
    <div class="card negative"><h3>负面评论</h3><div class="value">${stats.negative}</div></div>
  `;
}

function destroyChart(chart) {
  if (chart) chart.destroy();
}

async function loadDashboard() {
  const stats = await request("/api/stats");
  renderStatCards(stats);

  destroyChart(sentimentChart);
  sentimentChart = new Chart($("#sentiment-chart"), {
    type: "doughnut",
    data: {
      labels: ["正面", "中性", "负面"],
      datasets: [{
        data: [stats.positive, stats.neutral, stats.negative],
        backgroundColor: ["#16a34a", "#d97706", "#dc2626"],
      }],
    },
    options: { maintainAspectRatio: false },
  });

  const products = stats.product_stats.slice(0, 8);
  destroyChart(productChart);
  productChart = new Chart($("#product-chart"), {
    type: "bar",
    data: {
      labels: products.map((item) => item.product_name),
      datasets: [{
        label: "平均情感得分",
        data: products.map((item) => item.average_score),
        backgroundColor: "#2563eb",
      }],
    },
    options: {
      maintainAspectRatio: false,
      scales: { y: { min: 0, max: 1 } },
    },
  });

  const trend = stats.recent_trend;
  destroyChart(trendChart);
  trendChart = new Chart($("#trend-chart"), {
    type: "line",
    data: {
      labels: trend.map((item) => item.date),
      datasets: [
        {
          label: "正面",
          data: trend.map((item) => item.positive),
          borderColor: "#16a34a",
          tension: 0.3,
        },
        {
          label: "中性",
          data: trend.map((item) => item.neutral),
          borderColor: "#d97706",
          tension: 0.3,
        },
        {
          label: "负面",
          data: trend.map((item) => item.negative),
          borderColor: "#dc2626",
          tension: 0.3,
        },
      ],
    },
    options: { maintainAspectRatio: false },
  });
}

function renderAnalyzeResult(result) {
  const keywords = (result.keywords || [])
    .map((word) => `<span class="keyword">${word}</span>`)
    .join("");

  $("#analyze-result").innerHTML = `
    <div>情感倾向：<span class="badge ${result.sentiment}">${SENTIMENT_LABELS[result.sentiment]}</span></div>
    <div style="margin-top:8px;">情感得分：<strong>${formatScore(result.score)}</strong></div>
    <div class="keywords">${keywords || "<span class='tip'>暂无关键词</span>"}</div>
  `;
}

async function analyzeSingle() {
  const content = $("#single-content").value.trim();
  if (!content) {
    alert("请输入评论内容");
    return;
  }
  const result = await request("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  renderAnalyzeResult(result);
}

async function saveSingleReview() {
  const content = $("#single-content").value.trim();
  const product_name = $("#single-product").value.trim() || "未分类商品";
  if (!content) {
    alert("请输入评论内容");
    return;
  }
  await request("/api/reviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, product_name }),
  });
  alert("评论已保存");
  await analyzeSingle();
}

function parseBatchLines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      if (line.includes("|")) {
        const [product_name, content] = line.split("|", 2);
        return { product_name: product_name.trim() || "未分类商品", content: content.trim() };
      }
      return { product_name: "未分类商品", content: line };
    });
}

async function submitBatch() {
  const reviews = parseBatchLines($("#batch-text").value);
  if (!reviews.length) {
    alert("请至少输入一条评论");
    return;
  }
  const result = await request("/api/reviews/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviews }),
  });
  alert(`${result.message}，共 ${result.count} 条`);
  $("#batch-text").value = "";
}

async function uploadCsv() {
  const fileInput = $("#csv-file");
  if (!fileInput.files.length) {
    alert("请选择 CSV 文件");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const result = await request("/api/reviews/upload", {
    method: "POST",
    body: formData,
  });
  alert(`${result.message}，共 ${result.count} 条`);
  fileInput.value = "";
}

async function loadReviews() {
  const params = new URLSearchParams();
  const sentiment = $("#filter-sentiment").value;
  const product = $("#filter-product").value.trim();
  const keyword = $("#filter-keyword").value.trim();
  if (sentiment) params.set("sentiment", sentiment);
  if (product) params.set("product_name", product);
  if (keyword) params.set("keyword", keyword);

  const reviews = await request(`/api/reviews?${params.toString()}`);
  const tbody = $("#review-table-body");

  if (!reviews.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">暂无评论数据</td></tr>`;
    return;
  }

  tbody.innerHTML = reviews
    .map(
      (review) => `
      <tr>
        <td>${review.id}</td>
        <td>${review.product_name}</td>
        <td>${review.content}</td>
        <td>${formatScore(review.score)}</td>
        <td><span class="badge ${review.sentiment}">${SENTIMENT_LABELS[review.sentiment]}</span></td>
        <td>${review.source}</td>
        <td><button class="btn btn-danger" data-delete="${review.id}">删除</button></td>
      </tr>
    `
    )
    .join("");

  tbody.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("确认删除这条评论吗？")) return;
      await request(`/api/reviews/${button.dataset.delete}`, { method: "DELETE" });
      await loadReviews();
      await loadDashboard();
    });
  });
}

async function loadKeywords() {
  const sentiment = $("#keyword-sentiment").value;
  const params = new URLSearchParams();
  if (sentiment) params.set("sentiment", sentiment);
  const keywords = await request(`/api/keywords?${params.toString()}`);
  const maxCount = keywords[0]?.count || 1;
  const container = $("#keyword-list");

  if (!keywords.length) {
    container.innerHTML = `<div class="empty">暂无关键词数据</div>`;
    return;
  }

  container.innerHTML = keywords
    .map((item) => {
      const width = Math.round((item.count / maxCount) * 100);
      return `
        <div class="keyword-item">
          <div style="flex:1;">
            <div>${item.word}</div>
            <div class="bar"><span style="width:${width}%"></span></div>
          </div>
          <strong>${item.count}</strong>
        </div>
      `;
    })
    .join("");
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => switchSection(item.dataset.section));
});

$("#btn-analyze").addEventListener("click", analyzeSingle);
$("#btn-save-review").addEventListener("click", saveSingleReview);
$("#btn-batch-submit").addEventListener("click", submitBatch);
$("#btn-upload").addEventListener("click", uploadCsv);
$("#btn-search").addEventListener("click", loadReviews);
$("#btn-load-keywords").addEventListener("click", loadKeywords);

$("#btn-export").addEventListener("click", () => {
  window.open("/api/export", "_blank");
});

$("#btn-reload-sample").addEventListener("click", async () => {
  if (!confirm("将清空现有数据并重新加载示例评论，是否继续？")) return;
  const result = await request("/api/seed", { method: "POST" });
  alert(`${result.message}，共 ${result.count} 条`);
  await loadDashboard();
});

$("#btn-clear").addEventListener("click", async () => {
  if (!confirm("确认清空全部评论数据吗？")) return;
  await request("/api/reviews", { method: "DELETE" });
  await loadDashboard();
  await loadReviews();
});

loadDashboard();
