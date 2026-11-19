/**
 * JS-side state reconciliation against a freshly-scanned tree. See
 * DESIGN.md section 10 and PROJECT.md section 7 ("Handling changed files").
 */

export function flattenFileNodes(tree) {
  const map = new Map();
  for (const node of tree || []) {
    if (node.type === "file") map.set(node.path, node);
    else for (const [k, v] of flattenFileNodes(node.children)) map.set(k, v);
  }
  return map;
}

function flattenPaths(tree) {
  return new Set(flattenFileNodes(tree).keys());
}

/** Relpaths tracked in `files` that no longer appear in the live tree. */
export function recomputeMissing(files, tree) {
  const livePaths = flattenPaths(tree);
  return Object.keys(files || {}).filter((path) => !livePaths.has(path));
}

/**
 * One-time merge of a saved state blob (restored onto the hidden widget by
 * litegraph's node.configure() when a workflow is loaded) against a
 * freshly-scanned tree. Newly-discovered files default to disabled/auto.
 * `order` is carried over unchanged -- table.js's own per-directory order
 * merge already appends newly-discovered files at the end on render, and
 * drops entries for files that turn out to be missing (those render in
 * the dedicated "missing" section instead).
 */
export function reconcileState(saved, tree) {
  const livePaths = flattenPaths(tree);

  const files = { ...(saved.files || {}) };
  for (const path of livePaths) {
    if (!files[path]) {
      files[path] = { enabled: false, mode: "auto", entry: null };
    }
  }

  const collapsed = {};
  if (Array.isArray(saved.collapsed)) {
    for (const dirPath of saved.collapsed) collapsed[dirPath] = true;
  }

  return {
    randomEnabled: !!saved.randomEnabled,
    files,
    order: { ...(saved.order || {}) },
    collapsed,
  };
}
