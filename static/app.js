"use strict";

const state = {
  user: null,
  options: null,
  recipes: [],
  ingredients: [],
  categories: [],
  selected: new Set(),
  currentTab: "recipes",
};

// ---------- 工具 ----------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 2200);
}

async function api(method, path, body) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (res.status === 401) {
    state.user = null; renderUser();
    throw new Error((data && data.detail) || "未登录");
  }
  if (!res.ok) throw new Error((data && data.detail) || "请求失败");
  return data;
}

// 客户端单位美化（与后端保持一致）
const WT = { 克: 1, 两: 50, 斤: 500, 公斤: 1000, 毫克: 0.001 };
const VT = { 毫升: 1, 升: 1000, 茶匙: 5, 汤匙: 15, 勺: 15 };
function dim(u) { if (u in WT) return "weight"; if (u in VT) return "volume"; return "other"; }
function pretty(q, u) {
  const d = dim(u);
  if (d === "weight") {
    const g = q * WT[u];
    if (g >= 500) { const j = Math.floor(g / 500), l = (g - j * 500) / 50; return Math.abs(l) < 1e-6 ? `${j}斤` : `${j}斤${l}两`; }
    return `${g}克`;
  }
  if (d === "volume") {
    const ml = q * VT[u];
    if (ml >= 1000) return `${ml / 1000}升`;
    return `${ml}毫升`;
  }
  if (["适量", "少许", "按口味", "若干"].includes(u)) return u;
  return q ? `${q}${u}` : (u || "");
}
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function fmtLocal(d) {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, "0"), da = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${da}`;
}
function mondayOf(date) {
  const d = new Date(date);
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  return d;
}

// ---------- 鉴权 UI ----------
function renderUser() {
  const box = $("#userbox");
  if (state.user) {
    box.innerHTML = `<span>👤 ${esc(state.user)}</span><button class="btn ghost sm" data-action="logout">退出</button>`;
  } else {
    box.innerHTML = `<button class="btn sm" data-action="openLogin">登录</button>`;
  }
}

function openLogin() {
  $("#modalContent").innerHTML = `
    <h3>登录</h3>
    <form id="loginForm">
      <p class="muted">账号密码已启用浏览器/密码管理器自动填充。</p>
      <div class="row" style="margin-bottom:10px">
        <input name="username" autocomplete="username" placeholder="用户名" style="flex:1" required />
      </div>
      <div class="row" style="margin-bottom:14px">
        <input name="password" type="password" autocomplete="current-password" placeholder="密码" style="flex:1" required />
      </div>
      <button class="btn" type="submit">登录</button>
      <span id="loginErr" class="muted"></span>
    </form>`;
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const d = await api("POST", "/api/login", { username: f.username.value, password: f.password.value });
      state.user = d.user; renderUser(); closeModal(); toast("登录成功");
    } catch (err) { $("#loginErr").textContent = err.message; }
  });
  showModal();
}

// ---------- 模态框 ----------
function showModal() { $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); $("#modalContent").innerHTML = ""; }
$("#modalClose").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

// ---------- 菜谱 ----------
async function loadRecipes() { state.recipes = await api("GET", "/api/recipes"); }

function recipeCard(r) {
  const checked = state.selected.has(r.id) ? "checked" : "";
  return `<div class="recipe">
    <div class="recipe-main" data-action="recipe-detail" data-id="${r.id}">
      ${coverThumb(r)}
      <div style="min-width:0">
        <div><b>${esc(r.title)}</b></div>
        <div class="meta">
          <span class="tag">${esc(r.cuisine)}</span>
          <span class="tag">${esc(r.method)}</span>
          <span class="tag">${esc(r.difficulty)}</span>
          约 ${r.prep_time + r.cook_time} 分钟 · ${r.servings} 人份
        </div>
      </div>
    </div>
    <input type="checkbox" class="check" ${checked} data-action="recipe-select" data-id="${r.id}" title="加入采购" />
  </div>`;
}

function coverThumb(r) {
  return r.cover
    ? `<img class="thumb" src="${esc(r.cover)}" alt="" loading="lazy" />`
    : `<div class="thumb ph">${esc((r.title || "菜").slice(0, 1))}</div>`;
}

function renderCoverPreview(src) {
  const box = $("#coverPreview");
  if (!box) return;
  box.innerHTML = src ? `<img class="cover-preview" src="${esc(src)}" alt="" />` : '<div class="cover-preview">无封面</div>';
}

async function uploadCover(rid, file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`/api/recipes/${rid}/cover`, {
    method: "POST", body: fd, credentials: "same-origin",
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(data.detail || "上传失败");
  return data.cover;
}

async function viewRecipes() {
  const view = $("#view");
  const opts = state.options || {};
  view.innerHTML = `
    <div class="card">
      <div class="row" style="margin-bottom:10px">
        <input id="rcSearch" placeholder="搜索菜名" style="flex:2" />
        <select id="rcCuisine"><option value="">全部菜系</option>${(opts.cuisines || []).map((c) => `<option>${c}</option>`).join("")}</select>
        <select id="rcMethod"><option value="">全部做法</option>${(opts.methods || []).map((c) => `<option>${c}</option>`).join("")}</select>
        ${state.user ? `<button class="btn" data-action="recipe-new">+ 新建菜谱</button>` : ""}
        <button class="btn ok" data-action="gen-shopping-selected">生成采购（选中 ${state.selected.size}）</button>
      </div>
      <div id="rcList"></div>
    </div>`;
  await refreshRecipeList();
  $("#rcSearch").addEventListener("input", debounce(refreshRecipeList, 300));
  $("#rcCuisine").addEventListener("change", refreshRecipeList);
  $("#rcMethod").addEventListener("change", refreshRecipeList);
}

async function refreshRecipeList() {
  const q = $("#rcSearch") ? $("#rcSearch").value : "";
  const cuisine = $("#rcCuisine") ? $("#rcCuisine").value : "";
  const method = $("#rcMethod") ? $("#rcMethod").value : "";
  let url = "/api/recipes?q=" + encodeURIComponent(q);
  if (cuisine) url += "&cuisine=" + encodeURIComponent(cuisine);
  if (method) url += "&method=" + encodeURIComponent(method);
  state.recipes = await api("GET", url);
  $("#rcList").innerHTML = state.recipes.length
    ? state.recipes.map(recipeCard).join("")
    : `<p class="muted">暂无菜谱，点“新建菜谱”或去“导入”页从下厨房拉取。</p>`;
  const btn = $('[data-action="gen-shopping-selected"]');
  if (btn) btn.textContent = `生成采购（选中 ${state.selected.size}）`;
}

async function openRecipeDetail(id) {
  const r = await api("GET", "/api/recipes/" + id);
  const ings = r.ingredients.map((i) => `<tr><td>${esc(i.name)}</td><td>${pretty(i.quantity, i.unit)}</td><td class="muted">${esc(i.note || "")}</td></tr>`).join("");
  const steps = r.steps.map((s, idx) => `<div class="step"><b>第${idx + 1}步 ${esc(s.title || "")}</b><div>${esc(s.text)}</div>${s.tip ? `<div class="tip">💡 ${esc(s.tip)}</div>` : ""}</div>`).join("");
  $("#modalContent").innerHTML = `
    ${r.cover ? `<img class="cover-hero" src="${esc(r.cover)}" alt="${esc(r.title)}" />` : ""}
    <h3>${esc(r.title)}</h3>
    <div class="meta" style="margin-bottom:8px">
      <span class="tag">${esc(r.cuisine)}</span><span class="tag">${esc(r.method)}</span><span class="tag">${esc(r.difficulty)}</span>
      ${r.prep_time ? `准备 ${r.prep_time} 分钟 · ` : ""}烹饪 ${r.cook_time} 分钟 · ${r.servings} 人份
      ${r.taste_tags ? `· 口味 ${esc(r.taste_tags)}` : ""}
    </div>
    <h4>食材</h4>
    <table><thead><tr><th>食材</th><th>用量</th><th>备注</th></tr></thead><tbody>${ings || '<tr><td colspan="3" class="muted">无</td></tr>'}</tbody></table>
    <h4>步骤</h4>${steps || '<p class="muted">无</p>'}
    ${r.tips ? `<hr><div class="tip">💡 小贴士：${esc(r.tips)}</div>` : ""}
    ${r.source_url ? `<p class="muted">来源：${esc(r.source_name || "")} <a href="${esc(r.source_url)}" target="_blank">链接</a></p>` : ""}
    <hr>
    <div class="row">
      ${state.user ? `<button class="btn" data-action="recipe-edit" data-id="${r.id}">编辑</button>
       <button class="btn danger" data-action="recipe-delete" data-id="${r.id}">删除</button>` : ""}
      <button class="btn ok" data-action="recipe-add-shopping" data-id="${r.id}">加入采购清单</button>
    </div>`;
  showModal();
}

function ingRowHtml(ing, idx) {
  return `<div class="ing-row" data-idx="${idx}">
    <input class="ing-name" list="ingNames" placeholder="食材名" value="${esc(ing && ing.name || "")}" />
    <input class="ing-qty" type="number" step="0.01" placeholder="数量" value="${ing && ing.quantity != null ? ing.quantity : ""}" />
    <input class="ing-unit" list="unitList" placeholder="单位" value="${esc(ing && ing.unit || "克")}" />
    <input class="ing-note" placeholder="备注" value="${esc(ing && ing.note || "")}" />
    <button class="btn ghost sm" data-action="ing-row-del">✕</button>
  </div>`;
}

async function openRecipeForm(id, prefill) {
  let r;
  if (id) r = await api("GET", "/api/recipes/" + id);
  else if (prefill) r = prefill;
  else r = { ingredients: [{ name: "", quantity: 0, unit: "克", note: "" }], steps: [{ text: "" }] };
  const opts = state.options || {};
  const ingNames = state.ingredients.map((i) => `<option value="${esc(i.name)}">`).join("");
  const units = ["克", "两", "斤", "公斤", "毫升", "升", "汤匙", "茶匙", "勺", "个", "根", "瓣", "块", "把", "棵", "适量", "少许", "按口味"].map((u) => `<option value="${u}">`).join("");
  $("#modalContent").innerHTML = `
    <h3>${id ? "编辑菜谱" : "新建菜谱"}</h3>
    <datalist id="ingNames">${ingNames}</datalist>
    <datalist id="unitList">${units}</datalist>
    <div class="grid">
      <input id="f_title" placeholder="菜名（必填）" value="${esc(r.title || "")}" />
      <div class="row">
        <select id="f_cuisine">${(opts.cuisines || []).map((c) => `<option ${c === r.cuisine ? "selected" : ""}>${c}</option>`).join("")}</select>
        <select id="f_method">${(opts.methods || []).map((c) => `<option ${c === r.method ? "selected" : ""}>${c}</option>`).join("")}</select>
        <select id="f_diff">${(opts.difficulties || []).map((c) => `<option ${c === r.difficulty ? "selected" : ""}>${c}</option>`).join("")}</select>
      </div>
      <div class="row">
        <label>人份 <input id="f_serv" type="number" value="${r.servings || 2}" style="width:70px" /></label>
        <label>准备(分) <input id="f_prep" type="number" value="${r.prep_time || 0}" style="width:70px" /></label>
        <label>烹饪(分) <input id="f_cook" type="number" value="${r.cook_time || 0}" style="width:70px" /></label>
      </div>
      <input id="f_taste" placeholder="口味标签，逗号分隔：咸鲜,麻辣" value="${esc(r.taste_tags || "")}" />
      <textarea id="f_tips" placeholder="小贴士（整体提示，如“提前腌制冷藏更入味”）" rows="2">${esc(r.tips || "")}</textarea>
      <div class="row">
        <input id="f_src_name" placeholder="来源名称（如 下厨房）" value="${esc(r.source_name || "")}" />
        <input id="f_src_url" placeholder="来源链接" value="${esc(r.source_url || "")}" />
      </div>
    </div>
    <hr>
    <h4>封面图</h4>
    <div class="cover-edit">
      <div id="coverPreview"></div>
      <div class="grid" style="flex:1">
        <input type="file" id="f_cover_file" accept="image/*" />
        <div class="row">
          <input id="f_cover" placeholder="或粘贴图片链接（http/https）" value="${esc(r.cover || "")}" style="flex:1" />
          <button class="btn ghost sm" type="button" data-action="cover-clear">移除</button>
        </div>
        <span class="muted">支持 JPG/PNG/WebP，自动压缩到 1280px 内</span>
      </div>
    </div>
    <hr>
    <h4>食材</h4>
    <div id="ingList">${r.ingredients.map((i, n) => ingRowHtml(i, n)).join("")}</div>
    <button class="btn ghost sm" data-action="ing-row-add">+ 添加食材</button>
    <hr>
    <h4>步骤（每行一步）</h4>
    <textarea id="f_steps" rows="8" placeholder="第一步内容&#10;第二步内容">${r.steps.map((s) => s.text).join("\n")}</textarea>
    <hr>
    <div class="row">
      <button class="btn" data-action="save-recipe" data-id="${id || ""}">保存</button>
      <span id="f_err" class="muted"></span>
    </div>`;
  $("#ingList").addEventListener("click", (e) => {
    if (e.target.dataset.action === "ing-row-del") e.target.closest(".ing-row").remove();
  });
  state._pendingCover = null;
  renderCoverPreview(r.cover || "");
  $("#f_cover_file").addEventListener("change", (e) => {
    const f = e.target.files && e.target.files[0];
    state._pendingCover = f || null;
    if (f) renderCoverPreview(URL.createObjectURL(f));
  });
  $("#f_cover").addEventListener("input", (e) => {
    if (!state._pendingCover) renderCoverPreview(e.target.value.trim());
  });
  showModal();
}

async function saveRecipe(id, btn) {
  const ings = $$("#ingList .ing-row").map((row) => ({
    name: $(".ing-name", row).value.trim(),
    quantity: parseFloat($(".ing-unit", row).value && $(".ing-qty", row).value) || 0,
    unit: $(".ing-unit", row).value.trim() || "克",
    note: $(".ing-note", row).value.trim(),
    order_idx: 0,
    ingredient_id: null,
  })).filter((i) => i.name);
  const stepsText = $("#f_steps").value.split("\n").map((s) => s.trim()).filter(Boolean);
  const payload = {
    title: $("#f_title").value.trim(),
    cuisine: $("#f_cuisine").value,
    method: $("#f_method").value,
    difficulty: $("#f_diff").value,
    servings: parseInt($("#f_serv").value) || 2,
    prep_time: parseInt($("#f_prep").value) || 0,
    cook_time: parseInt($("#f_cook").value) || 0,
    taste_tags: $("#f_taste").value.trim(),
    tips: $("#f_tips").value.trim(),
    source_name: $("#f_src_name").value.trim(),
    source_url: $("#f_src_url").value.trim(),
    cover: $("#f_cover") ? $("#f_cover").value.trim() : "",
    ingredients: ings,
    steps: stepsText.map((t, i) => ({ step_no: i + 1, text: t, title: "", tip: "" })),
  };
  if (!payload.title) { $("#f_err").textContent = "菜名必填"; return; }
  // 关联已有食材 id
  const nameToId = {};
  state.ingredients.forEach((i) => (nameToId[i.name] = i.id));
  payload.ingredients.forEach((i) => { if (nameToId[i.name]) i.ingredient_id = nameToId[i.name]; });
  try {
    let saved;
    if (id) saved = await api("PUT", "/api/recipes/" + id, payload);
    else saved = await api("POST", "/api/recipes", payload);
    if (state._pendingCover && saved && saved.id) {
      try {
        await uploadCover(saved.id, state._pendingCover);
        state._pendingCover = null;
      } catch (err) {
        toast("菜谱已保存，但封面上传失败：" + err.message);
      }
    }
    toast("已保存");
    closeModal();
    await refreshRecipeList();
  } catch (e) { $("#f_err").textContent = e.message; }
}

// ---------- 食材库 ----------
async function loadIngredients() {
  const [ings, cats] = await Promise.all([api("GET", "/api/ingredients"), api("GET", "/api/categories")]);
  state.ingredients = ings; state.categories = cats;
}
function catName(id) { const c = state.categories.find((x) => x.id === id); return c ? c.name : "未分类"; }

async function viewIngredients() {
  await loadIngredients();
  const tree = state.categories.map((c) => {
    const subs = state.categories.filter((x) => x.parent_id === c.id);
    const subNames = subs.map((s) => catName(s.id)).join(" / ");
    const count = state.ingredients.filter((i) => {
      if (i.category_id === c.id) return true;
      return subs.some((s) => s.id === i.category_id);
    }).length;
    return `<div class="card" style="margin:0"><b>${c.icon || ""} ${esc(c.name)}</b> <span class="muted">(${count})</span>${subNames ? ` <span class="muted">· ${esc(subNames)}</span>` : ""}</div>`;
  }).join("");
  const rows = state.ingredients.map((i) => `<tr><td>${esc(i.name)}</td><td>${esc(catName(i.category_id))}</td><td>${esc(i.default_unit)}</td><td class="muted">${esc(i.purchase_spec || "")}</td><td class="muted">${esc(i.channel || "")}</td>${state.user ? `<td><button class="btn ghost sm danger" data-action="ing-del" data-id="${i.id}">删</button></td>` : "<td></td>"}</tr>`).join("");
  $("#view").innerHTML = `
    <div class="card"><h4>分类</h4>${tree || '<p class="muted">暂无</p>'}</div>
    ${state.user ? `<div class="card">
      <h4>新增食材</h4>
      <div class="row">
        <input id="n_name" placeholder="食材名" />
        <select id="n_cat"><option value="">未分类</option>${state.categories.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>
        <input id="n_unit" placeholder="默认单位" value="克" style="width:90px" />
        <input id="n_spec" placeholder="采购规格" />
        <input id="n_ch" placeholder="常用渠道" />
        <button class="btn" data-action="ing-add">添加</button>
      </div>
      <span id="n_err" class="muted"></span>
    </div>` : ""}
    <div class="card"><h4>全部食材（${state.ingredients.length}）</h4>
      <table><thead><tr><th>名称</th><th>分类</th><th>单位</th><th>规格</th><th>渠道</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="6" class="muted">暂无</td></tr>'}</tbody></table>
    </div>`;
}

// ---------- 采购清单 ----------
async function viewShopping() {
  let lists = await api("GET", "/api/shopping-lists");
  const selNote = state.selected.size
    ? `<button class="btn ok" data-action="gen-shopping-selected">从选中菜谱生成（${state.selected.size}）</button>`
    : `<span class="muted">提示：在“菜谱”页勾选菜谱后可一键生成采购清单</span>`;
  $("#view").innerHTML = `
    <div class="card row" style="justify-content:space-between">
      <div class="row">${selNote}</div>
      <div class="row">
        <input id="mp_from" type="date" /> <input id="mp_to" type="date" />
        <button class="btn" data-action="gen-shopping-week">从周菜单生成</button>
      </div>
    </div>
    <div id="slList">
      ${(lists || []).map((l) => `<div class="recipe"><div data-action="open-shopping" data-id="${l.id}" style="flex:1;cursor:pointer"><b>${esc(l.name)}</b> <span class="muted">· ${l.item_count} 项，已购 ${l.checked_count}</span> <span class="muted">${esc(l.created_at.slice(0, 10))}</span></div><button class="btn ghost sm danger" data-action="del-shopping" data-id="${l.id}">删除</button></div>`).join("") || '<p class="muted">还没有采购清单。</p>'}
    </div>`;
}

async function openShopping(id) {
  const l = await api("GET", "/api/shopping-lists/" + id);
  const items = l.items.map((i) => `<tr>
    <td><input type="checkbox" class="check" data-action="toggle-item" data-lid="${l.id}" data-iid="${i.id}" ${i.checked ? "checked" : ""} /></td>
    <td style="${i.checked ? "text-decoration:line-through;color:var(--muted)" : ""}">${esc(i.name)}</td>
    <td><b>${esc(i.display || pretty(i.quantity, i.unit))}</b></td>
    <td><input class="i-ch" data-action="ch-change" data-lid="${l.id}" data-iid="${i.id}" value="${esc(i.channel || "")}" placeholder="渠道" style="width:90px" /></td>
  </tr>`).join("");
  $("#modalContent").innerHTML = `
    <h3>${esc(l.name)}</h3>
    <p class="muted">勾选表示已购买；渠道可填写菜市场/超市/电商等，方便分头采购。</p>
    <table><thead><tr><th></th><th>食材</th><th>数量</th><th>渠道</th></tr></thead><tbody>${items}</tbody></table>`;
  showModal();
}

// ---------- 周菜单 ----------
async function viewMealPlan() {
  if (!state.recipes.length) await loadRecipes();
  const start = mondayOf(new Date());
  const startDate = fmtLocal(start);
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start); d.setDate(d.getDate() + i);
    days.push(fmtLocal(d));
  }
  $("#view").innerHTML = `
    <div class="card row" style="justify-content:space-between">
      <div class="row">本周从 <b>${startDate}</b> 起</div>
      <button class="btn ok" data-action="gen-shopping-week">生成本周采购清单</button>
    </div>
    <div class="card"><div class="week" id="weekGrid"></div></div>`;
  const endDate = days[6];
  const plans = await api("GET", "/api/meal-plan?date_from=" + startDate + "&date_to=" + endDate);
  const byDay = {};
  plans.forEach((p) => { (byDay[p.plan_date] = byDay[p.plan_date] || []).push(p); });
  const recipeOpts = state.recipes.map((r) => `<option value="${r.id}">${esc(r.title)}</option>`).join("");
  $("#weekGrid").innerHTML = days.map((d) => {
    const list = (byDay[d] || []).map((p) => {
      const r = state.recipes.find((x) => x.id === p.recipe_id);
      return `<div class="slot"><small>${esc(p.meal_type)}</small> ${esc(r ? r.title : "已删除")} <button class="btn ghost sm danger" data-action="meal-del" data-id="${p.id}">✕</button></div>`;
    }).join("") || '<div class="slot muted">—</div>';
    return `<div class="day"><h4>${d.slice(5)}</h4>${list}
      <div class="row" style="margin-top:6px">
        <select class="mp-recipe" data-date="${d}">${recipeOpts}</select>
        <select class="mp-meal" data-date="${d}"><option>早餐</option><option>午餐</option><option>晚餐</option><option>加餐</option></select>
        <button class="btn sm" data-action="meal-add" data-date="${d}">+</button>
      </div></div>`;
  }).join("");
}

// ---------- 导入 ----------
function viewImport() {
  $("#view").innerHTML = `
    <div class="card">
      <h4>从下厨房导入</h4>
      <p class="muted">粘贴菜谱链接（m.xiachufang.com 或 www.xiachufang.com/recipe/数字），
      系统会尽力解析用料与步骤，导入前请务必复核。</p>
      <div class="row">
        <input id="imp_url" placeholder="https://www.xiachufang.com/recipe/12345/" style="flex:1" />
        <button class="btn" data-action="import-run">解析</button>
      </div>
      <span id="imp_err" class="muted"></span>
    </div>`;
}

async function runImport() {
  const url = $("#imp_url").value.trim();
  if (!url) { $("#imp_err").textContent = "请输入链接"; return; }
  $("#imp_err").textContent = "解析中…";
  try {
    const d = await api("POST", "/api/import/xiachufang", { url });
    await openRecipeFormFromDraft(d);
    $("#imp_err").textContent = "";
  } catch (e) {
    $("#imp_err").textContent = "解析失败：" + e.message + "（可手动录入）";
  }
}

async function openRecipeFormFromDraft(d) {
  await loadIngredients();
  const r = {
    title: d.title || "",
    cuisine: "家常", method: "炒", difficulty: "普通",
    servings: 2, prep_time: 0, cook_time: 0, taste_tags: "", tips: "",
    source_url: d.source_url || "", source_name: d.source_name || "下厨房",
    ingredients: (d.ingredients && d.ingredients.length ? d.ingredients : [{ name: "", quantity: 0, unit: "克" }]),
    steps: (d.steps && d.steps.length ? d.steps : [{ text: "" }]),
  };
  await openRecipeForm(null, r);
}

// ---------- 设置 ----------
function viewSettings() {
  const opts = state.options || {};
  const units = ["克", "两", "斤", "毫升", "升", "汤匙", "个", "适量"];
  $("#view").innerHTML = `
    <div class="card">
      <h4>账号</h4>
      ${state.user ? `<p>当前登录：<b>${esc(state.user)}</b></p><button class="btn ghost" data-action="logout">退出登录</button>`
        : `<p class="muted">未登录，登录后可新建/编辑菜谱、食材与采购清单。</p>
           <div class="row">
             <input id="s_user" autocomplete="username" placeholder="用户名" />
             <input id="s_pw" type="password" autocomplete="current-password" placeholder="密码" />
             <button class="btn" data-action="settings-login">登录</button>
           </div><span id="s_err" class="muted"></span>`}
    </div>
    <div class="card">
      <h4>单位换算测试</h4>
      <div class="row">
        <input id="u_qty" type="number" value="550" style="width:90px" />
        <input id="u_unit" list="uList" value="克" style="width:90px" />
        <datalist id="uList">${units.map((u) => `<option value="${u}">`).join("")}</datalist>
        <button class="btn" data-action="u-test">换算</button>
        <b id="u_out"></b>
      </div>
      <p class="muted">支持：斤/两/克/公斤/毫升/升/汤匙/茶匙/勺，以及 个/根/瓣 等计数单位与 适量/少许 定性单位。</p>
    </div>`;
}

// ---------- 事件委托 ----------
document.addEventListener("click", async (e) => {
  const t = e.target.closest("[data-action]");
  if (!t) return;
  const a = t.dataset.action;
  const id = t.dataset.id;
  try {
    if (a === "openLogin") return openLogin();
    if (a === "logout") { await api("POST", "/api/logout"); state.user = null; renderUser(); toast("已退出"); if (state.currentTab !== "recipes") switchTab("recipes"); else await viewRecipes(); return; }
    if (a === "recipe-detail") return openRecipeDetail(id);
    if (a === "recipe-new") return openRecipeForm(null);
    if (a === "recipe-edit") return openRecipeForm(id);
    if (a === "recipe-select") { if (t.checked) state.selected.add(Number(id)); else state.selected.delete(Number(id)); const b = $('[data-action="gen-shopping-selected"]'); if (b) b.textContent = `生成采购（选中 ${state.selected.size}）`; return; }
    if (a === "recipe-delete") { if (!confirm("确认删除该菜谱？")) return; await api("DELETE", "/api/recipes/" + id); toast("已删除"); closeModal(); await refreshRecipeList(); return; }
    if (a === "recipe-add-shopping") { state.selected.add(Number(id)); toast("已加入采购选择，去采购清单页生成"); return; }
    if (a === "cover-clear") {
      state._pendingCover = null;
      if ($("#f_cover")) $("#f_cover").value = "";
      if ($("#f_cover_file")) $("#f_cover_file").value = "";
      renderCoverPreview("");
      return;
    }
    if (a === "ing-row-add") { const n = $$("#ingList .ing-row").length; $("#ingList").insertAdjacentHTML("beforeend", ingRowHtml(null, n)); return; }
    if (a === "ing-add") {
      const name = $("#n_name").value.trim(); if (!name) { $("#n_err").textContent = "名称必填"; return; }
      await api("POST", "/api/ingredients", { name, category_id: $("#n_cat").value ? Number($("#n_cat").value) : null, default_unit: $("#n_unit").value || "克", purchase_spec: $("#n_spec").value, channel: $("#n_ch").value });
      toast("已添加"); await viewIngredients(); return;
    }
    if (a === "ing-del") { if (!confirm("删除该食材？")) return; await api("DELETE", "/api/ingredients/" + id); toast("已删除"); await viewIngredients(); return; }
    if (a === "gen-shopping-selected") {
      if (!state.user) { toast("请先登录"); return openLogin(); }
      if (!state.selected.size) { toast("请先在菜谱页勾选"); return; }
      const d = await api("POST", "/api/shopping-lists/from-recipes", { recipe_ids: Array.from(state.selected), name: "采购清单" });
      toast("已生成采购清单"); state.selected.clear(); switchTab("shopping"); return;
    }
    if (a === "gen-shopping-week") {
      if (!state.user) { toast("请先登录"); return openLogin(); }
      const from = ($("#mp_from") && $("#mp_from").value) || mondayOf(new Date()).toISOString().slice(0, 10);
      const to = ($("#mp_to") && $("#mp_to").value) || fmtLocal(new Date(mondayOf(new Date()).getTime() + 6 * 864e5));
      await api("POST", "/api/shopping-lists/from-mealplan", { from, to, name: "周采购清单" });
      toast("已按周菜单生成"); switchTab("shopping"); return;
    }
    if (a === "open-shopping") return openShopping(id);
    if (a === "del-shopping") { if (!confirm("删除该采购清单？")) return; await api("DELETE", "/api/shopping-lists/" + id); toast("已删除"); await viewShopping(); return; }
    if (a === "meal-add") {
      if (!state.user) { toast("请先登录"); return openLogin(); }
      const rid = $(`.mp-recipe[data-date="${id}"]`).value;
      const meal = $(`.mp-meal[data-date="${id}"]`).value;
      await api("POST", "/api/meal-plan", { plan_date: id, meal_type: meal, recipe_id: Number(rid) });
      toast("已添加"); await viewMealPlan(); return;
    }
    if (a === "meal-del") { await api("DELETE", "/api/meal-plan/" + id); toast("已移除"); await viewMealPlan(); return; }
    if (a === "import-run") return runImport();
    if (a === "settings-login") {
      try { const d = await api("POST", "/api/login", { username: $("#s_user").value, password: $("#s_pw").value }); state.user = d.user; renderUser(); toast("登录成功"); await viewSettings(); }
      catch (err) { $("#s_err").textContent = err.message; }
      return;
    }
    if (a === "u-test") {
      const d = await api("GET", "/api/units/info?qty=" + $("#u_qty").value + "&unit=" + encodeURIComponent($("#u_unit").value));
      $("#u_out").textContent = "→ " + d.pretty + "（维度：" + d.dimension + "）"; return;
    }
  } catch (err) {
    toast(err.message);
  }
});

// 动态控件事件
document.addEventListener("change", async (e) => {
  const t = e.target.closest("[data-action]");
  if (!t) return;
  const a = t.dataset.action;
  if (a === "toggle-item") {
    await api("PUT", `/api/shopping-lists/${t.dataset.lid}/items/${t.dataset.iid}`, { checked: t.checked });
    if (t.checked) t.closest("tr").querySelector("td:nth-child(2)").style.cssText = "text-decoration:line-through;color:var(--muted)";
    else t.closest("tr").querySelector("td:nth-child(2)").style.cssText = "";
  }
  if (a === "ch-change") {
    clearTimeout(t._tm);
    t._tm = setTimeout(() => api("PUT", `/api/shopping-lists/${t.dataset.lid}/items/${t.dataset.iid}`, { channel: t.value }), 600);
  }
});

$("#view").addEventListener("submit", (e) => {
  if (e.target.id === "loginForm") e.preventDefault();
});

// save-recipe 按钮（在 modal 内）
document.addEventListener("click", (e) => {
  if (e.target.dataset.action === "save-recipe") {
    e.preventDefault();
    saveRecipe(e.target.dataset.id, e.target);
  }
});

// ---------- 标签切换 ----------
const TAB_VIEWS = { recipes: viewRecipes, ingredients: viewIngredients, shopping: viewShopping, mealplan: viewMealPlan, import: viewImport, settings: viewSettings };
function switchTab(name, syncHash = true) {
  if (!TAB_VIEWS[name]) name = "recipes";
  state.currentTab = name;
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (syncHash && location.hash !== "#" + name) {
    try { history.replaceState(null, "", "#" + name); } catch (e) { location.hash = name; }
  }
  return (TAB_VIEWS[name] || viewRecipes)();
}
$("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-tab]"); if (b) switchTab(b.dataset.tab); });
// 支持直接访问 /#shopping 这类深链（可收藏、可从 Unraid WebUI 直达）
window.addEventListener("hashchange", () => {
  const name = location.hash.replace(/^#/, "");
  if (TAB_VIEWS[name] && name !== state.currentTab) switchTab(name, false);
});

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// ---------- 启动 ----------
(async function init() {
  try {
    const me = await api("GET", "/api/me");
    state.user = me.user;
  } catch (e) { state.user = null; }
  try { state.options = await api("GET", "/api/meta/options"); } catch (e) { state.options = {}; }
  renderUser();
  const initial = location.hash.replace(/^#/, "");
  if (TAB_VIEWS[initial]) await switchTab(initial, false);
  else await viewRecipes();
})();
