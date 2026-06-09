import { createApi } from "./api.js";

const bridge = window.AstrBotPluginPage;
const root = document.documentElement;
const themeMediaQuery =
typeof window.matchMedia === "function"
? window.matchMedia("(prefers-color-scheme: dark)")
: null;
const THEME_STORAGE_KEY = "geetest-verify-page-theme-mode";
const DEFAULT_GROUP_ID = "__default__";
const DEFAULT_GROUP_ICON = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><rect width='96' height='96' rx='24' fill='%236EB1D8'/><svg x='24' y='24' width='48' height='48' viewBox='0 -960 960 960' fill='%231f1f1f'><path d='M440-120v-240h80v80h320v80H520v80h-80Zm-320-80v-80h240v80H120Zm160-160v-80H120v-80h160v-80h80v240h-80Zm160-80v-80h400v80H440Zm160-160v-240h80v80h160v80H680v80h-80Zm-480-80v-80h400v80H120Z'/></svg></svg>";
const CHECK_ICON = "data:image/png;base64,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";

let api = null;
let bootstrapData = null;
let currentGroup = null;
let allGroups = [];
let detachContextHandler = null;
let detachSystemThemeHandler = null;
let themePreference = loadThemePreference();

const els = {
  groupForm: document.getElementById("groupForm"),
  groupList: document.getElementById("groupList"),
  groupSearchInput: document.getElementById("groupSearchInput"),
  groupDetailHeader: document.getElementById("groupDetailHeader"),
  groupInfoAvatar: document.getElementById("groupInfoAvatar"),
  groupInfoName: document.getElementById("groupInfoName"),
  groupInfoSub: document.getElementById("groupInfoSub"),
  groupListCount: document.getElementById("groupListCount"),
  toastLayer: document.getElementById("toastLayer"),
  toggleThemeBtn: document.getElementById("toggleThemeBtn"),
  addGroupBtn: document.getElementById("addGroupBtn"),
  saveGroupBtn: document.getElementById("saveGroupBtn"),
  deleteGroupBtn: document.getElementById("deleteGroupBtn"),
  addGroupModal: document.getElementById("addGroupModal"),
  modalCloseBtn: document.getElementById("modalCloseBtn"),
  modalSearchInput: document.getElementById("modalSearchInput"),
  modalGroupList: document.getElementById("modalGroupList"),
  modalConfirmBtn: document.getElementById("modalConfirmBtn"),
  deleteConfirmModal: document.getElementById("deleteConfirmModal"),
  deleteConfirmCloseBtn: document.getElementById("deleteConfirmCloseBtn"),
  deleteConfirmBody: document.getElementById("deleteConfirmBody"),
  deleteConfirmCancelBtn: document.getElementById("deleteConfirmCancelBtn"),
  deleteConfirmOkBtn: document.getElementById("deleteConfirmOkBtn"),
};

/* -- theme -- */
function loadThemePreference() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "auto") {
      return stored;
    }
  } catch {}
  return "auto";
}

function saveThemePreference() {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
  } catch {}
}

function getThemeButtonLabel() {
  if (themePreference === "dark") return "主题: 深色";
  if (themePreference === "light") return "主题: 浅色";
  return "主题: 自动";
}

function updateThemeButton() {
  if (els.toggleThemeBtn) {
    els.toggleThemeBtn.textContent = getThemeButtonLabel();
  }
}

function getBridgeThemeMode(context) {
  if (context?.theme === "dark" || context?.theme === "light") {
    return context.theme;
  }
  return null;
}

function getSystemThemeMode() {
  return themeMediaQuery?.matches ? "dark" : "light";
}

function resolveThemeMode(context) {
  if (themePreference === "dark" || themePreference === "light") {
    return themePreference;
  }
  const bridgeThemeMode = getBridgeThemeMode(context);
  if (bridgeThemeMode) {
    return bridgeThemeMode;
  }
  return getSystemThemeMode();
}

function applyThemeMode(themeMode) {
  root.dataset.theme = themeMode;
  root.style.colorScheme = themeMode;
}

