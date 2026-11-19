import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { renderTable } from "./table.js";
import { closeEntryPicker, getEntries } from "./entry_picker.js";
import { flattenFileNodes, recomputeMissing, reconcileState } from "./state_sync.js";

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
    missing: [],
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

function findStateWidget(node) {
  return (node.widgets || []).find((w) => w.name === "wildcards_state");
}

// Keeps the widget serialized (so its value round-trips with the workflow)
// while hiding it from view -- our DOM widget is the real UI.
function hideStateWidget(widget) {
  widget.computeSize = () => [0, -4];
  widget.type = "hidden";
  if (widget.inputEl) widget.inputEl.style.display = "none";
  if (widget.element) widget.element.style.display = "none";
}

function loadStateFromWidgetValue(raw) {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
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

    // configure() is how litegraph restores a saved workflow's widget
    // values onto an already-constructed node -- it runs AFTER
    // onNodeCreated, so this is the first point where the hidden state
    // widget's value actually reflects what was saved (not the INPUT_TYPES
    // default). The tree hasn't loaded yet at this point (loadFiles() is
    // async), so we just capture the raw blob here; the first successful
    // tree load in loadFiles() does the actual reconciliation against it.
    const onConfigure = nodeType.prototype.configure;
    nodeType.prototype.configure = function () {
      const result = onConfigure ? onConfigure.apply(this, arguments) : undefined;
      const ctx = this._smartWildcards;
      if (ctx) {
        const widget = findStateWidget(this);
        ctx.pendingRestoreRaw = widget ? loadStateFromWidgetValue(widget.value) : null;
        ctx.tryReconcile();
      }
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
  const ctx = { node, state, tree: null, reconciled: false, pendingRestoreRaw: null };
  node._smartWildcards = ctx;

  const stateWidget = findStateWidget(node);
  if (stateWidget) hideStateWidget(stateWidget);

  function persist() {
    if (!stateWidget) return;
    stateWidget.value = JSON.stringify({
      version: 1,
      randomEnabled: state.randomEnabled,
      files: state.files,
      order: state.order,
      collapsed: Object.keys(state.collapsed).filter((k) => state.collapsed[k]),
      missing: state.missing || [],
    });
  }

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
  randomBtn.classList.toggle("sw-active", state.randomEnabled);
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

  // One-time merge of a saved workflow's state against the tree, once both
  // are available (see the configure() override above and DESIGN.md 10).
  // Safe to call multiple times/orders -- only acts once.
  ctx.tryReconcile = function () {
    if (ctx.reconciled || !ctx.tree) return;
    ctx.reconciled = true;
    if (ctx.pendingRestoreRaw) {
      const merged = reconcileState(ctx.pendingRestoreRaw, ctx.tree.tree);
      state.randomEnabled = merged.randomEnabled;
      state.files = merged.files;
      state.order = merged.order;
      state.collapsed = merged.collapsed;
      randomBtn.classList.toggle("sw-active", state.randomEnabled);
    }
  };

  function renderBody() {
    if (!ctx.tree) return;
    renderTable(body, ctx.tree, state, {
      onStateChanged: ({ rerender }) => {
        persist();
        if (rerender) renderBody();
      },
      onNotice: showNotice,
    });
    persist();
  }

  // Re-checks every manually-selected file's entry against a fresh read,
  // on every load/refresh (not just workflow load) -- PROJECT.md section 7
  // ("refresh its entries if the file contents have changed"). Runs after
  // the table's first paint so it never blocks showing the file list.
  async function checkStaleManualEntries() {
    if (!ctx.tree) return;
    const fileNodes = flattenFileNodes(ctx.tree.tree);
    const candidates = Object.entries(state.files).filter(([relpath, fstate]) => {
      if (fstate.mode !== "entry" || fstate.entry === null) return false;
      const info = fileNodes.get(relpath);
      return info && (info.status === "ok" || info.status === "empty");
    });

    let changed = false;
    for (const [relpath, fstate] of candidates) {
      const info = fileNodes.get(relpath);
      try {
        const freshEntries = await getEntries(relpath, info.mtime);
        if (!freshEntries.includes(fstate.entry)) {
          fstate.mode = "auto";
          fstate.entry = null;
          changed = true;
          showNotice(`${relpath}: selected entry no longer found, reset to Automatic`);
        }
      } catch {
        // A hiccup fetching entries during this background check is not
        // fatal -- the entry picker will surface it next time it's opened.
      }
    }

    if (changed) {
      persist();
      renderBody();
    }
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
      ctx.tryReconcile();
      state.missing = recomputeMissing(state.files, ctx.tree.tree);

      const count = countFiles(ctx.tree.tree);
      setStatus(`${count} file${count === 1 ? "" : "s"}`, false);
      renderBody();
      checkStaleManualEntries();
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
    persist();
  };

  refreshBtn.onclick = () => loadFiles({ refresh: true });

  const tableWidget = node.addDOMWidget("smart_wildcards_table", "SmartWildcardsTable", root, {
    serialize: false,
    getMinHeight: () => 220,
  });

  // The DOM-widget layout system only honors height bounds (above), not
  // width -- a freshly created node is only as wide as its narrowest
  // widget (e.g. "control_after_generate"), which leaves the table cramped
  // until the user manually drags the node wider. Give it a sane default
  // size; the table's CSS (width/height: 100%) already fills whatever size
  // the node ends up at, including on later manual resizes.
  const MIN_NODE_WIDTH = 420;
  const MIN_NODE_HEIGHT = 320;
  node.setSize([Math.max(node.size[0], MIN_NODE_WIDTH), Math.max(node.size[1], MIN_NODE_HEIGHT)]);

  // The host positions this widget's DOM wrapper using
  // `(tableWidget.width ?? node.width) - margin*2` every frame. Once
  // something assigns tableWidget.width a concrete number, the node's
  // *live* width is never consulted again, even while manually dragging
  // the node's resize handle -- which is exactly the frozen-width bug
  // observed in production. Forcing it to the node's real width on every
  // resize keeps it from ever going stale, regardless of what pinned it.
  const syncTableWidgetWidth = () => {
    tableWidget.width = node.size[0];
  };
  syncTableWidgetWidth();

  const onResizeBeforeDebug = node.onResize;
  node.onResize = function () {
    const result = onResizeBeforeDebug ? onResizeBeforeDebug.apply(this, arguments) : undefined;
    syncTableWidgetWidth();
    return result;
  };

  // TEMPORARY DEBUG INSTRUMENTATION -- remove once the width-resize bug
  // is diagnosed. Logs whenever our element, its parent (the host's
  // DOM-widget wrapper), or the node's own size actually change, so we
  // can see from the console which of those does/doesn't track a
  // manual node resize -- without depending on devtools element-picking
  // (which ComfyUI's canvas contextmenu handler appears to block).
  (function installResizeDebug() {
    const tag = "[SmartWildcards DEBUG]";
    const describe = (label) => {
      const rootRect = root.getBoundingClientRect();
      const parent = root.parentElement;
      const parentRect = parent ? parent.getBoundingClientRect() : null;
      console.log(tag, label, {
        nodeSize: node.size ? [node.size[0], node.size[1]] : null,
        rootRect: [Math.round(rootRect.width), Math.round(rootRect.height)],
        parentTag: parent ? `${parent.tagName}.${parent.className}` : null,
        parentRect: parentRect ? [Math.round(parentRect.width), Math.round(parentRect.height)] : null,
        parentInlineStyle: parent ? parent.getAttribute("style") : null,
      });
    };

    describe("initial");

    if (typeof ResizeObserver !== "undefined") {
      const roRoot = new ResizeObserver(() => describe("ResizeObserver(root element)"));
      roRoot.observe(root);
      if (root.parentElement) {
        const roParent = new ResizeObserver(() => describe("ResizeObserver(parent wrapper)"));
        roParent.observe(root.parentElement);
      }
    } else {
      console.log(tag, "ResizeObserver unavailable in this browser");
    }

    const origOnResize = node.onResize;
    node.onResize = function (size) {
      console.log(tag, "node.onResize fired", size ? [size[0], size[1]] : null);
      const result = origOnResize ? origOnResize.apply(this, arguments) : undefined;
      describe("after node.onResize (tableWidget.width=" + tableWidget.width + ")");
      return result;
    };
  })();

  loadFiles();
}
