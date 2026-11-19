import { api } from "../../scripts/api.js";

const entryCache = new Map(); // relpath -> { mtime, entries }
let activePopover = null;

export function getCachedEntries(relpath, mtime) {
  const cached = entryCache.get(relpath);
  if (cached && cached.mtime === mtime) return cached.entries;
  return null;
}

async function fetchEntries(relpath) {
  const resp = await api.fetchApi(`/smart_wildcards/entries?file=${encodeURIComponent(relpath)}`);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(body?.error?.message || `failed to load entries for ${relpath}`);
  }
  entryCache.set(relpath, { mtime: body.mtime, entries: body.entries });
  return body.entries;
}

export async function getEntries(relpath, knownMtime, { forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const cached = getCachedEntries(relpath, knownMtime);
    if (cached) return cached;
  }
  return fetchEntries(relpath);
}

export function closeEntryPicker() {
  if (!activePopover) return;
  activePopover.backdrop.remove();
  activePopover.popover.remove();
  document.removeEventListener("keydown", activePopover.onKeyDown);
  activePopover = null;
}

/**
 * Opens the entry picker popover anchored under `anchorEl`. Also reconciles
 * a stale manual selection: if fileState.mode is "entry" but that entry no
 * longer appears in the freshly-fetched `entries`, resets it to "auto" and
 * surfaces a notice (DESIGN.md section 10 / PROJECT.md section 7).
 */
export function openEntryPicker({ relpath, fileState, entries, anchorEl, onSelect, onNotice }) {
  if (fileState.mode === "entry" && fileState.entry !== null && !entries.includes(fileState.entry)) {
    fileState.mode = "auto";
    fileState.entry = null;
    if (onNotice) {
      onNotice(`${relpath}: selected entry no longer found, reset to Automatic`);
    }
  }

  closeEntryPicker();

  const backdrop = document.createElement("div");
  backdrop.className = "sw-popover-backdrop";

  const popover = document.createElement("div");
  popover.className = "sw-popover";

  const width = 220;
  const estHeight = 260;
  const rect = anchorEl.getBoundingClientRect();
  const left = Math.min(Math.max(4, rect.left), Math.max(4, window.innerWidth - width - 4));
  const top = rect.bottom + 4 + estHeight > window.innerHeight
    ? Math.max(4, rect.top - estHeight - 4)
    : rect.bottom + 4;
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;

  const search = document.createElement("input");
  search.className = "sw-popover-search";
  search.type = "text";
  search.placeholder = "Search entries…";
  popover.appendChild(search);

  const list = document.createElement("div");
  list.className = "sw-popover-list";
  popover.appendChild(list);

  function selectAuto() {
    fileState.mode = "auto";
    fileState.entry = null;
    closeEntryPicker();
    onSelect();
  }

  function selectEntry(entry) {
    fileState.mode = "entry";
    fileState.entry = entry;
    closeEntryPicker();
    onSelect();
  }

  function renderList(filterText) {
    list.innerHTML = "";

    const auto = document.createElement("div");
    auto.className = "sw-popover-item sw-auto-option";
    if (fileState.mode === "auto") auto.classList.add("sw-selected");
    auto.textContent = "Automatic / Default";
    auto.onclick = selectAuto;
    list.appendChild(auto);

    if (entries.length === 0) {
      const empty = document.createElement("div");
      empty.className = "sw-popover-empty";
      empty.textContent = "No entries in this file";
      list.appendChild(empty);
      return;
    }

    const needle = (filterText || "").toLowerCase();
    entries.forEach((entry, index) => {
      if (needle && !entry.toLowerCase().includes(needle)) return;
      const item = document.createElement("div");
      item.className = "sw-popover-item";
      if (index === 0) item.classList.add("sw-default-entry");
      if (fileState.mode === "entry" && fileState.entry === entry) item.classList.add("sw-selected");
      item.textContent = entry;
      item.title = entry;
      item.onclick = () => selectEntry(entry);
      list.appendChild(item);
    });
  }

  renderList("");
  search.addEventListener("input", () => renderList(search.value));

  backdrop.onclick = () => closeEntryPicker();
  popover.onclick = (e) => e.stopPropagation();

  const onKeyDown = (e) => {
    if (e.key === "Escape") closeEntryPicker();
  };
  document.addEventListener("keydown", onKeyDown);

  document.body.appendChild(backdrop);
  document.body.appendChild(popover);
  search.focus();

  activePopover = { backdrop, popover, onKeyDown };
}