function syncThemeFromContext(context) {
  applyThemeMode(resolveThemeMode(context));
  updateThemeButton();
}

function cycleThemePreference() {
  if (themePreference === "auto") {
    themePreference = "dark";
  } else if (themePreference === "dark") {
    themePreference = "light";
  } else {
    themePreference = "auto";
  }
  saveThemePreference();
  syncThemeFromContext(bridge?.getContext?.());
}

function bindSystemTheme() {
  if (!themeMediaQuery) return;
  const handleThemeChange = () => {
    if (themePreference === "auto") {
      applyThemeMode(resolveThemeMode(bridge?.getContext?.()));
    }
  };
  if (typeof themeMediaQuery.addEventListener === "function") {
    themeMediaQuery.addEventListener("change", handleThemeChange);
    detachSystemThemeHandler = () => {
      themeMediaQuery.removeEventListener("change", handleThemeChange);
    };
    return;
  }
  if (typeof themeMediaQuery.addListener === "function") {
    themeMediaQuery.addListener(handleThemeChange);
    detachSystemThemeHandler = () => {
      themeMediaQuery.removeListener(handleThemeChange);
    };
  }
}

/* -- toast -- */
function showToast(message, type = "success") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  els.toastLayer.appendChild(node);
  setTimeout(() => {
    node.classList.add("fade-out");
    node.addEventListener("animationend", () => node.remove());
  }, 2600);
}

/* -- form renderer -- */
function setByPath(target, path, value) {
  const parts = path.split(".");
  let cursor = target;
  parts.forEach((part, index) => {
    if (index === parts.length - 1) {
      cursor[part] = value;
      return;
    }
    if (!cursor[part] || typeof cursor[part] !== "object") {
      cursor[part] = {};
    }
    cursor = cursor[part];
  });
}

function buildField(key, schema, value, prefix) {
  const path = prefix ? `${prefix}.${key}` : key;
  const type = schema.type || "string";

  if (type === "object") {
    return buildObjectField(path, key, schema, value || {});
  }

  const field = document.createElement("label");
  field.className = "field";

  const copy = document.createElement("div");
  copy.className = "field-copy";

  const label = document.createElement("div");
  label.className = "field-label";
  label.textContent = schema.description || key;
  copy.appendChild(label);

  if (schema.hint) {
    const hint = document.createElement("div");
    hint.className = "field-hint";
    hint.textContent = schema.hint;
    copy.appendChild(hint);
  }

  field.appendChild(copy);

  const control = document.createElement("div");
  control.className = "field-control";

  let input;
  if (type === "bool") {
    field.classList.add("checkbox-field");
    const shell = document.createElement("span");
    shell.className = "switch";
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    const slider = document.createElement("span");
    slider.className = "slider";
    shell.appendChild(input);
    shell.appendChild(slider);
    control.appendChild(shell);
  } else if (type === "int") {
    input = document.createElement("input");
    input.type = "number";
    input.value = String(value ?? schema.default ?? 0);
    if (schema.slider) {
      if (schema.slider.min !== undefined) input.min = schema.slider.min;
      if (schema.slider.max !== undefined) input.max = schema.slider.max;
    }
    control.appendChild(input);
  } else if (type === "list") {
    input = document.createElement("textarea");
    input.value = Array.isArray(value) ? value.join("\n") : "";
    input.placeholder = "每行一个条目";
    control.appendChild(input);
  } else {
    input = document.createElement("input");
    input.type = "text";
    input.value = String(value ?? schema.default ?? "");
    control.appendChild(input);
  }

  input.dataset.path = path;
  input.dataset.type = type;
  field.appendChild(control);
  return field;
}

