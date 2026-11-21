(function () {
    "use strict";

    const rendererMap = {
        statusBadge: function (params) {
            const value = params.value;
            const isActive =
                value === 1 ||
                value === "1" ||
                value === true ||
                String(value).toLowerCase() === "active";

            const label = isActive ? "Active" : "Inactive";
            const badgeClass = isActive
                ? "bg-success-subtle text-success"
                : "bg-warning-subtle text-warning";

            return `<span class="badge ${badgeClass}">${label}</span>`;
        },


        visibilityBadge: function (params) {

    const value = params.value;

    const isHidden =
        value === 1 ||
        value === "1" ||
        value === true ||
        String(value).toLowerCase() === "hide";

    const label = isHidden ? "Hide" : "Show";

    const badgeClass = isHidden
        ? "bg-danger-subtle text-danger"
        : "bg-success-subtle text-success";

    return `<span class="badge ${badgeClass}">${label}</span>`;
},

        lifecycleBadge: function (params) {
            const value = params.value || "";
            let badgeClass = "bg-info-subtle text-info";
            let label = value || "Lead";

            if (value === "SO" || value === "SO Created") {
                badgeClass = "bg-warning-subtle text-warning";
                label = "SO Customer";
            } else if (value === "Paid Client") {
                badgeClass = "bg-success-subtle text-success";
                label = "Paid Client";
            }

            return `<span class="badge ${badgeClass}">${escapeHtml(label)}</span>`;
        },

        leadStatusBadge: function (params) {
            const row = params.data || {};
            const value = params.value || row.status_name || "";
            const tone = row.status_tone || "slate";

            return `<span class="lead-tone-chip lead-tone-${escapeHtml(tone)}">${escapeHtml(value)}</span>`;
        },

        leadToneBadge: function (params) {
            const value = params.value || "slate";

            return `<span class="lead-tone-chip lead-tone-${escapeHtml(value)}">${escapeHtml(value)}</span>`;
        },

        callStateBadge: function (params) {
            const value = params.value || "Fresh";

            const badgeClass = value === "Called - Status Pending"
                ? "bg-warning-subtle text-warning"
                : value === "Called"
                    ? "bg-success-subtle text-success"
                    : "bg-primary-subtle text-primary";

            return `<span class="badge ${badgeClass}">${escapeHtml(value)}</span>`;
        },

        leadFlagBadges: function (params) {
            const row = params.data || {};
            const badges = [];

            if (Number(row.has_contact || 0) === 1) {
                badges.push([
                    "Contact",
                    "bg-info-subtle text-info"
                ]);
            }

            if (Number(row.has_followup || 0) === 1) {
                badges.push([
                    "Follow-up",
                    "bg-primary-subtle text-primary"
                ]);
            }

            if (Number(row.has_free_trial || 0) === 1) {
                badges.push([
                    "Free Trial",
                    "bg-warning-subtle text-warning"
                ]);
            }

            if (Number(row.has_so || 0) === 1) {
                badges.push([
                    "SO",
                    "bg-danger-subtle text-danger"
                ]);
            }

            if (Number(row.is_paid_client || 0) === 1) {
                badges.push([
                    "Paid Client",
                    "bg-success-subtle text-success"
                ]);
            }

            if (Number(row.is_suspended || 0) === 1) {
                badges.push([
                    "Suspended",
                    "bg-secondary-subtle text-secondary"
                ]);
            }

            if (!badges.length) {
                badges.push([
                    row.working_status || "Fresh",
                    "bg-light text-muted"
                ]);
            }

            return `<div class="lead-flag-badges">${
                badges.map(function (badge) {
                    return `<span class="badge ${badge[1]}">${escapeHtml(badge[0])}</span>`;
                }).join("")
            }</div>`;
        },

        leadCallAction: function (params) {
            const row = params.data || {};
            const leadUuid = row.lead_uuid || "";

            const isPending =
                row.is_status_pending === true ||
                row.is_status_pending === "true" ||
                row.working_status === "Called - Status Pending";

            const disabled =
                !isPending &&
                (
                    row.can_call === false ||
                    row.can_call === "false"
                );

            const btnClass = isPending
                ? "btn-warning"
                : "btn-primary";

            const title = isPending
                ? "Open Status Pending"
                : "Click to Call";

            const icon = isPending
                ? "mdi-clipboard-text-clock-outline"
                : "mdi-phone-outgoing-outline";

            const label = isPending
                ? "Call Again"
                : "Call";

            return `
                <button
                    type="button"
                    class="btn btn-sm ${btnClass}"
                    data-lead-call="${escapeHtml(leadUuid)}"
                    data-status-pending="${isPending ? "1" : "0"}"
                    title="${title}"
                    ${disabled ? "disabled" : ""}
                >
                    <i class="mdi ${icon} me-1"></i>${label}
                </button>
            `;
        },

        button: function (params) {
            const column = params.colDef || {};
            const row = params.data || {};
            const button = document.createElement("button");

            const buttonText =
                column.buttonText ||
                params.value ||
                "";

            const buttonIcon =
                column.buttonIcon ||
                "";

            const classField =
                column.buttonClassField ||
                "";

            const classValue =
                column.buttonClassValue;

            const classMatch =
                column.buttonClassMatch ||
                "";

            const rowValue = classField
                ? row[classField]
                : undefined;

            const isClassMatch =
                Boolean(classField) &&
                (
                    rowValue === classValue ||
                    String(rowValue) === String(classValue)
                );

            const enabledField =
                column.buttonEnabledField ||
                "";

            const enabledValue = enabledField
                ? row[enabledField]
                : true;

            const isEnabled =
                !enabledField ||
                enabledValue === 1 ||
                enabledValue === "1" ||
                enabledValue === true ||
                String(enabledValue).toLowerCase() === "true";

            button.type = "button";

            button.className =
                isClassMatch && classMatch
                    ? classMatch
                    : (
                        column.buttonClass ||
                        "btn btn-sm btn-primary"
                    );

            button.title =
                column.buttonTitle ||
                buttonText;

            button.disabled = !isEnabled;

            button.setAttribute(
                "data-clientos-action",
                column.buttonAction || ""
            );

            if (buttonIcon) {
                const icon =
                    document.createElement("i");

                icon.className = buttonIcon;

                if (buttonText) {
                    icon.classList.add("me-1");
                }

                button.appendChild(icon);
            }

            if (buttonText) {
                const text =
                    document.createElement("span");

                text.textContent = buttonText;
                button.appendChild(text);
            }

            button.addEventListener(
                "click",
                function () {
                    document.dispatchEvent(
                        new CustomEvent(
                            "clientosGridButtonClick",
                            {
                                detail: {
                                    action:
                                        column.buttonAction ||
                                        "",
                                    field:
                                        column.field ||
                                        "",
                                    value:
                                        params.value,
                                    row:
                                        row,
                                    button:
                                        button
                                }
                            }
                        )
                    );
                }
            );

            return button;
        },

        settingsUserCount: function (params) {
            const row = params.data || {};
            const count = Number(
                params.value || 0
            );

            const idField =
                params.context &&
                params.context.rowIdField
                    ? params.context.rowIdField
                    : "id";

            const id =
                row[idField] ||
                "";

            const label =
                row.display_name ||
                row.designation_name ||
                row.role_name ||
                row.extension_number ||
                "Record";

            return `
                <button
                    type="button"
                    class="btn btn-sm btn-light settings-user-count-btn"
                    data-users-for="${escapeHtml(id)}"
                    data-users-label="${escapeHtml(label)}"
                >
                    <i class="mdi mdi-account-group-outline me-1"></i>${count}
                </button>
            `;
        },

        settingsMasterAction: function (params) {
            const row = params.data || {};

            const idField =
                params.context &&
                params.context.rowIdField
                    ? params.context.rowIdField
                    : "id";

            const id =
                row[idField] ||
                "";

            return `
                <div class="clientos-grid-actions">
                    <button
                        type="button"
                        class="btn btn-sm btn-primary"
                        title="Edit"
                        data-edit-master="${escapeHtml(id)}"
                    >
                        <i class="mdi mdi-pencil-outline"></i>
                    </button>
                </div>
            `;
        }
    };

    function escapeHtml(value) {
        return String(
            value === null ||
            value === undefined
                ? ""
                : value
        )
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function toComparable(value) {
        if (
            value === null ||
            value === undefined
        ) {
            return "";
        }

        return String(value);
    }

    function formatNumber(value) {
        return Number(
            value || 0
        ).toLocaleString("en-IN");
    }

    function getSelectedPageSize(
        pageSizeSelect,
        totalRows,
        fallbackPageSize
    ) {
        const selectedValue =
            pageSizeSelect
                ? pageSizeSelect.value
                : fallbackPageSize;

        if (selectedValue === "all") {
            return Math.max(
                totalRows,
                1
            );
        }

        return Number(
            selectedValue ||
            fallbackPageSize ||
            10
        );
    }

    function buildActionsRenderer(actions) {
        return function (params) {
            const idField =
                actions.idField ||
                "id";

            const id =
                params.data &&
                params.data[idField]
                    ? params.data[idField]
                    : "";

            const buttons = [];

            if (actions.viewUrl) {
                buttons.push(`
                    <a
                        href="${actions.viewUrl}${id}"
                        class="btn btn-sm btn-light"
                        title="View"
                    >
                        <i class="mdi mdi-eye-outline"></i>
                    </a>
                `);
            }

            if (actions.editUrl) {
                buttons.push(`
                    <a
                        href="${actions.editUrl}${id}"
                        class="btn btn-sm btn-primary"
                        title="Edit"
                    >
                        <i class="mdi mdi-pencil-outline"></i>
                    </a>
                `);
            }

            if (actions.deleteUrl) {
                buttons.push(`
                    <a
                        href="${actions.deleteUrl}${id}"
                        class="btn btn-sm btn-danger"
                        title="Delete"
                        onclick="return confirm('Delete record?')"
                    >
                        <i class="mdi mdi-trash-can-outline"></i>
                    </a>
                `);
            }

            return `
                <div class="clientos-grid-actions">
                    ${buttons.join("")}
                </div>
            `;
        };
    }

    function getSearchableFields(columns) {
        return (columns || [])
            .filter(function (column) {
                return (
                    column.field &&
                    !column.hide
                );
            })
            .map(function (column) {
                return column.field;
            });
    }

    function rowMatchesSearch(
        row,
        searchableFields,
        query
    ) {
        if (!query) {
            return true;
        }

        return searchableFields.some(
            function (field) {
                return toComparable(
                    row[field]
                )
                    .toLowerCase()
                    .includes(query);
            }
        );
    }

    function buildColumnDefs(
        columns,
        actions
    ) {
        const columnDefs =
            columns.map(function (column) {
                const columnDef =
                    Object.assign(
                        {},
                        column
                    );

                if (
                    column.renderer &&
                    rendererMap[column.renderer]
                ) {
                    columnDef.cellRenderer =
                        rendererMap[
                            column.renderer
                        ];

                    delete columnDef.renderer;
                }

                return columnDef;
            });

        if (
            actions.viewUrl ||
            actions.editUrl ||
            actions.deleteUrl
        ) {
            columnDefs.push({
                headerName: "Action",
                field: "action",
                minWidth: 140,
                sortable: false,
                filter: false,
                cellRenderer:
                    buildActionsRenderer(
                        actions
                    )
            });
        }

        return columnDefs;
    }

    function applyGridTheme(gridDiv) {
        const isDark =
            document.documentElement
                .getAttribute(
                    "data-bs-theme"
                ) === "dark";

        gridDiv.classList.toggle(
            "ag-theme-quartz",
            !isDark
        );

        gridDiv.classList.toggle(
            "ag-theme-quartz-dark",
            isDark
        );
    }

    function createGrid(wrapper) {
        const configElement =
            wrapper.querySelector(
                ".clientos-grid-config"
            );

        const gridDiv =
            wrapper.querySelector(
                "[data-grid-table]"
            );

        if (
            !configElement ||
            !gridDiv ||
            typeof agGrid === "undefined"
        ) {
            return;
        }

        const config = JSON.parse(
            configElement.textContent
        );

        let originalRows =
            Array.isArray(config.data)
                ? config.data
                : [];

        const filters =
            Array.isArray(config.filters)
                ? config.filters
                : [];

        const actions =
            config.actions ||
            {};

        const rowIdField =
            config.rowIdField ||
            actions.idField ||
            "id";

        const searchableFields =
            getSearchableFields(
                config.columns || []
            );

function getInitiallyFilteredRows() {
    return originalRows.filter(
        function (row) {
            return filters.every(
                function (filter) {
                    const element =
                        wrapper.querySelector(
                            `.clientos-grid-filter[data-field="${filter.name}"]`
                        );

                    const value =
                        element
                            ? element.value
                            : "";

                    return (
                        !value ||
                        toComparable(
                            row[filter.name]
                        ) === value
                    );
                }
            );
        }
    );
}

let currentRows =
    getInitiallyFilteredRows();

let gridApi;


        const gridOptions = {
            rowData: currentRows,

            columnDefs: buildColumnDefs(
                config.columns || [],
                actions
            ),

            context: {
                rowIdField: rowIdField
            },

            getRowId: function (params) {
                return toComparable(
                    params.data &&
                    params.data[rowIdField]
                );
            },

            defaultColDef: {
                sortable: true,
                filter: false,
                resizable: true,
                floatingFilter: false,
                suppressHeaderMenuButton: true
            },

            pagination: true,

            paginationPageSize: Number(
                config.pageSize || 10
            ),

            paginationPageSizeSelector: false,
            suppressPaginationPanel: true,
            rowHeight: 52,
            headerHeight: 54,
            animateRows: true,
            domLayout: "normal",

            rowClassRules: {
                "lead-row-action-pending":
                    function (params) {
                        const row =
                            params.data ||
                            {};

                        return (
                            row.is_status_pending === true ||
                            row.is_status_pending === "true" ||
                            row.working_status ===
                                "Called - Status Pending"
                        );
                    }
            },

            rowSelection: {
                mode: "multiRow",
                checkboxes: true,
                headerCheckbox: true,
                selectAll: "currentPage",
                enableClickSelection: false
            },

            onSelectionChanged: function () {
                updateSelectionState();
            },

            onPaginationChanged: function () {
                updatePaginationFooter();
            },

            onSortChanged: function () {
                updatePaginationFooter();
            }
        };

        gridApi = agGrid.createGrid(
            gridDiv,
            gridOptions
        );

        const totalBadge =
            wrapper.querySelector(
                "[data-grid-total]"
            );

        const activeBadge =
            wrapper.querySelector(
                "[data-grid-active]"
            );

        const inactiveBadge =
            wrapper.querySelector(
                "[data-grid-inactive]"
            );

        const rowSummary =
            wrapper.querySelector(
                "[data-grid-row-summary]"
            );

        const pageStatus =
            wrapper.querySelector(
                "[data-grid-page-status]"
            );

        const pageSizeSelect =
            wrapper.querySelector(
                "[data-grid-page-size]"
            );

        const firstButton =
            wrapper.querySelector(
                "[data-grid-first]"
            );

        const previousButton =
            wrapper.querySelector(
                "[data-grid-prev]"
            );

        const nextButton =
            wrapper.querySelector(
                "[data-grid-next]"
            );

        const lastButton =
            wrapper.querySelector(
                "[data-grid-last]"
            );

        const searchInput =
            wrapper.querySelector(
                "[data-grid-search]"
            );

        const selectedBadge =
            wrapper.querySelector(
                "[data-grid-selected]"
            );

        const bulkDeleteButton =
            wrapper.querySelector(
                "[data-grid-bulk-delete]"
            );

        function updateGridRows(rows) {
            currentRows = rows.slice();

            if (!gridApi) {
                return;
            }

            if (gridApi.setGridOption) {
                gridApi.setGridOption(
                    "rowData",
                    rows
                );
            } else if (gridApi.setRowData) {
                gridApi.setRowData(rows);
            }

            updateCounts();

            if (
                gridApi.paginationGoToFirstPage
            ) {
                gridApi.paginationGoToFirstPage();
            }

            window.setTimeout(
                updatePaginationFooter,
                0
            );

            window.setTimeout(
                updateSelectionState,
                0
            );
        }

        function updateCounts() {
            const statusField =
                config.statusField ||
                "status";

            const activeValues =
                (
                    config.activeValues ||
                    []
                ).map(toComparable);

            const activeCount =
                currentRows.filter(
                    function (row) {
                        return activeValues.includes(
                            toComparable(
                                row[statusField]
                            )
                        );
                    }
                ).length;

            const inactiveCount =
                currentRows.length -
                activeCount;

            if (totalBadge) {
                totalBadge.textContent =
                    "Total: " +
                    formatNumber(
                        currentRows.length
                    );
            }

            if (activeBadge) {
                activeBadge.textContent =
                    "Active: " +
                    formatNumber(
                        activeCount
                    );
            }

            if (inactiveBadge) {
                inactiveBadge.textContent =
                    "Inactive: " +
                    formatNumber(
                        inactiveCount
                    );
            }
        }

        function updatePaginationFooter() {
            if (!gridApi) {
                return;
            }

            const totalRows =
                currentRows.length;

            const pageSize =
                getSelectedPageSize(
                    pageSizeSelect,
                    totalRows,
                    config.pageSize || 10
                );

            const totalPages =
                Math.max(
                    1,
                    Math.ceil(
                        totalRows /
                        pageSize
                    )
                );

            const currentPage =
                gridApi.paginationGetCurrentPage
                    ? gridApi.paginationGetCurrentPage() + 1
                    : 1;

            const safePage =
                Math.min(
                    currentPage,
                    totalPages
                );

            const startRow =
                totalRows === 0
                    ? 0
                    : (
                        (safePage - 1) *
                        pageSize
                    ) + 1;

            const endRow =
                Math.min(
                    safePage *
                    pageSize,
                    totalRows
                );

            const isFirstPage =
                safePage <= 1;

            const isLastPage =
                safePage >= totalPages;

            if (rowSummary) {
                rowSummary.textContent =
                    startRow +
                    " to " +
                    endRow +
                    " of " +
                    formatNumber(
                        totalRows
                    );
            }

            if (pageStatus) {
                pageStatus.textContent =
                    "Page " +
                    safePage +
                    " of " +
                    totalPages;
            }

            if (firstButton) {
                firstButton.disabled =
                    isFirstPage;
            }

            if (previousButton) {
                previousButton.disabled =
                    isFirstPage;
            }

            if (nextButton) {
                nextButton.disabled =
                    isLastPage;
            }

            if (lastButton) {
                lastButton.disabled =
                    isLastPage;
            }
        }

        function updateSelectionState() {
            if (!gridApi) {
                return;
            }

            const selectedRows =
                gridApi.getSelectedRows
                    ? gridApi.getSelectedRows()
                    : [];

            const selectedCount =
                selectedRows.length;

            if (selectedBadge) {
                selectedBadge.textContent =
                    "Selected: " +
                    formatNumber(
                        selectedCount
                    );

                selectedBadge.classList.toggle(
                    "d-none",
                    selectedCount === 0
                );
            }

            if (bulkDeleteButton) {
                bulkDeleteButton.disabled =
                    selectedCount === 0;
            }
        }

        function applyGridState() {
            const query = searchInput
                ? searchInput.value
                    .trim()
                    .toLowerCase()
                : "";

            const filteredRows =
                originalRows.filter(
                    function (row) {
                        const filterMatched =
                            filters.every(
                                function (filter) {
                                    const element =
                                        wrapper.querySelector(
                                            `.clientos-grid-filter[data-field="${filter.name}"]`
                                        );

                                    const value =
                                        element
                                            ? element.value
                                            : "";

                                    return (
                                        !value ||
                                        toComparable(
                                            row[
                                                filter.name
                                            ]
                                        ) === value
                                    );
                                }
                            );

                        return (
                            filterMatched &&
                            rowMatchesSearch(
                                row,
                                searchableFields,
                                query
                            )
                        );
                    }
                );

            updateGridRows(
                filteredRows
            );
        }

        function setRows(rows) {
            originalRows =
                Array.isArray(rows)
                    ? rows.slice()
                    : [];

            applyGridState();
        }

        wrapper.clientosGrid = {
            api: gridApi,

            getRows: function () {
                return originalRows.slice();
            },

            getCurrentRows: function () {
                return currentRows.slice();
            },

            setRows: setRows
        };

        wrapper.querySelectorAll(
            ".clientos-grid-filter"
        ).forEach(
            function (element) {
                element.addEventListener(
                    "change",
                    applyGridState
                );
            }
        );

        if (searchInput) {
            searchInput.addEventListener(
                "input",
                applyGridState
            );
        }

        const resetButton =
            wrapper.querySelector(
                "[data-grid-reset]"
            );

        if (resetButton) {
            resetButton.addEventListener(
                "click",
                function () {
                    wrapper.querySelectorAll(
                        ".clientos-grid-filter"
                    ).forEach(
                        function (element) {
                            element.value = "";
                        }
                    );

                    if (searchInput) {
                        searchInput.value = "";
                    }

                    applyGridState();
                }
            );
        }

        if (
            bulkDeleteButton &&
            actions.bulkDeleteUrl
        ) {
            bulkDeleteButton.addEventListener(
                "click",
                function () {
                    const selectedRows =
                        gridApi.getSelectedRows
                            ? gridApi.getSelectedRows()
                            : [];

                    const selectedIdField =
                        actions.idField ||
                        rowIdField;

                    const selectedIds =
                        selectedRows
                            .map(
                                function (row) {
                                    return row[
                                        selectedIdField
                                    ];
                                }
                            )
                            .filter(
                                function (id) {
                                    return (
                                        id !== null &&
                                        id !== undefined &&
                                        id !== ""
                                    );
                                }
                            );

                    if (!selectedIds.length) {
                        return;
                    }

                    if (
                        !window.confirm(
                            "Delete " +
                            selectedIds.length +
                            " selected record(s)?"
                        )
                    ) {
                        return;
                    }

                    bulkDeleteButton.disabled =
                        true;

                    fetch(
                        actions.bulkDeleteUrl,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                    "application/json"
                            },
                            body: JSON.stringify({
                                ids: selectedIds
                            })
                        }
                    )
                        .then(
                            function (response) {
                                return response
                                    .json()
                                    .then(
                                        function (
                                            payload
                                        ) {
                                            return {
                                                ok:
                                                    response.ok,
                                                payload:
                                                    payload
                                            };
                                        }
                                    );
                            }
                        )
                        .then(
                            function (result) {
                                if (
                                    !result.ok ||
                                    !result.payload.success
                                ) {
                                    throw new Error(
                                        result.payload.message ||
                                        "Selected records could not be deleted."
                                    );
                                }

                                window.alert(
                                    result.payload.message
                                );

                                window.location.reload();
                            }
                        )
                        .catch(
                            function (error) {
                                window.alert(
                                    error.message
                                );

                                updateSelectionState();
                            }
                        );
                }
            );
        }

        if (pageSizeSelect) {
            pageSizeSelect.addEventListener(
                "change",
                function () {
                    const pageSize =
                        getSelectedPageSize(
                            pageSizeSelect,
                            currentRows.length,
                            config.pageSize ||
                                10
                        );

                    if (
                        gridApi.setGridOption
                    ) {
                        gridApi.setGridOption(
                            "paginationPageSize",
                            pageSize
                        );
                    } else if (
                        gridApi.paginationSetPageSize
                    ) {
                        gridApi.paginationSetPageSize(
                            pageSize
                        );
                    }

                    gridApi.paginationGoToFirstPage();

                    window.setTimeout(
                        updatePaginationFooter,
                        0
                    );
                }
            );
        }

        if (firstButton) {
            firstButton.addEventListener(
                "click",
                function () {
                    gridApi.paginationGoToFirstPage();

                    window.setTimeout(
                        updatePaginationFooter,
                        0
                    );
                }
            );
        }

        if (previousButton) {
            previousButton.addEventListener(
                "click",
                function () {
                    gridApi.paginationGoToPreviousPage();

                    window.setTimeout(
                        updatePaginationFooter,
                        0
                    );
                }
            );
        }

        if (nextButton) {
            nextButton.addEventListener(
                "click",
                function () {
                    gridApi.paginationGoToNextPage();

                    window.setTimeout(
                        updatePaginationFooter,
                        0
                    );
                }
            );
        }

        if (lastButton) {
            lastButton.addEventListener(
                "click",
                function () {
                    gridApi.paginationGoToLastPage();

                    window.setTimeout(
                        updatePaginationFooter,
                        0
                    );
                }
            );
        }

        applyGridTheme(
            gridDiv
        );

        updateGridRows(
            currentRows
        );

        updatePaginationFooter();

        const themeObserver =
            new MutationObserver(
                function () {
                    applyGridTheme(
                        gridDiv
                    );
                }
            );

        themeObserver.observe(
            document.documentElement,
            {
                attributes: true,
                attributeFilter: [
                    "data-bs-theme"
                ]
            }
        );
    }

    document.addEventListener(
        "DOMContentLoaded",
        function () {
            document.querySelectorAll(
                ".clientos-grid-wrap"
            ).forEach(
                createGrid
            );
        }
        
    );
})();