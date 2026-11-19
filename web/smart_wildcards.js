import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { renderTable } from "./table.js";
import { closeEntryPicker } from "./entry_picker.js";

const NODE_CLASS = "SmartWildcards";

const cssUrl = new URL("./style.css", import.meta.url).href;
if (!document.querySelector(`link[href="${cssUrl}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = cssUrl;
  document.head.appendChild(link);
}

function createDefaultState() {
  return {
    randomEnabled: false,
    files: {},
    order: {},
    collapsed: {},
  };
}

function countFiles(nodes) {
  let total = 0;
  for (const entry of nodes || []) {
    if (entry.type === "file") total += 1;
    else total += countFiles(entry.children);
  }
  return total;
}

app.registerExtension({
  name: "SmartWildcards",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      initSmartWildcardsNode(this);
      return result;
    };

    const onRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      if (this._smartWildcards) closeEntryPicker();
      return onRemoved ? onRemoved.apply(this, arguments) : undefined;
    };
  },
});

function initSmartWildcardsNode(node) {
  const state = createDefaultState();
  const ctx = { node, state, tree: null };
  node._smartWildcards = ctx;

  const root = document.createElement("div");
  root.className = "sw-root";

  const header = document.createElement("div");
  header.className = "sw-header";

  const addBtn = document.createElement("button");
  addBtn.className = "sw-btn";
  addBtn.textContent = "+ Add File";
  header.appendChild(addBtn);

  const addInput = document.createElement("input");
  addInput.className = "sw-add-input";
  addInput.type = "text";
  addInput.placeholder = "filename.txt — Enter to create";
  addInput.style.display = "none";
  header.appendChild(addInput);

  const randomBtn = document.createElement("button");
  randomBtn.className = "sw-btn";
  randomBtn.textContent = "Random";
  randomBtn.title = "When on, Automatic files are randomly selected at execution time";
  header.appendChild(randomBtn);

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "sw-btn";
  refreshBtn.textContent = "⟳";
  refreshBtn.title = "Refresh file list";
  header.appendChild(refreshBtn);

  const spacer = document.createElement("span");
  spacer.className = "sw-header-spacer";
  header.appendChild(spacer);

  const status = document.createElement("span");
  status.className = "sw-status";
  header.appendChild(status);

  root.appendChild(header);

  const notice = document.createElement("div");
  notice.className = "sw-notice";
  notice.style.display = "none";
  root.appendChild(notice);

  const body = document.createElement("div");
  body.className = "sw-body";
  root.appendChild(body);

  let noticeTimer = null;
  function showNotice(text) {
    notice.textContent = text;
    notice.style.display = "block";
    if (noticeTimer) clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => {
      notice.style.display = "none";
    }, 6000);
  }

  function setStatus(text, isError) {
    status.textContent = text;
    status.classList.toggle("sw-error", !!isError);
  }

  function renderBody() {
    if (!ctx.tree) return;
    renderTable(body, ctx.tree, state, {
      onStateChanged: ({ rerender }) => {
        if (rerender) renderBody();
      },
      onNotice: showNotice,
    });
  }

  async function loadFiles({ refresh = false } = {}) {
    setStatus(refresh ? "Refreshing…" : "Loading…", false);
    try {
      const resp = await api.fetchApi(
        refresh ? "/smart_wildcards/refresh" : "/smart_wildcards/files",
        { method: refresh ? "POST" : "GET" }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data?.error?.message || `request failed (${resp.status})`);
      }
      ctx.tree = data;
      const count = countFiles(ctx.tree.tree);
      setStatus(`${count} file${count === 1 ? "" : "s"}`, false);
      renderBody();
    } catch (err) {
      setStatus(String(err.message || err), true);
    }
  }

  addBtn.onclick = () => {
    const show = addInput.style.display === "none";
    addInput.style.display = show ? "inline-block" : "none";
    if (show) {
      addInput.value = "";
      addInput.focus();
    }
  };

  addInput.addEventListener("keydown", async (e) => {
    if (e.key === "Escape") {
      addInput.style.display = "none";
      return;
    }
    if (e.key !== "Enter") return;

    const name = addInput.value.trim();
    if (!name) return;

    try {
      const resp = await api.fetchApi("/smart_wildcards/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const result = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(result?.error?.message || "failed to create file");
      }
      addInput.style.display = "none";
      await loadFiles();
    } catch (err) {
      showNotice(String(err.message || err));
    }
  });

  randomBtn.onclick = () => {
    state.randomEnabled = !state.randomEnabled;
    randomBtn.classList.toggle("sw-active", state.randomEnabled);
  };

  refreshBtn.onclick = () => loadFiles({ refresh: true });

  node.addDOMWidget("smart_wildcards_table", "SmartWildcardsTable", root, {
    serialize: false,
    getMinHeight: () => 220,
    getMaxHeight: () => 600,
  });

  loadFiles();
}