function buildObjectField(path, key, schema, values) {
  const wrapper = document.createElement("section");
  wrapper.className = "form-object";

  const header = document.createElement("div");
  header.className = "section-head";

  const title = document.createElement("div");
  title.className = "section-title";
  title.textContent = schema.description || key;
  header.appendChild(title);

  if (schema.hint) {
    const hint = document.createElement("div");
    hint.className = "section-hint";
    hint.textContent = schema.hint;
    header.appendChild(hint);
  }

  wrapper.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "field-grid";
  Object.entries(schema.items || {}).forEach(([childKey, childSchema]) => {
    const val = values?.[childKey] ?? childSchema.default;
    grid.appendChild(buildField(childKey, childSchema, val, path));
  });
  wrapper.appendChild(grid);
  return wrapper;
}

function renderSchemaFields(rootEl, schema, values) {
  rootEl.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "field-grid";
  Object.entries(schema).forEach(([key, fieldSchema]) => {
    const val = values?.[key] ?? fieldSchema.default;
    grid.appendChild(buildField(key, fieldSchema, val, ""));
  });
  rootEl.appendChild(grid);
}

function collectFormData(rootEl) {
  const payload = {};
  rootEl.querySelectorAll("[data-path]").forEach((node) => {
    const { path, type } = node.dataset;
    let value;
    if (type === "bool") {
      value = node.checked;
    } else if (type === "int") {
      value = Number(node.value || 0);
    } else if (type === "list") {
      value = node.value
        .split(/\n+/)
        .map((item) => item.trim())
        .filter(Boolean);
    } else {
      value = node.value;
    }
    setByPath(payload, path, value);
  });
  return payload;
}

/* -- group list -- */
function normalizeGroups(groups) {
  return Array.isArray(groups) ? groups : [];
}

function filterGroups() {
  const keyword = String(els.groupSearchInput.value || "")
    .trim()
    .toLowerCase();
  if (!keyword) return allGroups;
  return allGroups.filter((group) => {
    const groupId = String(group.group_id || "").toLowerCase();
    const groupName = String(group.group_name || "").toLowerCase();
    return groupId.includes(keyword) || groupName.includes(keyword);
  });
}

function renderGroupCards(forceRebuild = false) {
  const groups = filterGroups();
  els.groupListCount.textContent = `${groups.length} 个群配置`;

  if (!groups.length) {
    els.groupList.classList.add("empty-state");
    els.groupList.textContent = "没有匹配的群配置。";
    return;
  }

  els.groupList.classList.remove("empty-state");

  // Build a map of existing cards by group_id for reuse
  const existingCards = new Map();
  if (!forceRebuild) {
    els.groupList.querySelectorAll(".group-card").forEach((card) => {
      existingCards.set(card.dataset.groupId, card);
    });
  }

  const fragment = document.createDocumentFragment();

  groups.forEach((group) => {
    const existing = existingCards.get(group.group_id);
    if (existing && !forceRebuild) {
      // Reuse existing card -- only update dynamic parts
      existing.classList.toggle("is-active", group.group_id === currentGroup?.group_id);
      updateCardBadges(existing, group);
      existingCards.delete(group.group_id);
      fragment.appendChild(existing);
      return;
    }

    // Build new card
    const card = document.createElement("article");
    card.className = "group-card";
    card.dataset.groupId = group.group_id;
    if (group.group_id === currentGroup?.group_id) {
      card.classList.add("is-active");
    }

    const avatar = document.createElement("img");
    avatar.className = "group-card-avatar";
    avatar.src =
      group.avatar ||
      (group.is_default_group
        ? DEFAULT_GROUP_ICON
        : "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><rect width='96' height='96' rx='24' fill='%23e8c49a'/><text x='48' y='56' text-anchor='middle' font-size='34' fill='%23824f1f' font-family='Arial'>G</text></svg>");
    avatar.alt = group.group_name + " 头像";
    avatar.loading = "lazy";
    card.appendChild(avatar);

    const main = document.createElement("div");
    main.className = "group-card-main";

    const title = document.createElement("div");
    title.className = "group-card-title";

    const name = document.createElement("div");
    name.className = "group-card-name";
    name.textContent = group.group_name || "群 " + group.group_id;
    title.appendChild(name);

    const badgesEl = document.createElement("span");
    badgesEl.className = "group-card-badges";
    title.appendChild(badgesEl);

    main.appendChild(title);

    const subline = document.createElement("div");
    subline.className = "group-card-subline";
    if (group.is_default_group) {
      subline.innerHTML =
        '<span class="group-card-id">默认模板</span><span>所有群共用的默认验证配置</span>';
    } else {
      subline.innerHTML =
        '<span class="group-card-id">' + group.group_id + "</span>";
    }
    main.appendChild(subline);

    card.appendChild(main);

    card.addEventListener("click", () => {
      switchGroup(group);
    });

    updateCardBadges(card, group);
    fragment.appendChild(card);
  });

  // Remove stale cards that no longer exist in groups
  existingCards.forEach((card) => card.remove());

  els.groupList.innerHTML = "";
  els.groupList.appendChild(fragment);
}

