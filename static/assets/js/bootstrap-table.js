(function () {
    "use strict";

    class ClientOSBootstrapTable {
        constructor(wrapper) {
            this.wrapper = wrapper;

            this.configElement =
                wrapper.querySelector(
                    "[data-table-config]"
                );

            this.config = this.readConfig();

            this.table =
                wrapper.querySelector("table");

            this.tableHead =
                wrapper.querySelector(
                    "[data-table-head]"
                );

            this.tableBody =
                wrapper.querySelector(
                    "[data-table-body]"
                );

            this.searchInput =
                wrapper.querySelector(
                    "[data-table-search]"
                );

            this.searchLoader =
                wrapper.querySelector(
                    "[data-table-search-loader]"
                );

            this.pageSizeSelect =
                wrapper.querySelector(
                    "[data-table-page-size]"
                );

            this.filterElements =
                wrapper.querySelectorAll(
                    "[data-table-filter]"
                );

            this.pagination =
                wrapper.querySelector(
                    "[data-table-pagination]"
                );

            this.tableInfo =
                wrapper.querySelector(
                    "[data-table-info]"
                );

            this.errorBox =
                wrapper.querySelector(
                    "[data-table-error]"
                );

            this.refreshButton =
                wrapper.querySelector(
                    "[data-table-refresh]"
                );

            this.resetButton =
                wrapper.querySelector(
                    "[data-table-reset]"
                );

            this.currentRows = [];

            this.state = {
                page: 1,
                pageSize: Number(
                    this.config.pageSize || 25
                ),
                search: "",
                sort:
                    this.config.defaultSort ||
                    "",
                order:
                    this.config.defaultOrder ||
                    "asc",
                filters: {}
            };

            this.searchTimer = null;
            this.requestController = null;

            this.renderHeader();
            this.bindEvents();
            this.loadData();
        }

        /**
         * Read the JSON configuration stored inside the table wrapper.
         */
        readConfig() {
            if (!this.configElement) {
                return {};
            }

            try {
                return JSON.parse(
                    this.configElement
                        .textContent
                        .trim()
                );
            } catch (error) {
                console.error(
                    "Invalid Bootstrap table configuration.",
                    error
                );

                return {};
            }
        }

        /**
         * Register all table events.
         */
        bindEvents() {
            this.bindSearchEvent();
            this.bindPageSizeEvent();
            this.bindFilterEvents();
            this.bindRefreshEvent();
            this.bindResetEvent();
            this.bindSortingEvent();
            this.bindPaginationEvent();
            this.bindTableButtonEvents();
        }

        /**
         * Load table data after the user stops typing.
         */
        bindSearchEvent() {
            if (!this.searchInput) {
                return;
            }

            this.searchInput.addEventListener(
                "input",
                () => {
                    window.clearTimeout(
                        this.searchTimer
                    );

                    this.toggleSearchLoader(
                        true
                    );

                    this.searchTimer =
                        window.setTimeout(
                            () => {
                                this.state.search =
                                    this.searchInput
                                        .value
                                        .trim();

                                this.state.page = 1;

                                this.loadData();
                            },
                            400
                        );
                }
            );
        }

        /**
         * Reload data when the page-size selector changes.
         */
        bindPageSizeEvent() {
            if (!this.pageSizeSelect) {
                return;
            }

            this.pageSizeSelect.addEventListener(
                "change",
                () => {
                    this.state.pageSize =
                        Number(
                            this.pageSizeSelect
                                .value
                        );

                    this.state.page = 1;

                    this.loadData();
                }
            );
        }

        /**
         * Reload data when any configured filter changes.
         */
        bindFilterEvents() {
            this.filterElements.forEach(
                (filterElement) => {
                    filterElement.addEventListener(
                        "change",
                        () => {
                            const filterName =
                                filterElement
                                    .dataset
                                    .filterName;

                            this.state.filters[
                                filterName
                            ] =
                                filterElement.value;

                            this.state.page = 1;

                            this.loadData();
                        }
                    );
                }
            );
        }

        /**
         * Reload the current table state.
         */
        bindRefreshEvent() {
            if (!this.refreshButton) {
                return;
            }

            this.refreshButton.addEventListener(
                "click",
                () => {
                    this.loadData();
                }
            );
        }

        /**
         * Reset search, filters, sorting and page size.
         */
        bindResetEvent() {
            if (!this.resetButton) {
                return;
            }

            this.resetButton.addEventListener(
                "click",
                () => {
                    this.resetTable();
                }
            );
        }

        /**
         * Apply sorting when a sortable heading is clicked.
         */
        bindSortingEvent() {
            if (!this.tableHead) {
                return;
            }

            this.tableHead.addEventListener(
                "click",
                (event) => {
                    const sortButton =
                        event.target.closest(
                            "[data-sort-field]"
                        );

                    if (!sortButton) {
                        return;
                    }

                    const sortField =
                        sortButton.dataset
                            .sortField;

                    if (!sortField) {
                        return;
                    }

                    if (
                        this.state.sort ===
                        sortField
                    ) {
                        this.state.order =
                            this.state.order ===
                            "asc"
                                ? "desc"
                                : "asc";
                    } else {
                        this.state.sort =
                            sortField;

                        this.state.order =
                            "asc";
                    }

                    this.state.page = 1;

                    this.renderHeader();
                    this.loadData();
                }
            );
        }

        /**
         * Change the current page.
         */
        bindPaginationEvent() {
            if (!this.pagination) {
                return;
            }

            this.pagination.addEventListener(
                "click",
                (event) => {
                    const pageButton =
                        event.target.closest(
                            "[data-page]"
                        );

                    if (
                        !pageButton ||
                        pageButton.disabled
                    ) {
                        return;
                    }

                    const page =
                        Number(
                            pageButton.dataset.page
                        );

                    if (
                        !page ||
                        page === this.state.page
                    ) {
                        return;
                    }

                    this.state.page = page;

                    this.loadData();
                }
            );
        }

        /**
         * Handle every configurable table button from one listener.
         */
        bindTableButtonEvents() {
            if (!this.tableBody) {
                return;
            }

            this.tableBody.addEventListener(
                "click",
                (event) => {
                    const button =
                        event.target.closest(
                            "[data-table-action]"
                        );

                    if (!button) {
                        return;
                    }

                    if (
                        button.disabled ||
                        button.getAttribute(
                            "aria-disabled"
                        ) === "true"
                    ) {
                        return;
                    }

                    const rowElement =
                        button.closest(
                            "[data-row-index]"
                        );

                    if (!rowElement) {
                        return;
                    }

                    const rowIndex =
                        Number(
                            rowElement.dataset
                                .rowIndex
                        );

                    const row =
                        this.currentRows[
                            rowIndex
                        ];

                    if (!row) {
                        return;
                    }

                    const action =
                        button.dataset
                            .tableAction || "";

                    const modalId =
                        button.dataset
                            .tableModal || "";

                    if (modalId) {
                        this.openConfiguredModal(
                            modalId,
                            row,
                            button
                        );
                    }

                    document.dispatchEvent(
                        new CustomEvent(
                            "clientosBootstrapTableAction",
                            {
                                detail: {
                                    action: action,
                                    row: row,
                                    button: button,
                                    modalId:
                                        modalId,
                                    tableId:
                                        this.config
                                            .tableId
                                }
                            }
                        )
                    );
                }
            );
        }

        /**
         * Open a Bootstrap modal configured on a table button.
         */
        openConfiguredModal(
            modalId,
            row,
            button
        ) {
            const normalizedModalId =
                String(modalId)
                    .replace(/^#/, "");

            const modalElement =
                document.getElementById(
                    normalizedModalId
                );

            if (
                !modalElement ||
                typeof bootstrap ===
                    "undefined" ||
                !bootstrap.Modal
            ) {
                return;
            }

            modalElement.dataset.tableId =
                this.config.tableId || "";

            modalElement.dataset.tableAction =
                button.dataset
                    .tableAction || "";

            modalElement.dataset.rowIndex =
                button.closest(
                    "[data-row-index]"
                )?.dataset.rowIndex || "";

            Object.entries(row).forEach(
                ([key, value]) => {
                    const fieldElements =
                        modalElement
                            .querySelectorAll(
                                `[data-modal-field="${this.escapeSelector(
                                    key
                                )}"]`
                            );

                    fieldElements.forEach(
                        (fieldElement) => {
                            this.setModalFieldValue(
                                fieldElement,
                                value
                            );
                        }
                    );
                }
            );

            bootstrap.Modal
                .getOrCreateInstance(
                    modalElement
                )
                .show();
        }

        /**
         * Insert row values into configured modal fields.
         */
        setModalFieldValue(
            element,
            value
        ) {
            const safeValue =
                value ?? "";

            if (
                element instanceof
                    HTMLInputElement ||
                element instanceof
                    HTMLSelectElement ||
                element instanceof
                    HTMLTextAreaElement
            ) {
                element.value =
                    String(safeValue);

                return;
            }

            element.textContent =
                String(safeValue);
        }

        /**
         * Render the table heading from the column configuration.
         */
        renderHeader() {
            const columns =
                this.config.columns || [];

            this.tableHead.innerHTML = "";

            columns.forEach(
                (column) => {
                    const th =
                        document.createElement(
                            "th"
                        );

                    th.scope = "col";

                    if (column.width) {
                        th.style.width =
                            column.width;
                    }

                    if (column.minWidth) {
                        th.style.minWidth =
                            column.minWidth;
                    }

                    if (column.className) {
                        th.className =
                            column.className;
                    }

                    if (column.sortable) {
                        const button =
                            document.createElement(
                                "button"
                            );

                        button.type =
                            "button";

                        button.className =
                            "btn btn-link text-body text-decoration-none p-0 fw-semibold d-inline-flex align-items-center gap-1";

                        button.dataset
                            .sortField =
                            column.field;

                        button.innerHTML =
                            this.escapeHtml(
                                column.label ||
                                ""
                            ) +
                            this.getSortIcon(
                                column.field
                            );

                        th.appendChild(
                            button
                        );
                    } else {
                        th.textContent =
                            column.label || "";
                    }

                    this.tableHead.appendChild(
                        th
                    );
                }
            );
        }

        /**
         * Return the correct sorting icon for a column.
         */
        getSortIcon(field) {
            if (
                this.state.sort !== field
            ) {
                return (
                    '<i class="mdi mdi-unfold-more-horizontal text-muted"></i>'
                );
            }

            if (
                this.state.order === "desc"
            ) {
                return (
                    '<i class="mdi mdi-arrow-down"></i>'
                );
            }

            return (
                '<i class="mdi mdi-arrow-up"></i>'
            );
        }

        /**
         * Build the AJAX URL and send only changed values.
         */
        buildRequestUrl() {
            const url =
                new URL(
                    this.config.apiUrl,
                    window.location.origin
                );

            const defaultPageSize =
                Number(
                    this.config.pageSize ||
                    25
                );

            const defaultSort =
                this.config.defaultSort ||
                "";

            const defaultOrder =
                this.config.defaultOrder ||
                "asc";

            if (this.state.page > 1) {
                url.searchParams.set(
                    "page",
                    this.state.page
                );
            }

            if (
                this.state.pageSize !==
                defaultPageSize
            ) {
                url.searchParams.set(
                    "page_size",
                    this.state.pageSize
                );
            }

            if (this.state.search) {
                url.searchParams.set(
                    "search",
                    this.state.search
                );
            }

            if (
                this.state.sort &&
                this.state.sort !==
                    defaultSort
            ) {
                url.searchParams.set(
                    "sort",
                    this.state.sort
                );
            }

            if (
                this.state.order &&
                this.state.order !==
                    defaultOrder
            ) {
                url.searchParams.set(
                    "order",
                    this.state.order
                );
            }

            Object.entries(
                this.state.filters
            ).forEach(
                ([name, value]) => {
                    if (value !== "") {
                        url.searchParams.set(
                            name,
                            value
                        );
                    }
                }
            );

            return url.toString();
        }

        /**
         * Load table data through AJAX.
         */
        async loadData() {
            this.showError("");
            this.showLoading();

            if (this.requestController) {
                this.requestController
                    .abort();
            }

            this.requestController =
                new AbortController();

            try {
                const response =
                    await fetch(
                        this.buildRequestUrl(),
                        {
                            method: "GET",
                            headers: {
                                "Accept":
                                    "application/json",
                                "X-Requested-With":
                                    "XMLHttpRequest"
                            },
                            signal:
                                this
                                    .requestController
                                    .signal
                        }
                    );

                const payload =
                    await response.json();

                if (!response.ok) {
                    throw new Error(
                        payload.message ||
                        "Unable to load table data."
                    );
                }

                this.currentRows =
                    payload.data || [];

                this.renderRows(
                    this.currentRows
                );

                this.renderPagination({
                    page:
                        Number(
                            payload.page ||
                            1
                        ),
                    pageSize:
                        Number(
                            payload.page_size ||
                            this.state
                                .pageSize
                        ),
                    total:
                        Number(
                            payload.total ||
                            0
                        ),
                    totalPages:
                        Number(
                            payload.total_pages ||
                            1
                        )
                });
            } catch (error) {
                if (
                    error.name ===
                    "AbortError"
                ) {
                    return;
                }

                console.error(
                    "Bootstrap table request failed.",
                    error
                );

                this.currentRows = [];

                this.renderRows([]);

                this.renderPagination({
                    page: 1,
                    pageSize:
                        this.state.pageSize,
                    total: 0,
                    totalPages: 1
                });

                this.showError(
                    error.message ||
                    "Unable to load table data."
                );
            } finally {
                this.toggleSearchLoader(
                    false
                );
            }
        }

        /**
         * Display the loading row.
         */
        showLoading() {
            const columnCount =
                Math.max(
                    (
                        this.config
                            .columns ||
                        []
                    ).length,
                    1
                );

            this.tableBody.innerHTML = `
                <tr>
                    <td
                        colspan="${columnCount}"
                        class="text-center py-5"
                    >
                        <span
                            class="spinner-border spinner-border-sm me-2"
                            role="status"
                        ></span>
                        Loading records...
                    </td>
                </tr>
            `;
        }

        /**
         * Render all table rows.
         */
        renderRows(rows) {
            const columns =
                this.config.columns || [];

            this.tableBody.innerHTML = "";

            if (!rows.length) {
                this.renderEmptyRow(
                    columns.length
                );

                return;
            }

            rows.forEach(
                (
                    rowData,
                    rowIndex
                ) => {
                    const row =
                        document.createElement(
                            "tr"
                        );

                    row.dataset.rowIndex =
                        rowIndex;

                    columns.forEach(
                        (column) => {
                            const cell =
                                document
                                    .createElement(
                                        "td"
                                    );

                            if (
                                column.className
                            ) {
                                cell.className =
                                    column
                                        .className;
                            }

                            if (
                                column.cellClass
                            ) {
                                cell.classList.add(
                                    ...String(
                                        column
                                            .cellClass
                                    ).split(" ")
                                );
                            }

                            cell.innerHTML =
                                this.renderCell(
                                    rowData,
                                    column
                                );

                            row.appendChild(
                                cell
                            );
                        }
                    );

                    this.tableBody
                        .appendChild(row);
                }
            );

            if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
                this.tableBody.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
                    new bootstrap.Tooltip(el);
                });
            }
        }

        /**
         * Display the empty-state row.
         */
        renderEmptyRow(
            columnCount
        ) {
            const row =
                document.createElement(
                    "tr"
                );

            const cell =
                document.createElement(
                    "td"
                );

            cell.colSpan =
                Math.max(
                    columnCount,
                    1
                );

            cell.className =
                "text-center text-muted py-5";

            cell.innerHTML = `
                <i
                    class="mdi mdi-database-off-outline fs-2 d-block mb-2"
                ></i>
                No records found.
            `;

            row.appendChild(cell);
            this.tableBody.appendChild(
                row
            );
        }

        /**
         * Render one table cell based on its configured type.
         */
        renderCell(row, column) {
            const value =
                row[column.field];

            switch (column.type) {
                case "serial":
                    return this.escapeHtml(
                        value ?? ""
                    );

                case "badge":
                    return this.renderBadge(
                        value,
                        column
                    );

                case "boolean":
                    return value
                        ? '<span class="badge bg-success-subtle text-success">Yes</span>'
                        : '<span class="badge bg-secondary-subtle text-secondary">No</span>';

                case "buttons":
                case "actions":
                    return this.renderButtons(
                        row,
                        column
                    );

                case "html":
                    return value || "";

                default:
                    return this.escapeHtml(
                        value ?? ""
                    );
            }
        }

        /**
         * Render a configured badge.
         */
        renderBadge(
            value,
            column
        ) {
            const normalizedValue =
                String(
                    value ?? ""
                );

            const badgeMap =
                column.badgeMap || {};

            const badge =
                badgeMap[
                    normalizedValue
                ] || {
                    class:
                        "bg-secondary-subtle text-secondary",
                    label:
                        normalizedValue ||
                        "NA"
                };

            return `
                <span class="badge ${this.escapeAttribute(
                    badge.class || ""
                )}">
                    ${this.escapeHtml(
                        badge.label ||
                        normalizedValue
                    )}
                </span>
            `;
        }

        /**
         * Render one or multiple configurable buttons inside any column.
         */
        renderButtons(
            row,
            column
        ) {
            const buttons =
                column.buttons ||
                column.actions ||
                [];

            return buttons
                .filter(
                    (button) =>
                        this.shouldShowButton(
                            button,
                            row
                        )
                )
                .map(
                    (button) =>
                        this.renderButton(
                            button,
                            row
                        )
                )
                .join(
                    column.buttonSeparator ??
                    " "
                );
        }

        /**
         * Decide whether a button should be visible for the current row.
         */
        shouldShowButton(
            button,
            row
        ) {
            const conditionField =
                button.flagField ||
                button.conditionField ||
                button.showWhenField;

            if (!conditionField) {
                return (
                    button.visible !==
                    false
                );
            }

            const rowValue =
                row[conditionField];

            const allowedValues =
                button.flagValues ||
                button.conditionValues ||
                button.showWhenValues;

            if (
                Array.isArray(
                    allowedValues
                )
            ) {
                return allowedValues.some(
                    (allowedValue) =>
                        String(
                            allowedValue
                        ) ===
                        String(
                            rowValue
                        )
                );
            }

            if (
                Object.prototype.hasOwnProperty.call(
                    button,
                    "flagValue"
                )
            ) {
                return (
                    String(rowValue) ===
                    String(
                        button.flagValue
                    )
                );
            }

            return this.isTruthyValue(
                rowValue
            );
        }

        /**
         * Render one button, link or static value.
         */
        renderButton(
            button,
            row
        ) {
            const action =
                button.action ||
                button.name ||
                "";

            const labelValue =
                button.labelField
                    ? row[
                        button
                            .labelField
                    ]
                    : button.label;

            const titleValue =
                button.titleField
                    ? row[
                        button
                            .titleField
                    ]
                    : (
                        button.title ||
                        labelValue ||
                        ""
                    );

            const icon =
                button.icon
                    ? `<i class="${this.escapeAttribute(
                        button.icon
                    )}"></i>`
                    : "";

            const label =
                button.showLabel === false
                    ? ""
                    : (
                        labelValue !==
                            undefined &&
                        labelValue !==
                            null
                            ? `<span class="${button.icon ? "ms-1" : ""}">${this.escapeHtml(
                                labelValue
                            )}</span>`
                            : ""
                    );

           let className =
    button.class ||
    "btn btn-sm btn-light";

if (
    button.classField &&
    button.classMap
) {
    const fieldValue =
        row[button.classField];

    className =
        button.classMap[fieldValue] ??
        button.classMap[String(fieldValue)] ??
        className;
}

            const modalId =
                button.modalId ||
                button.modal ||
                "";

            const disabled =
                this.isButtonDisabled(
                    button,
                    row
                );

            if (
                button.type ===
                    "static" ||
                button.static === true
            ) {
                return `
                    <span
                        class="${this.escapeAttribute(
                            className
                        )}"
                        title="${this.escapeAttribute(
                            titleValue
                        )}"
                    >
                        ${icon}${label}
                    </span>
                `;
            }

            if (
                button.type === "link" ||
                button.url ||
                button.urlField
            ) {
                const url =
                    this.resolveButtonUrl(
                        button,
                        row
                    );

                return `
                    <a
                        href="${this.escapeAttribute(
                            url || "#"
                        )}"
                        class="${this.escapeAttribute(
                            className
                        )}"
                        title="${this.escapeAttribute(
                            titleValue
                        )}"
                        ${button.target
                            ? `target="${this.escapeAttribute(
                                button.target
                            )}"`
                            : ""}
                        ${button.newTab
                            ? 'target="_blank" rel="noopener noreferrer"'
                            : ""}
                        ${disabled
                            ? 'aria-disabled="true" tabindex="-1"'
                            : ""}
                    >
                        ${icon}${label}
                    </a>
                `;
            }

            return `
                <button
                    type="button"
                    class="${this.escapeAttribute(
                        className
                    )}"
                    data-table-action="${this.escapeAttribute(
                        action
                    )}"
                    data-bs-toggle="tooltip"
                    data-bs-placement="top"
                    ${modalId
                        ? `data-table-modal="${this.escapeAttribute(
                            modalId
                        )}"`
                        : ""}
                    title="${this.escapeAttribute(
                        titleValue
                    )}"
                    ${disabled
                        ? 'disabled aria-disabled="true"'
                        : ""}
                >
                    ${icon}${label}
                </button>
            `;
        }

        /**
         * Decide whether a configured button should be disabled.
         */
        isButtonDisabled(
            button,
            row
        ) {
            if (
                button.disabled === true
            ) {
                return true;
            }

            const field =
                button.disabledField;

            if (!field) {
                return false;
            }

            const rowValue =
                row[field];

            if (
                Array.isArray(
                    button.disabledValues
                )
            ) {
                return button
                    .disabledValues
                    .some(
                        (value) =>
                            String(value) ===
                            String(rowValue)
                    );
            }

            return this.isTruthyValue(
                rowValue
            );
        }

        /**
         * Resolve a static or row-based URL.
         */
        resolveButtonUrl(
            button,
            row
        ) {
            if (button.urlField) {
                return (
                    row[
                        button.urlField
                    ] || ""
                );
            }

            let url =
                button.url || "";

            Object.entries(row).forEach(
                ([key, value]) => {
                    url = url.replaceAll(
                        `{${key}}`,
                        encodeURIComponent(
                            value ?? ""
                        )
                    );
                }
            );

            return url;
        }

        /**
         * Treat common database values as true.
         */
        isTruthyValue(value) {
            return [
                true,
                1,
                "1",
                "true",
                "yes",
                "active"
            ].includes(
                typeof value ===
                    "string"
                    ? value
                        .trim()
                        .toLowerCase()
                    : value
            );
        }

        /**
         * Render pagination and record information.
         */
        renderPagination(meta) {
            const totalPages =
                Math.max(
                    meta.totalPages,
                    1
                );

            this.state.page =
                Math.min(
                    Math.max(
                        meta.page,
                        1
                    ),
                    totalPages
                );

            const start =
                meta.total === 0
                    ? 0
                    : (
                        (
                            this.state
                                .page - 1
                        ) *
                        meta.pageSize
                    ) + 1;

            const end =
                Math.min(
                    this.state.page *
                    meta.pageSize,
                    meta.total
                );

            this.tableInfo.textContent =
                `Showing ${start} to ${end} of ${meta.total} records`;

            this.pagination.innerHTML =
                "";

            this.pagination.appendChild(
                this.createPageItem(
                    "Previous",
                    this.state.page - 1,
                    this.state.page <= 1
                )
            );

            this.getVisiblePages(
                this.state.page,
                totalPages
            ).forEach(
                (page) => {
                    this.pagination
                        .appendChild(
                            this.createPageItem(
                                page,
                                page,
                                false,
                                page ===
                                    this.state
                                        .page
                            )
                        );
                }
            );

            this.pagination.appendChild(
                this.createPageItem(
                    "Next",
                    this.state.page + 1,
                    this.state.page >=
                        totalPages
                )
            );
        }

        /**
         * Return a maximum of five visible page numbers.
         */
        getVisiblePages(
            currentPage,
            totalPages
        ) {
            const pages = [];

            let start =
                Math.max(
                    currentPage - 2,
                    1
                );

            let end =
                Math.min(
                    start + 4,
                    totalPages
                );

            start =
                Math.max(
                    end - 4,
                    1
                );

            for (
                let page = start;
                page <= end;
                page += 1
            ) {
                pages.push(page);
            }

            return pages;
        }

        /**
         * Create one pagination button.
         */
        createPageItem(
            label,
            page,
            disabled,
            active
        ) {
            const item =
                document.createElement(
                    "li"
                );

            item.className =
                "page-item" +
                (
                    disabled
                        ? " disabled"
                        : ""
                ) +
                (
                    active
                        ? " active"
                        : ""
                );

            const button =
                document.createElement(
                    "button"
                );

            button.type = "button";
            button.className =
                "page-link";
            button.dataset.page =
                page;
            button.disabled =
                disabled;
            button.textContent =
                label;

            item.appendChild(button);

            return item;
        }

        /**
         * Reset the table to its original configuration.
         */
        resetTable() {
            this.state.page = 1;
            this.state.search = "";
            this.state.sort =
                this.config.defaultSort ||
                "";
            this.state.order =
                this.config.defaultOrder ||
                "asc";
            this.state.filters = {};

            if (this.searchInput) {
                this.searchInput.value =
                    "";
            }

            this.filterElements.forEach(
                (filterElement) => {
                    filterElement.value =
                        "";
                }
            );

            if (this.pageSizeSelect) {
                this.pageSizeSelect.value =
                    String(
                        this.config
                            .pageSize ||
                        25
                    );

                this.state.pageSize =
                    Number(
                        this
                            .pageSizeSelect
                            .value
                    );
            }

            this.renderHeader();
            this.loadData();
        }

        /**
         * Show or hide the search loading indicator.
         */
        toggleSearchLoader(show) {
            if (!this.searchLoader) {
                return;
            }

            this.searchLoader
                .classList
                .toggle(
                    "d-none",
                    !show
                );
        }

        /**
         * Show or clear the table error message.
         */
        showError(message) {
            if (!this.errorBox) {
                return;
            }

            if (!message) {
                this.errorBox
                    .textContent = "";

                this.errorBox
                    .classList
                    .add("d-none");

                return;
            }

            this.errorBox.textContent =
                message;

            this.errorBox
                .classList
                .remove("d-none");
        }

        /**
         * Escape HTML before inserting text into the page.
         */
        escapeHtml(value) {
            const element =
                document.createElement(
                    "div"
                );

            element.textContent =
                String(value ?? "");

            return element.innerHTML;
        }

        /**
         * Escape values used inside HTML attributes.
         */
        escapeAttribute(value) {
            return this.escapeHtml(
                value
            )
                .replace(
                    /"/g,
                    "&quot;"
                )
                .replace(
                    /'/g,
                    "&#039;"
                );
        }

        /**
         * Escape values used inside querySelector selectors.
         */
        escapeSelector(value) {
            if (
                window.CSS &&
                typeof window.CSS.escape ===
                    "function"
            ) {
                return window.CSS.escape(
                    String(value)
                );
            }

            return String(value)
                .replace(
                    /["\\]/g,
                    "\\$&"
                );
        }
    }

    /**
     * Initialize every Bootstrap table component on the page.
     */
    function initializeBootstrapTables() {
        document
            .querySelectorAll(
                ".clientos-bootstrap-table-wrapper"
            )
            .forEach(
                (wrapper) => {
                    if (
                        wrapper.dataset
                            .tableInitialized ===
                        "1"
                    ) {
                        return;
                    }

                    wrapper.dataset
                        .tableInitialized =
                        "1";

                    new ClientOSBootstrapTable(
                        wrapper
                    );
                }
            );
    }

    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeBootstrapTables
        );
    } else {
        initializeBootstrapTables();
    }

    window.ClientOSBootstrapTable =
        ClientOSBootstrapTable;
})();