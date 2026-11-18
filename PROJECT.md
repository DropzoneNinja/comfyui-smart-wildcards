# PROJECT.md --- ComfyUI Smart Wildcard Node

## 1. Project overview

Build a custom ComfyUI node that provides an interactive, table-based
interface for managing and combining wildcard text files from:

``` text
/basedir/wildcards
```

The node should make it easy to select one or more wildcard files,
optionally choose a specific entry from each file, and generate a prompt
fragment from those selections.

The node is intended to be a more capable, visual alternative to
manually typing wildcard references into a prompt. It should support
both deterministic selection and random selection, while allowing a
manually selected entry to override random selection for an individual
file.

**Working name:** Smart Wildcards

## 2. Goals

-   Discover and display wildcard `.txt` files beneath
    `/basedir/wildcards`.
-   Display one wildcard file per table row.
-   Treat subdirectories as visual section headers, not as selectable
    wildcard files.
-   Allow individual wildcard files to be enabled or disabled.
-   Allow a specific line/entry to be selected from each file.
-   Provide a global random mode.
-   In random mode, randomly choose an entry from each enabled file
    unless that file has a manually selected entry.
-   In non-random mode, use the selected entry for each enabled file,
    defaulting to the first non-empty entry.
-   Allow the user to drag and drop file rows to define a custom prompt
    ordering, and persist that ordering in the workflow.
-   Allow new wildcard files to be created from the node UI.
-   Produce a single prompt string containing the selected text from all
    enabled files.
-   Persist UI selections correctly when the workflow is saved and
    reopened.
-   Handle missing, empty, unreadable, or changed files gracefully.

## 3. ComfyUI integration and implementation approach

Implement this as a standard ComfyUI custom node package, including:

-   Python node implementation and registration.
-   A JavaScript frontend extension for the interactive table UI.
-   Any supporting CSS/JavaScript files required by the extension.
-   A clear installation and directory structure.
-   A README with installation, usage, and troubleshooting instructions.

Use ComfyUI's supported custom-node and frontend-extension APIs for the
installed ComfyUI version. Do not modify ComfyUI core files.

The Python side is authoritative for reading wildcard files and
generating output. The frontend should request file and entry
information through custom API routes registered by the extension. Do
not rely on the browser being able to access the server filesystem
directly.

The implementation must work in a Docker deployment where
`/basedir/wildcards` is the path visible to the ComfyUI process. Do not
silently substitute a different wildcard directory. If the directory is
missing or inaccessible, show a useful error in the node UI and return a
clear execution error or safe, documented output.

Before implementation, inspect the target ComfyUI version and current
custom-node conventions. Prefer maintained ComfyUI APIs over
private/internal APIs where possible.

## 4. Node user interface

### 4.1 Overall layout

The node should have:

1.  A header/action area at the top.
2.  A table containing wildcard files and section dividers.
3.  A generated prompt output.

The UI should be compact enough to use in a normal ComfyUI workflow, but
the table must remain readable when many wildcard files are present.

### 4.2 Header controls

At the top of the node, provide:

-   **Add File** button.
-   **Random** toggle/button.

#### Add File

Clicking **Add File** should open a small input dialog or inline input.

Behaviour:

1.  The user enters a filename.
2.  The filename is interpreted relative to `/basedir/wildcards`.
3.  If the user enters `lighting`, create `lighting.txt`.
4.  If the user enters `lighting.txt`, create `lighting.txt`.
5.  Do not append `.txt` twice.
6.  Reject empty names, path traversal (`../`), absolute paths, and
    unsupported extensions.
7.  Initially, creation is at the wildcard root. The UI may optionally
    support choosing a subdirectory later, but this is not required for
    the first release.
8.  If the file already exists, do not overwrite it. Show a clear
    message and leave the existing file untouched.
9.  A newly created file should appear in the table immediately and be
    **disabled by default**. It must not alter the generated prompt until
    the user explicitly enables it.
10. The file should be created with UTF-8 encoding and be ready for the
    user to edit/populate externally in a text editor.

The Add File operation must be performed server-side. Validate and
normalise the path on the server, and ensure the resolved path remains
inside `/basedir/wildcards`.