function updateCardBadges(card, group) {
  const badgesEl = card.querySelector(".group-card-badges");
  if (!badgesEl) return;
  badgesEl.innerHTML = "";

  const badges = [];
  if (group.is_default_group) {
    badges.push({ cls: "group-card-badge", text: "全局" });
  }
  if (group.template_name) {
    badges.push({ cls: "group-card-badge", text: group.template_name });
  }

  // Badge based on `enabled` field in group config (skip for default group)
  const cfg = group.config || {};
  if (!group.is_default_group) {
    if (cfg.enabled === true) {
      badges.push({ cls: "group-card-badge enabled", text: "已启用" });
    } else if (cfg.enabled === false) {
      badges.push({ cls: "group-card-badge disabled", text: "已停用" });
    }
  }

  badges.forEach((badgeInfo) => {
    const badge = document.createElement("span");
    badge.className = badgeInfo.cls;
    badge.textContent = badgeInfo.text;
    badgesEl.appendChild(badge);
  });
}

/* -- group detail -- */
function renderGroupDetailHeader(groupPayload) {
  const group = groupPayload;
  const info = group.group_info || {};
  const groupName = info.group_name || group.group_name || "群 " + group.group_id;
  const groupId = group.group_id || "";

  els.groupDetailHeader.style.display = "";
  els.groupInfoName.textContent = groupName;

  if (groupId === DEFAULT_GROUP_ID) {
    els.groupInfoSub.textContent = "全局默认配置";
  } else {
    els.groupInfoSub.textContent = "群号: " + groupId;
  }

  if (els.groupInfoAvatar) {
    els.groupInfoAvatar.src =
      (info.avatar || group.avatar) ||
      (group.is_default_group
        ? DEFAULT_GROUP_ICON
        : "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><rect width='96' height='96' rx='24' fill='%23e8c49a'/><text x='48' y='56' text-anchor='middle' font-size='34' fill='%23824f1f' font-family='Arial'>G</text></svg>");
    els.groupInfoAvatar.alt = groupName + " 头像";
  }
}

function renderGroupForm(groupPayload) {
  currentGroup = groupPayload;

  // Render detail header with avatar + name
  renderGroupDetailHeader(groupPayload);

  const isDefault = Boolean(groupPayload.is_default_group);
  const schema = bootstrapData?.schema || {};

  els.groupForm.innerHTML = "";

  if (isDefault) {
    // Default group: show global config section only
    const globalConfig = bootstrapData?.global_config || {};

    // Render global config section
    if (schema.global && Object.keys(schema.global).length > 0) {
      const globalSection = buildSchemaSection("全局配置", "对所有群生效的通用配置项", schema.global, globalConfig);
      els.groupForm.appendChild(globalSection);
    }

    els.deleteGroupBtn.style.display = "none";
    els.saveGroupBtn.textContent = "保存默认全局配置";
  } else {
    // Per-group: render only the per-group template fields
    const groupSchema = filterOutKeys(schema.default || {}, ["group_id"]);
    const config = groupPayload.config || {};
    renderSchemaFields(els.groupForm, groupSchema, config);

    els.deleteGroupBtn.style.display = "";
    els.saveGroupBtn.textContent = "保存此群配置";
  }

  renderGroupCards();
}

