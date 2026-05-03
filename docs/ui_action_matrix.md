# UI Action Matrix

Last checked: 2026-05-03

This file lists launcher controls that trigger behavior and need stable object names for
tests, UI automation, accessibility review, and refactor safety. Static tests enforce that
every ID below exists in source and that newly created Qt button-like controls get an
object name near construction.

## Main Window

| Area | Object name | Control | Action | Current coverage |
| --- | --- | --- | --- | --- |
| Top actions | `addNodeButton` | button | Opens the create-node dialog. | Static inventory, startup smoke |
| Top actions | `startNodeButton` | button | Starts or stops the selected node container. | Static inventory, startup smoke |
| Top actions | `downloadDockerButton` | button | Opens Docker download flow. | Static inventory, startup smoke |
| Top actions | `openDappButton` | button | Opens the node dApp URL. | Static inventory, startup smoke |
| Top actions | `openExplorerButton` | button | Opens the node explorer URL. | Static inventory, startup smoke |
| Node info | `refreshNodeInfoButton` | button | Refreshes node metadata from Docker. | Static inventory, startup smoke |
| Node info | `copyAddrButton` | button | Copies node address. | Static inventory, startup smoke |
| Node info | `copyEthButton` | button | Copies ETH address. | Static inventory, startup smoke |
| Bottom actions | `renameNodeButton` | button | Opens rename-node dialog. | Static inventory, startup smoke |
| Bottom actions | `themeToggleButton` | button | Switches light or dark theme. | Static inventory, startup smoke |
| Bottom actions | `forceDebugCheckbox` | checkbox | Enables or disables debug logging. | Static inventory, startup smoke |
| Rename dialog | `renameNodeSaveButton` | button | Saves renamed node alias. | Static inventory |
| Rename dialog | `renameNodeCancelButton` | button | Closes rename dialog without saving. | Static inventory |
| Create-node dialog | `createNodeConfirmButton` | button | Creates a new node container entry. | Static inventory |
| Create-node dialog | `createNodeCancelButton` | button | Closes create-node dialog without creating. | Static inventory |

## Dialogs

| Area | Object name | Control | Action | Current coverage |
| --- | --- | --- | --- | --- |
| Authorized address row | `authorizedAddressCopyAddressButton` | button | Copies an authorized address. | Static inventory, dialog click |
| Authorized address row | `authorizedAddressCopyAliasButton` | button | Copies an authorized address alias. | Static inventory, dialog click |
| Authorized address row | `authorizedAddressDeleteButton` | button | Removes the address row. | Static inventory, dialog click |
| Authorized addresses | `authorizedAddressAddButton` | button | Adds a blank authorized address row. | Static inventory, dialog click |
| Authorized addresses | `authorizedAddressSaveButton` | button | Validates and saves authorized addresses. | Static inventory, dialog click |
| Authorized addresses | `authorizedAddressCloseButton` | button | Closes without saving. | Static inventory, dialog click |
| Docker check | `dockerCheckDownloadButton` | button | Opens Docker download page. | Static inventory, dialog click with browser mocked |
| Docker check | `dockerCheckRetryButton` | button | Retries Docker availability check. | Static inventory, dialog click |
| Docker check | `dockerCheckQuitButton` | button | Quits the Docker-check flow. | Static inventory, dialog click |
| Image pull | `imagePullCancelButton` | button | Cancels image-pull progress dialog. | Static inventory, dialog click |
| Config editor dialog | `configEditorSaveButton` | button | Saves edited config text. | Static inventory, dialog action ID |
| Config editor dialog | `configEditorCancelButton` | button | Closes config editor without saving. | Static inventory, dialog action ID |

## Extracted Widgets

| Area | Object name | Control | Action | Current coverage |
| --- | --- | --- | --- | --- |
| Host selector | `hostSelectorModeCheckbox` | checkbox | Enables multi-host mode. | Static inventory, widget click |
| Host selector | `hostSelectorRefreshButton` | button | Refreshes available hosts. | Static inventory, widget click |
| Config editor | `configEditorEditButton` | button | Opens config editor dialog. | Static inventory, widget click |
| Container list | `containerListToggleButton` | button | Emits start or stop request for selected container. | Static inventory, widget click |
| Container list | `containerListAddNodeButton` | button | Emits add-container request. | Static inventory, widget click |
| Log console | `logConsoleClearButton` | button | Clears visible log text. | Static inventory, widget click |
| Metrics | `metricsRefreshButton` | button | Emits metrics refresh request. | Static inventory, widget click |
| Node info | `nodeInfoCopyAddressButton` | button | Emits copy request for node address. | Static inventory, widget click |
| Node info | `nodeInfoCopyEthButton` | button | Emits copy request for ETH address. | Static inventory, widget click |
| Node info | `nodeInfoRefreshButton` | button | Emits node-info refresh request. | Static inventory, widget click |

## Coverage Rules

- Every new `QPushButton`, `QToolButton`, `QCheckBox`, and action-like standard dialog
  button must have a stable `objectName`.
- Every stable action ID must appear in this matrix and in source.
- Workflow tests should be added before changing behavior behind an action.
- Visual redesigns should preserve these IDs unless the action is intentionally removed
  and this matrix plus tests are updated in the same commit.