**Important:** Creating a file does not necessarily mean it has useful
entries. An empty file should be shown with an appropriate empty-state
indication and should not crash prompt generation.

#### Random toggle

Provide a clearly visible global Random toggle.

-   **Off:** Use the manually selected entry for each enabled file. If
    no entry has been manually selected, use the first non-empty entry.
-   **On:** Randomly select an entry for each enabled file, except where
    that file has a manually selected entry. A manually selected entry
    always takes precedence over random selection.
-   The toggle state must be saved with the workflow.
-   Random selection should occur at node execution time, not merely
    when the UI is rendered.
-   A new execution should be able to produce a new random combination.
-   Random selection must be deterministic from a ComfyUI seed value.
    Add an exposed seed input/control compatible with ComfyUI execution.
    The same seed and same wildcard file contents must produce the same
    selected entries. Changing the seed must be able to produce a new
    combination.
-   Recompute the selection during every node execution; do not freeze a
    random result in frontend state. With a fixed seed, repeated executions
    remain reproducible. A changed seed produces a different deterministic
    selection.

### 4.3 Table layout

Display one row per wildcard file.

Suggested columns:

  -----------------------------------------------------------------------
  Column                              Purpose
  ----------------------------------- -----------------------------------
  Enabled                             Toggle to include/exclude this file

  Wildcard file                       Relative filename, including
                                      subdirectory where applicable

  Selected entry                      Button/control showing the selected
                                      entry or a placeholder

  Status                              Optional compact status, such as
                                      entry count or empty/missing
  -----------------------------------------------------------------------

The Enabled control should be at the left of each file row. Include a
 drag handle or equivalent affordance so the user can drag rows into a
 custom order.

Each file row must show the filename clearly. For files in
subdirectories, show a relative path or otherwise make the parent
section clear.

The selected-entry control should open a dropdown, popover, or small
secondary window containing the entries in that file. The user must be
able to select an entry. The currently selected entry should be visible
in the row, truncated if necessary, with the full value available on
hover or in the selection UI.

The entry picker should:

-   Show entries in their original file order.
-   Make it possible to distinguish the first/default entry from other
    entries.
-   Handle long entries without making the table excessively wide.
-   Clearly indicate the selected entry.
-   Provide a way to return to automatic/default selection. This is
    important because a manually selected entry overrides random mode.
-   Refresh its entries if the file contents have changed.
-   Avoid treating blank lines as selectable entries.

For a large wildcard file, the picker should remain usable. Consider a
searchable list or scrollable popover rather than rendering an extremely
tall dropdown.

### 4.4 Directory section markers

Directories under `/basedir/wildcards` should be displayed as section
dividers.

Example directory structure:

``` text
/basedir/wildcards/
    lighting.txt
    camera.txt
    people/
        age.txt
        hair.txt
    clothing/
        style.txt
        colour.txt
```

Suggested table presentation:

``` text
[section: Root]
[✓] lighting.txt       [Choose entry...]
[✓] camera.txt         [Choose entry...]

[−] People
[✓] age.txt            [Choose entry...]
[✓] hair.txt           [Choose entry...]

[−] Clothing
[✓] style.txt          [Choose entry...]
[✓] colour.txt         [Choose entry...]
```

Requirements:

-   A directory is a section divider, not a selectable wildcard itself.
-   Each section divider has a collapse/expand control.
-   Collapsing a section hides its file rows without changing their
    enabled states or selected entries.
-   Expanding restores the rows and their state.
-   The root-level files should be displayed in a root section (the root
    section may be non-collapsible if that is simpler, but consistency
    is preferred).
-   Support nested directories. Display them in a clear hierarchy, or
    flatten them with a readable relative path if nested visual sections
    become too complex.
-   Use alphabetical, case-insensitive order as the initial order when a
    file is first discovered. Thereafter, the user-defined drag-and-drop
    order is authoritative and must be preserved across refreshes and
    workflow save/reload.
-   New files should be inserted into a predictable position (for example,
    at the end of their section) and remain disabled until enabled by the
    user. Do not reset existing custom order during a directory refresh.
-   Empty directories may be omitted unless there is a clear reason to
    show them.