function buildSchemaSection(title, hint, schemaObj, values) {
  const section = document.createElement("section");
  section.className = "form-section";

  const head = document.createElement("div");
  head.className = "section-head";

  const titleEl = document.createElement("div");
  titleEl.className = "section-title";
  titleEl.textContent = title;
  head.appendChild(titleEl);

  if (hint) {
    const hintEl = document.createElement("div");
    hintEl.className = "section-hint";
    hintEl.textContent = hint;
    head.appendChild(hintEl);
  }

  section.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "field-grid";
  Object.entries(schemaObj).forEach(([key, fieldSchema]) => {
    const val = values?.[key] ?? fieldSchema.default;
    grid.appendChild(buildField(key, fieldSchema, val, ""));
  });
  section.appendChild(grid);

  return section;
}

function filterOutKeys(obj, keysToRemove, extraExcludeSet) {
  const set = new Set(keysToRemove);
  const result = {};
  for (const [key, value] of Object.entries(obj || {})) {
    if (!set.has(key) && !(extraExcludeSet && extraExcludeSet.has(key))) {
      result[key] = value;
    }
  }
  return result;
}

function switchGroup(group) {
  if (currentGroup?.group_id !== group.group_id) {
    saveCurrentGroupSilent(currentGroup);
  }
  renderGroupForm(group);
}

/* -- API helpers -- */
async function loadBootstrapData() {
  const data = await api.safeGet("settings/bootstrap");
  bootstrapData = data;
  allGroups = normalizeGroups(data.groups || []);
}

async function loadGroupConfig(groupId) {
  const target = String(groupId || "").trim();
  if (!target) return;

  const data = await api.safeGet("settings/group", { group_id: target });
  renderGroupForm(data);
}

async function saveGroupConfig() {
  if (!currentGroup) {
    showToast("请先选择一个群配置", "error");
    return;
  }

  const formData = collectFormData(els.groupForm);
  const schema = bootstrapData?.schema || {};
  const globalKeys = new Set(Object.keys(schema.global || {}));

  let requestBody;

  if (currentGroup.is_default_group) {
    // Split form data into global_config and config based on schema
    const globalConfig = {};
    const config = {};
    for (const [key, value] of Object.entries(formData)) {
      if (globalKeys.has(key)) {
        globalConfig[key] = value;
      } else {
        config[key] = value;
      }
    }
    requestBody = {
      group_id: currentGroup.group_id,
      config: config,
      global_config: globalConfig,
    };
  } else {
    // Per-group: send all form fields as config (they are per-group fields from schema.default)
    requestBody = {
      group_id: currentGroup.group_id,
      config: formData,
    };
  }

  const data = await api.safePost("settings/group", requestBody);

  // Update local data without re-fetching
  Object.assign(currentGroup, data);
  const idx = allGroups.findIndex((g) => g.group_id === currentGroup.group_id);
  if (idx !== -1) {
    allGroups[idx] = { ...allGroups[idx], ...data };
  }

  renderGroupCards();
  showToast("配置已保存");
}

async function saveCurrentGroupSilent(group) {
  if (!group || !els.groupForm.querySelector("[data-path]")) return;
  try {
    const formData = collectFormData(els.groupForm);
    const schema = bootstrapData?.schema || {};
    const globalKeys = new Set(Object.keys(schema.global || {}));

    if (group.is_default_group) {
      const globalConfig = {};
      const config = {};
      for (const [key, value] of Object.entries(formData)) {
        if (globalKeys.has(key)) {
          globalConfig[key] = value;
        } else {
          config[key] = value;
        }
      }
      await api.safePost("settings/group", {
        group_id: group.group_id,
        config: config,
        global_config: globalConfig,
      });
    } else {
      await api.safePost("settings/group", {
        group_id: group.group_id,
        config: formData,
      });
    }
  } catch {}
}

