import { getCachedEntries, getEntries, openEntryPicker } from "./entry_picker.js";

let dragState = null;

export function ensureFileState(state, relpath) {
  if (!state.files[relpath]) {
    state.files[relpath] = { enabled: false, mode: "auto", entry: null };
  }
  return state.files[relpath];
}

function applyOrder(names, orderList) {
  const known = orderList.filter((n) => names.includes(n));
  const rest = names
    .filter((n) => !orderList.includes(n))
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  return [...known, ...rest];
}

function basename(relpath) {
  const idx = relpath.lastIndexOf("/");
  return idx === -1 ? relpath : relpath.slice(idx + 1);
}

export function renderTable(container, treeResult, state, actions) {
  container.innerHTML = "";

  const errorsByPath = new Map((treeResult.errors || []).map((e) => [e.path, e.message]));

  if (!treeResult.tree || treeResult.tree.length === 0) {
    const empty = document.createElement("div");
    empty.className = "sw-empty-state";
    empty.textContent = (treeResult.errors && treeResult.errors.length)
      ? `Wildcard root unavailable: ${treeResult.errors[0].message}`
      : "No wildcard files found. Use “+ Add File” to create one.";
    container.appendChild(empty);
    return;
  }

  renderDirContents(container, ".", 0, treeResult.tree, state, actions, errorsByPath);
}

function renderDirContents(container, dirPath, depth, children, state, actions, errorsByPath) {
  const files = children.filter((c) => c.type === "file");
  const dirs = [...children.filter((c) => c.type === "dir")].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
  );

  const names = files.map((f) => f.name);
  const order = applyOrder(names, state.order[dirPath] || []);
  state.order[dirPath] = order;

  const byName = new Map(files.map((f) => [f.name, f]));
  for (const name of order) {
    const fileNode = byName.get(name);
    if (fileNode) {
      container.appendChild(renderFileRow(fileNode, depth, state, actions, errorsByPath));
    }
  }

  for (const dir of dirs) {
    container.appendChild(renderSection(dir, depth, state, actions, errorsByPath));
  }
}

function renderSection(dirNode, depth, state, actions, errorsByPath) {
  const wrapper = document.createElement("div");
  wrapper.className = "sw-section";
  wrapper.dataset.depth = String(depth);

  const collapsed = !!state.collapsed[dirNode.path];

  const header = document.createElement("div");
  header.className = "sw-section-header";

  const caret = document.createElement("span");
  caret.className = "sw-section-caret";
  caret.textContent = collapsed ? "▶" : "▼";
  header.appendChild(caret);

  const label = document.createElement("span");
  label.textContent = basename(dirNode.path);
  header.appendChild(label);

  header.onclick = () => {
    state.collapsed[dirNode.path] = !collapsed;
    actions.onStateChanged({ rerender: true });
  };
  wrapper.appendChild(header);

  if (!collapsed) {
    const body = document.createElement("div");
    renderDirContents(body, dirNode.path, depth + 1, dirNode.children, state, actions, errorsByPath);
    wrapper.appendChild(body);
  }

  return wrapper;
}

function renderFileRow(fileNode, depth, state, actions, errorsByPath) {
  const relpath = fileNode.path;
  const fstate = ensureFileState(state, relpath);
  const dirPath = relpath.includes("/") ? relpath.slice(0, relpath.lastIndexOf("/")) : ".";

  const row = document.createElement("div");
  row.className = "sw-row";
  row.dataset.depth = String(depth);
  row.dataset.relpath = relpath;
  row.dataset.dir = dirPath;
  row.draggable = true;

  const handle = document.createElement("span");
  handle.className = "sw-drag-handle";
  handle.textContent = "⋮⋮";
  row.appendChild(handle);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = fstate.enabled;
  checkbox.onchange = () => {
    fstate.enabled = checkbox.checked;
    actions.onStateChanged({ rerender: false });
  };
  row.appendChild(checkbox);

  const name = document.createElement("span");
  name.className = "sw-row-name" + (fileNode.status === "empty" ? " sw-empty-file" : "");
  name.textContent = fileNode.name;
  name.title = relpath;
  row.appendChild(name);

  const entryBtn = document.createElement("button");
  entryBtn.className = "sw-entry-btn" + (fstate.mode === "auto" ? " sw-auto" : "");
  entryBtn.textContent = entryButtonLabel(relpath, fstate, fileNode);
  entryBtn.title = fstate.mode === "entry" && fstate.entry !== null ? fstate.entry : "Automatic / Default";
  entryBtn.onclick = async (e) => {
    e.preventDefault();
    if (fileNode.status === "unreadable") {
      actions.onNotice(`${relpath}: ${errorsByPath.get(relpath) || "file is unreadable"}`);
      return;
    }
    entryBtn.disabled = true;
    try {
      const entries = await getEntries(relpath, fileNode.mtime);
      openEntryPicker({
        relpath,
        fileState: fstate,
        entries,
        anchorEl: entryBtn,
        onSelect: () => actions.onStateChanged({ rerender: true }),
        onNotice: actions.onNotice,
      });
    } catch (err) {
      actions.onNotice(String(err.message || err));
    } finally {
      entryBtn.disabled = false;
    }
  };
  row.appendChild(entryBtn);

  const status = document.createElement("span");
  status.className = "sw-row-status" + (fileNode.status === "unreadable" ? " sw-error" : "");
  if (fileNode.status === "unreadable") {
    status.textContent = "error";
    status.title = errorsByPath.get(relpath) || "unreadable";
  } else if (fileNode.status === "empty") {
    status.textContent = "empty";
  } else {
    status.textContent = `${fileNode.entryCount}`;
  }
  row.appendChild(status);

  wireDragAndDrop(row, dirPath, relpath, state, actions);

  return row;
}

function entryButtonLabel(relpath, fstate, fileNode) {
  if (fstate.mode === "entry" && fstate.entry !== null) {
    return fstate.entry;
  }
  const cached = getCachedEntries(relpath, fileNode.mtime);
  if (cached && cached.length > 0) {
    return `Automatic (${cached[0]})`;
  }
  return "Automatic / Default";
}

function wireDragAndDrop(row, dirPath, relpath, state, actions) {
  row.addEventListener("dragstart", (e) => {
    dragState = { relpath, dirPath };
    row.classList.add("sw-dragging");
    e.dataTransfer.setData("text/plain", relpath);
    e.dataTransfer.effectAllowed = "move";
  });

  row.addEventListener("dragend", () => {
    row.classList.remove("sw-dragging");
    dragState = null;
  });

  row.addEventListener("dragover", (e) => {
    if (!dragState || dragState.dirPath !== dirPath) return;
    e.preventDefault();
    row.classList.add("sw-drag-over");
  });

  row.addEventListener("dragleave", () => {
    row.classList.remove("sw-drag-over");
  });

  row.addEventListener("drop", (e) => {
    row.classList.remove("sw-drag-over");
    if (!dragState || dragState.dirPath !== dirPath || dragState.relpath === relpath) return;
    e.preventDefault();

    const order = state.order[dirPath] || [];
    const fromName = basename(dragState.relpath);
    const toName = basename(relpath);
    const fromIdx = order.indexOf(fromName);
    if (fromIdx === -1 || order.indexOf(toName) === -1) return;

    order.splice(fromIdx, 1);
    order.splice(order.indexOf(toName), 0, fromName);
    state.order[dirPath] = order;

    actions.onStateChanged({ rerender: true });
  });
}