A directory scan should not follow symlinks outside the wildcard root.
Ignore hidden/system files unless explicitly required.

### 4.5 Row enable/disable behaviour

Each wildcard file row has its own enabled toggle.

-   Enabled files contribute one selected entry to the generated prompt.
-   Disabled files do not contribute text.
-   Disabling a row must not clear its selected entry.
-   Re-enabling a row restores its previous selection.
-   Row enablement must persist with the workflow.
-   An empty file should be visibly marked and should not contribute
    text.

### 4.6 Selected-entry behaviour

Each file has a selection state with at least these logical values:

-   `auto` --- no manual entry selected.
-   `entry` --- a specific entry is manually selected.

The UI may present this as a dropdown with an `Automatic / Default`
option followed by the file's entries.

Selection rules:

  Random mode   File selection   Result
  ------------- ---------------- ------------------------
  Off           Auto             First non-empty entry
  Off           Specific entry   Specific entry
  On            Auto             Random non-empty entry
  On            Specific entry   Specific entry

This precedence is fundamental: **a specific manually selected entry
must never be replaced by random selection**, even when global Random
mode is enabled.

When the user chooses Automatic / Default, the file becomes eligible for
random selection when Random mode is on.

## 5. Prompt generation

The node should output one combined string made from the selected
entries of all enabled wildcard files.

Recommended initial behaviour:

-   Include one selected entry per enabled file.
-   Preserve the table's displayed order.
-   Join entries using `,` (comma followed by a space).
-   Skip disabled files.
-   Skip empty files and blank entries.
-   Do not add the filename itself to the prompt.
-   Do not add extra punctuation around individual entries.
-   Trim leading/trailing whitespace from each selected entry, while
    preserving meaningful internal whitespace.

Example:

``` text
A person with long hair, cinematic lighting, portrait photography, wearing a leather jacket
```

The exact separator should be configurable only if that can be done
without making the first version unnecessarily complicated. For the
first release, use comma-space.

The node should expose a standard ComfyUI `STRING` output named `prompt`
(or `text`) so it can connect to normal text/prompt nodes.

The node should also expose a useful execution preview/status if
supported by ComfyUI, but the output string remains the authoritative
result.

## 6. File format and parsing rules

For the first release:

-   Files are UTF-8 text files with a `.txt` extension.
-   Each non-empty line represents one selectable entry.
-   Preserve the order of entries.
-   Ignore blank lines.
-   Strip a UTF-8 byte-order mark if present.
-   Handle Windows (`CRLF`) and Unix (`LF`) line endings.
-   Do not interpret comment lines specially unless explicitly decided
    later.
-   Do not recursively expand wildcard syntax contained inside an entry
    in the first release. Entries are plain text values.

If a file contains duplicate lines, keep them. This preserves the file
as authored and means duplicates may have their natural weighting in
random selection.

If a file cannot be read, report the filename and error clearly. One
unreadable file should not cause the entire UI to become unusable.
Define whether execution should skip the file with a warning or fail;
the recommended initial behaviour is to skip that file and report a
warning in the node status.

## 7. State persistence and workflow behaviour

The workflow must preserve the user's node configuration when saved and
reopened.

Persist at least:

-   Global Random enabled/disabled state.
-   Each file's enabled/disabled state.
-   The custom ordering of file rows (including relative placement within
    directory sections).
-   The seed value or connected seed input configuration.
-   Each file's selection mode (`auto` or a specific entry).
-   The selected entry value or a robust reference to it.
-   Section collapse/expand state, if practical.
-   Any additional UI settings required to restore the node.

Do not rely exclusively on transient browser state.

### Handling changed files

The wildcard files may be edited outside ComfyUI while a workflow is
open.

When the UI refreshes or the node is reloaded:

-   Re-read the file list from the server.
-   Reconcile saved node state with the current files.
-   Preserve settings for files that still exist.
-   Mark files that no longer exist as missing rather than silently
    applying their settings to another file.
-   If a selected entry no longer exists in its file, reset that file to
    `auto` and show a non-blocking notice.
-   Newly discovered files should appear disabled by default.
-   Preserve custom row ordering for files that still exist; place newly
    discovered files at the end of their appropriate section until the
    user reorders them.