async function deleteGroupConfig() {
  if (!currentGroup || currentGroup.is_default_group) {
    showToast("不能删除默认全局配置", "error");
    return;
  }

  await api.safePost("settings/group/delete", {
    group_id: currentGroup.group_id,
  });

  // Switch to default group
  const defaultGroup = allGroups.find((g) => g.is_default_group);
  if (defaultGroup) {
    await loadGroupConfig(defaultGroup.group_id);
  }

  await loadBootstrapData();
  renderGroupCards(true);
  showToast("群配置已删除");
}

/* -- add-group modal -- */
let modalAvailableGroups = [];
let modalSelectedGroup = null;

function openAddGroupModal() {
  modalSelectedGroup = null;
  els.addGroupModal.style.display = "";
  els.modalSearchInput.value = "";
  els.modalConfirmBtn.disabled = true;
  loadAvailableGroups();
  els.modalSearchInput.focus();
}

function closeAddGroupModal() {
  els.addGroupModal.style.display = "none";
  modalSelectedGroup = null;
}

async function loadAvailableGroups() {
  els.modalGroupList.innerHTML = '<div class="modal-loading">加载中...</div>';
  try {
    const data = await api.safeGet("settings/available-groups");
    modalAvailableGroups = Array.isArray(data) ? data : [];
    renderModalGroups();
  } catch (error) {
    els.modalGroupList.innerHTML = '<div class="modal-empty">加载失败: ' + (error.message || "未知错误") + '</div>';
  }
}

function renderModalGroups() {
  const keyword = String(els.modalSearchInput.value || "")
    .trim()
    .toLowerCase();

  let filtered = modalAvailableGroups;
  if (keyword) {
    filtered = modalAvailableGroups.filter((g) => {
      const gid = String(g.group_id || "").toLowerCase();
      const gname = String(g.group_name || "").toLowerCase();
      return gid.includes(keyword) || gname.includes(keyword);
    });
  }

  if (!filtered.length) {
    els.modalGroupList.innerHTML = '<div class="modal-empty">' + (keyword ? "没有匹配的群" : "所有群都已有配置") + "</div>";
    return;
  }

  els.modalGroupList.innerHTML = "";

  filtered.forEach((group) => {
    const item = document.createElement("div");
    item.className = "modal-group-item";
    item.dataset.groupId = group.group_id;
    if (modalSelectedGroup && modalSelectedGroup.group_id === group.group_id) {
      item.classList.add("is-selected");
    }

    const avatar = document.createElement("img");
    avatar.className = "modal-group-item-avatar";
    avatar.src = group.avatar || "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><rect width='96' height='96' rx='24' fill='%23e8c49a'/><text x='48' y='56' text-anchor='middle' font-size='34' fill='%23824f1f' font-family='Arial'>G</text></svg>";
    avatar.alt = group.group_name;
    avatar.loading = "lazy";
    item.appendChild(avatar);

    const info = document.createElement("div");
    info.className = "modal-group-item-info";

    const name = document.createElement("div");
    name.className = "modal-group-item-name";
    name.textContent = group.group_name || "群 " + group.group_id;
    info.appendChild(name);

    const idLine = document.createElement("div");
    idLine.className = "modal-group-item-id";
    idLine.textContent = group.group_id + (group.member_count ? " | " + group.member_count + " 人" : "");
    info.appendChild(idLine);

    item.appendChild(info);

    const check = document.createElement("span");
    check.className = "modal-group-check";
    const checkImg = document.createElement("img");
    checkImg.src = CHECK_ICON;
    checkImg.alt = "selected";
    checkImg.width = 24;
    checkImg.height = 24;
    check.appendChild(checkImg);
    item.appendChild(check);

    item.addEventListener("click", () => {
      if (modalSelectedGroup && modalSelectedGroup.group_id === group.group_id) {
        modalSelectedGroup = null;
        els.modalConfirmBtn.disabled = true;
      } else {
        modalSelectedGroup = group;
        els.modalConfirmBtn.disabled = false;
      }
      els.modalGroupList.querySelectorAll(".modal-group-item").forEach((el) => {
        el.classList.toggle("is-selected", el.dataset.groupId === (modalSelectedGroup && modalSelectedGroup.group_id));
      });
    });

    els.modalGroupList.appendChild(item);
  });
}