-   Do not silently discard user configuration.

The node must also work when the workflow is opened on another ComfyUI
instance where the wildcard directory differs. Explain this limitation
in the README. The file list is server-side and the workflow should
reconcile against the files available on the current server.

## 8. Backend API and security

Implement narrowly scoped custom API endpoints for the frontend,
following ComfyUI's supported server route registration patterns.

Required capabilities:

1.  List wildcard files and directories.
2.  Read the entries in a specific wildcard file.
3.  Create a new wildcard file.
4.  Optionally refresh/rescan the wildcard directory.

Possible endpoint design (adapt to current ComfyUI conventions):

``` text
GET  /smart_wildcards/files
GET  /smart_wildcards/entries?file=<relative-path>
POST /smart_wildcards/files
POST /smart_wildcards/refresh
```

These are illustrative routes, not a requirement to use these exact
names.

Security requirements:

-   Resolve all user-supplied paths against `/basedir/wildcards`.
-   Reject absolute paths and path traversal.
-   Verify the resolved path remains inside the wildcard root.
-   Do not follow symlinks that escape the root.
-   Restrict file creation to `.txt`.
-   Do not overwrite existing files.
-   Return structured JSON errors.
-   Never expose arbitrary filesystem browsing or file-reading
    functionality.
-   Do not accept arbitrary server paths from the frontend.

## 9. Refresh and responsiveness

The frontend should not rescan the directory on every minor UI
interaction.

-   Scan on node initialisation.
-   Provide a refresh action if practical (this can be a small
    icon/button).
-   Refresh after a file is created.
-   Fetch a file's entries when its entry picker is opened, or cache
    them with a sensible refresh strategy.
-   Avoid repeated requests while a picker is open.
-   Show a loading state while files or entries are being fetched.
-   Show useful error messages if the API is unavailable.

The UI should remain responsive with a large number of files and
entries.

## 10. Defaults

Unless changed by answers to the questions in section 12, use these
defaults:

  -----------------------------------------------------------------------
  Setting                             Default
  ----------------------------------- -----------------------------------
  Wildcard root                       `/basedir/wildcards`

  File extension                      `.txt`

  New file location                   Wildcard root

  New files                           Disabled

  Existing files on first discovery   Disabled

  Random mode                         Off

  Per-file selection                  Automatic

  Automatic selection with random off First non-empty entry

  Manual selection with random on     Manual entry wins

  Empty lines                         Ignored

  Prompt separator                    `, `

  Initial file ordering               Alphabetical, case-insensitive

  Ongoing file ordering                User-defined drag-and-drop order

  Directory ordering                  Alphabetical, case-insensitive

  Duplicate entries                   Preserved

  File removed after configuration    Mark missing; do not silently
                                      reassign

  Unreadable file at execution        Skip with warning
  -----------------------------------------------------------------------

## 11. Acceptance criteria

The implementation is complete when all of the following work:

1.  The node appears in a sensible ComfyUI category and can be added to
    a workflow.
2.  The node scans `/basedir/wildcards` and displays all supported
    `.txt` files.
3.  Files in subdirectories are displayed under collapsible section
    dividers.
4.  Each file has an independent enabled/disabled toggle.
5.  The Add File action creates a new root-level `.txt` file and
    refreshes the table.
6.  Entering a filename with or without `.txt` creates the expected
    filename.
7.  Existing files cannot accidentally be overwritten.
8.  The entry picker displays the non-empty lines from the selected
    file.
9.  A specific entry can be selected and is displayed in the table row.
10. Returning a file to Automatic clears its manual override.
11. With Random off, each enabled file contributes its selected entry,
    or its first non-empty entry when set to Automatic.
12. With Random on, each enabled file set to Automatic contributes a
    seed-determined random entry.
13. With Random on, a manually selected entry is used unchanged.
14. Disabled files never contribute to the output.
15. Empty files and blank lines do not cause errors.
16. The generated output is a single string and connects to standard
    ComfyUI text inputs.
17. Random selection occurs during every execution, not just when the
    node UI loads, and is reproducible for a given seed and file contents.
18. Changing the seed can change the selected entries.
19. Drag-and-drop reordering changes prompt output order and survives
    workflow save/reload and directory refresh.
20. Workflow save/reload preserves Random mode, seed configuration,
    enabled states, manual selections, and custom row ordering.
21. File changes, missing files, and invalid paths are handled safely
    and visibly.
22. Newly created and newly discovered files are disabled by default.
23. The node works in the Docker environment with `/basedir/wildcards`
    mounted and accessible to ComfyUI.
24. No ComfyUI core files need to be modified.

## 12. Confirmed product decisions

The following decisions have been confirmed and are requirements, not open
questions:

1. **New files are disabled by default.** Newly discovered files should
   also be added disabled so they cannot unexpectedly change an existing
   prompt. The user must explicitly enable them.
2. **Random selection uses a seed.** Expose a seed input/control and use
   deterministic random selection. The same seed and same file contents
   must yield the same result. A changed seed should be capable of
   producing a different result.
3. **Wildcard contents are edited externally.** The node creates blank
   files and reads their contents, but does not provide an in-node text
   editor. Users edit files with their normal text editor or other tools.
4. **Custom ordering is supported in the first release.** Users can drag
   and drop file rows to control the order in which their selected text
   appears in the generated prompt. Persist the order in the workflow.
   Alphabetical order is only the initial order for files not yet assigned
   a saved position. Newly discovered files should be appended to the end
   of their section until manually moved.
5. **Random selection happens at node execution.** Resolve random entries
   in the Python execution function, not in the frontend. Re-evaluate on
   every execution while retaining deterministic results for an unchanged
   seed and unchanged file contents.

The remaining implementation choices are intentionally left to Claude:

- Support arbitrary nested directory depth, using nested collapsible
  sections or an indented hierarchy.
- Scan on node initialisation and after Add File, with a manual Refresh
  action; do not poll the filesystem continuously.
- Skip empty or unreadable files, show row-level status, and continue
  processing other files with a warning.
- Preserve the user's custom file order as the output order.

## 13. Suggested implementation milestones

1.  **Inspect and scaffold**
    -   Inspect the installed ComfyUI version and extension APIs.
    -   Create the custom-node package structure.
    -   Register a minimal node with a string output.
2.  **Backend discovery**
    -   Implement safe wildcard directory scanning.
    -   Return files, directories, relative paths, and basic file
        metadata.
    -   Implement entry-reading and file-creation endpoints.
3.  **Frontend table**
    -   Render section headers and file rows.
    -   Implement collapse/expand.
    -   Implement per-file enabled toggles.
    -   Implement Add File and Refresh.
4.  **Entry selection**
    -   Implement the entry picker.
    -   Persist manual selection and Automatic state.
    -   Reconcile state when files change.
5.  **Prompt execution**
    -   Implement deterministic/default selection.
    -   Implement seeded random selection and manual-selection precedence.
    -   Implement drag-and-drop ordering and workflow persistence.
    -   Produce the combined prompt string.
6.  **Persistence and validation**
    -   Test workflow save/reload.
    -   Test missing, empty, unreadable, and modified files.
    -   Test path traversal and symlink protections.
7.  **Documentation and packaging**
    -   Add README and installation instructions.
    -   Document the required `/basedir/wildcards` mount.
    -   Add examples and troubleshooting notes.

## 14. Guidance to Claude

Prioritise a reliable, usable first release over unnecessary features.

Before coding, inspect the actual ComfyUI installation and existing
custom-node conventions in the target environment. Do not assume a
particular frontend API version without checking it.

Keep the implementation modular:

-   Python backend for file discovery, validation, reading, creation,
    and prompt generation.
-   Frontend extension for the interactive table and user controls.
-   Clear state serialisation so ComfyUI workflows retain configuration.

Do not implement a generic file manager. The node should only manage the
narrowly defined wildcard operations described here.

Do not overwrite user wildcard files. Do not silently change saved
selections. Do not let a manually selected entry be overridden by random
mode.

At the end, provide: - The complete custom-node source. -
Installation/update instructions for the Docker setup. - A concise
explanation of how state is stored in the workflow. - A test checklist
demonstrating the acceptance criteria. - Any known limitations or
decisions that still require user input.