async function confirmAddGroup() {
  if (!modalSelectedGroup) return;
  const group = modalSelectedGroup;
  const groupId = group.group_id;
  closeAddGroupModal();

  try {
    const defaultGroup = allGroups.find((g) => g.is_default_group);
    const newConfig = defaultGroup?.config ? { ...defaultGroup.config } : {};

    await api.safePost("settings/group", {
      group_id: groupId,
      config: newConfig,
    });

    await loadBootstrapData();
    renderGroupCards(true);

    const newGroup = allGroups.find((g) => g.group_id === groupId);
    if (newGroup) {
      renderGroupForm(newGroup);
    }

    showToast("群 " + group.group_name + " 配置已添加");
  } catch (error) {
    showToast(error.message || "添加群配置失败", "error");
  }
}

/* -- delete confirm modal -- */
function openDeleteConfirmModal() {
  if (!currentGroup || currentGroup.is_default_group) {
    showToast("不能删除默认全局配置", "error");
    return;
  }
  const info = currentGroup.group_info || {};
  const displayName = info.group_name || currentGroup.group_name || currentGroup.group_id;
  els.deleteConfirmBody.textContent = '确定要删除 "' + displayName + '"（' + currentGroup.group_id + '）的配置吗？此操作不可撤销。';
  els.deleteConfirmModal.style.display = "";
}

function closeDeleteConfirmModal() {
  els.deleteConfirmModal.style.display = "none";
}

/* -- events -- */
function bindEvents() {
  els.toggleThemeBtn.addEventListener("click", () => cycleThemePreference());

  els.addGroupBtn.addEventListener("click", () => openAddGroupModal());

  els.modalCloseBtn.addEventListener("click", () => closeAddGroupModal());

  els.addGroupModal.addEventListener("click", (e) => {
    if (e.target === els.addGroupModal) closeAddGroupModal();
  });

  els.modalSearchInput.addEventListener("input", () => renderModalGroups());

  els.modalConfirmBtn.addEventListener("click", () => confirmAddGroup());

  els.saveGroupBtn.addEventListener("click", async () => {
    try {
      await saveGroupConfig();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.deleteGroupBtn.addEventListener("click", () => openDeleteConfirmModal());

  els.deleteConfirmCloseBtn.addEventListener("click", () => closeDeleteConfirmModal());

  els.deleteConfirmCancelBtn.addEventListener("click", () => closeDeleteConfirmModal());

  els.deleteConfirmModal.addEventListener("click", (e) => {
    if (e.target === els.deleteConfirmModal) closeDeleteConfirmModal();
  });

  els.deleteConfirmOkBtn.addEventListener("click", async () => {
    closeDeleteConfirmModal();
    try {
      await deleteGroupConfig();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.groupSearchInput.addEventListener("input", () => renderGroupCards());
}

/* -- init -- */
async function init() {
  bindSystemTheme();
  updateThemeButton();
  applyThemeMode(resolveThemeMode(null));

  if (!bridge) return;

  try {
    api = createApi(bridge);
  } catch {
    return;
  }

  try {
    if (typeof bridge.ready === "function") {
      const context = await Promise.race([
        bridge.ready(),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Bridge ready timeout")), 5000)
        ),
      ]);
      syncThemeFromContext(context);
    }

    if (typeof bridge.onContext === "function") {
      detachContextHandler = bridge.onContext((context) => {
        syncThemeFromContext(context);
      });
    } else {
      syncThemeFromContext(bridge.getContext?.());
    }

    bindEvents();
    await loadBootstrapData();
    renderGroupCards();

    // Auto-select default group
    const defaultGroup = allGroups.find((g) => g.is_default_group);
    if (defaultGroup) {
      await loadGroupConfig(defaultGroup.group_id);
    }
  } catch (error) {
    const message = error?.message || "页面初始化失败";
    showToast(message, "error");
  }
}

window.addEventListener("beforeunload", () => {
  detachContextHandler?.();
  detachSystemThemeHandler?.();
});

init();
