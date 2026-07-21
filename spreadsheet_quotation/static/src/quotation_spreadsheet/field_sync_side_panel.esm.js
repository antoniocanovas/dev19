/** @odoo-module **/

import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {helpers, registries} from "@odoo/o-spreadsheet";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";

const {sidePanelRegistry} = registries;
const {lettersToNumber, numberToLetters} = helpers;
const {Component, useState, onWillStart} = owl;

// Used when sale.order.line fields cannot be read from the server.
const FALLBACK_SYNCABLE_FIELDS = [
    {name: "product_id", label: _t("Product"), type: "many2one"},
    {name: "name", label: _t("Description"), type: "char"},
    {name: "product_uom_qty", label: _t("Quantity"), type: "float"},
    {name: "price_unit", label: _t("Unit Price"), type: "float"},
    {name: "discount", label: _t("Discount (%)"), type: "float"},
];

// Types whose spreadsheet cell value can be written straight to the field.
// Dates are excluded on purpose: a spreadsheet date cell evaluates to a serial
// number, not to a value the ORM would accept. Relational fields are excluded
// too, except product_id, which is resolved by name in _findProduct().
const SYNCABLE_FIELD_TYPES = [
    "char",
    "text",
    "float",
    "integer",
    "monetary",
    "boolean",
    "selection",
];

const NON_SYNCABLE_FIELDS = ["id", "order_id", "display_type", "sequence"];

export class FieldSyncPanel extends Component {
    static template = "spreadsheet_quotation.FieldSyncPanel";
    // o-spreadsheet always passes onCloseSidePanel to a side panel Body
    static props = {
        onCloseSidePanel: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.availableColumns = [];
        this.syncableFields = FALLBACK_SYNCABLE_FIELDS;
        this.state = useState({
            newColumn: "",
            newField: "",
            saving: false,
        });
        onWillStart(async () => {
            this._loadAvailableColumns();
            await this._loadSyncableFields();
        });
    }

    get mappings() {
        try {
            return this.env.model.getters.getFieldSyncMappings();
        } catch {
            return [];
        }
    }

    get listId() {
        try {
            return this.env.model.getters.getFieldSyncListId();
        } catch {
            return "1";
        }
    }

    get hasSOList() {
        try {
            const id = this.listId;
            if (!id || !this.env.model.getters.isExistingList(id)) {
                return false;
            }
            const def = this.env.model.getters.getListDefinition(id);
            return def.model === "sale.order.line";
        } catch {
            return false;
        }
    }

    get orderId() {
        try {
            const filters = this.env.model.getters.getGlobalFilters();
            for (const filter of filters) {
                if (filter.type === "relation" && filter.modelName === "sale.order") {
                    // Since 19.0 a relational filter value is {operator, ids},
                    // no longer a bare array of ids.
                    const value = this.env.model.getters.getGlobalFilterValue(
                        filter.id
                    );
                    const defaultValue =
                        this.env.model.getters.getGlobalFilterDefaultValue(filter.id);
                    const ids = value?.ids ?? defaultValue?.ids;
                    if (Array.isArray(ids) && ids.length > 0) {
                        return ids[0];
                    }
                }
            }
        } catch {
            // Filter getters not available
        }
        return null;
    }

    get hasProductMapping() {
        return this.mappings.some((m) => m.field === "product_id");
    }

    _loadAvailableColumns() {
        const sheetId = this.env.model.getters.getActiveSheetId();
        const numberOfCols = this.env.model.getters.getNumberCols(sheetId);
        this.availableColumns = Array.from({length: numberOfCols}, (_, i) =>
            numberToLetters(i)
        );
    }

    /**
     * Build the list of sale.order.line fields that can be written from the
     * spreadsheet: stored, not readonly, and of a type whose cell value maps
     * directly onto the field. Custom fields (purchase_price, ...) are picked
     * up automatically.
     */
    async _loadSyncableFields() {
        let fields = null;
        try {
            fields = await this.orm.call("sale.order.line", "fields_get", [], {
                attributes: ["string", "type", "store", "readonly", "relation"],
            });
        } catch {
            // Keep the fallback list
            return;
        }
        const syncable = [];
        for (const [name, def] of Object.entries(fields)) {
            if (NON_SYNCABLE_FIELDS.includes(name) || !def.store || def.readonly) {
                continue;
            }
            const isProduct =
                name === "product_id" && def.relation === "product.product";
            if (!isProduct && !SYNCABLE_FIELD_TYPES.includes(def.type)) {
                continue;
            }
            syncable.push({name, label: def.string || name, type: def.type});
        }
        if (syncable.length) {
            syncable.sort((a, b) => a.label.localeCompare(b.label));
            this.syncableFields = syncable;
        }
    }

    getFieldLabel(fieldName) {
        const field = this.syncableFields.find((f) => f.name === fieldName);
        return field ? field.label.toString() : fieldName;
    }

    addMapping() {
        if (!this.state.newColumn || !this.state.newField) {
            return;
        }
        const existing = this.mappings.find((m) => m.column === this.state.newColumn);
        if (existing) {
            this.notification.add(_t("This column already has a mapping"), {
                type: "warning",
            });
            return;
        }
        const existingField = this.mappings.find(
            (m) => m.field === this.state.newField
        );
        if (existingField) {
            this.notification.add(_t("This field already has a mapping"), {
                type: "warning",
            });
            return;
        }
        this.env.model.dispatch("ADD_FIELD_SYNC_MAPPING", {
            mapping: {
                column: this.state.newColumn,
                field: this.state.newField,
            },
        });
        this.state.newColumn = "";
        this.state.newField = "";
    }

    removeMapping(index) {
        this.env.model.dispatch("REMOVE_FIELD_SYNC_MAPPING", {index});
    }

    /**
     * Read one spreadsheet row and return the SO line ID (if it maps to an
     * existing ODOO.LIST record), the mapped field values, and a flag
     * indicating whether the row contains any data worth syncing.
     */
    _readRow(sheetId, row) {
        const result = {lineId: null, values: {}, productName: null, hasData: false};

        try {
            const listPosition = row - 1;
            const idResult = this.env.model.getters.getListCellValueAndFormat(
                this.listId,
                listPosition,
                "id"
            );
            if (idResult && idResult.value && typeof idResult.value === "number") {
                result.lineId = idResult.value;
            }
        } catch {
            // No list record at this position
        }

        for (const mapping of this.mappings) {
            const colIdx = lettersToNumber(mapping.column);
            const cell = this.env.model.getters.getEvaluatedCell({
                sheetId,
                col: colIdx,
                row,
            });
            if (
                cell.type !== "empty" &&
                cell.value !== undefined &&
                cell.value !== ""
            ) {
                result.hasData = true;
                if (mapping.field === "product_id") {
                    result.productName = String(cell.value);
                } else {
                    result.values[mapping.field] = cell.value;
                }
            }
        }

        if (result.lineId) {
            result.hasData = true;
        }
        return result;
    }

    /**
     * Search for a product by name using name_search (handles display_name,
     * internal reference, etc.).  Returns the product ID or null.
     */
    async _findProduct(name) {
        if (!name) {
            return null;
        }
        for (const operator of ["=", "ilike"]) {
            const matches = await this.orm.call("product.product", "name_search", [], {
                name,
                operator,
                limit: 1,
            });
            if (matches.length) {
                return matches[0][0];
            }
        }
        return null;
    }

    _getRpcErrorMessage(error) {
        return error.data?.message || error.message || String(error);
    }

    /**
     * Ensure the linked sale order allows spreadsheet synchronization.
     */
    async _ensureOrderSyncAllowed(orderId) {
        const [order] = await this.orm.read("sale.order", [orderId], ["state"]);
        if (order.state === "sale" || order.state === "cancel") {
            const message =
                order.state === "cancel"
                    ? _t("Cannot sync a cancelled quotation.")
                    : _t("Cannot sync a confirmed sales order.");
            this.notification.add(message, {type: "warning"});
            return false;
        }
        return true;
    }

    /**
     * Show a confirmation dialog listing the products that will be created.
     * Resolves to true when the user confirms, false otherwise.
     */
    _confirmCreateProducts(productNames) {
        return new Promise((resolve) => {
            const list = productNames.map((n) => `  • ${n}`).join("\n");
            const body =
                _t(
                    "The following products were not found in the catalog and will be created:"
                ) +
                "\n\n" +
                list +
                "\n\n" +
                _t("Do you want to create them?");

            this.dialog.add(ConfirmationDialog, {
                title: _t("Create New Products"),
                body,
                confirmLabel: _t("Create and Sync"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
    }

    /**
     * Main sync entry-point.
     *
     * 1. Scan spreadsheet rows for data (existing lines and new rows).
     * 2. Resolve product names to IDs (via name_search).
     * 3. If products are missing, ask the user for confirmation to create them.
     * 4. Build ORM x2many commands and write to the sale order.
     */
    async saveToSaleOrder() {
        if (!this.hasSOList) {
            this.notification.add(_t("No sale order line list found"), {
                type: "warning",
            });
            return;
        }
        const orderId = this.orderId;
        if (!orderId) {
            this.notification.add(
                _t("No sale order linked. Set the Sale Order filter first."),
                {type: "warning"}
            );
            return;
        }
        if (!this.mappings.length) {
            this.notification.add(_t("No field mappings configured"), {
                type: "warning",
            });
            return;
        }

        this.state.saving = true;
        try {
            if (!(await this._ensureOrderSyncAllowed(orderId))) {
                return;
            }
            await this.env.saveSpreadsheet();

            const sheetId = this.env.model.getters.getActiveSheetId();
            const listId = this.listId;

            const listDataSource = this.env.model.getters.getListDataSource(listId);
            if (listDataSource && !listDataSource.isReady()) {
                await listDataSource.load();
            }

            // ---- 1. Scan rows ----
            const existingUpdates = {};
            const newRows = [];
            const maxRow = this.env.model.getters.getNumberRows(sheetId);
            let emptyStreak = 0;

            for (let row = 1; row < maxRow && emptyStreak < 5; row++) {
                const rowData = this._readRow(sheetId, row);
                if (!rowData.hasData) {
                    emptyStreak++;
                    continue;
                }
                emptyStreak = 0;

                if (rowData.lineId) {
                    existingUpdates[rowData.lineId] = {
                        values: rowData.values,
                        productName: rowData.productName,
                    };
                } else if (
                    rowData.productName ||
                    Object.keys(rowData.values).length > 0
                ) {
                    newRows.push({
                        values: rowData.values,
                        productName: rowData.productName,
                    });
                }
            }

            // ---- 2. Resolve product names to IDs ----
            const allProductNames = new Set();
            for (const data of Object.values(existingUpdates)) {
                if (data.productName) {
                    allProductNames.add(data.productName);
                }
            }
            for (const row of newRows) {
                if (row.productName) {
                    allProductNames.add(row.productName);
                }
            }

            const productMap = {};
            const names = [...allProductNames];
            const foundIds = await Promise.all(
                names.map((name) => this._findProduct(name))
            );
            names.forEach((name, i) => {
                if (foundIds[i]) {
                    productMap[name] = foundIds[i];
                }
            });

            // ---- 3. Handle missing products ----
            const missingProducts = [...allProductNames].filter((n) => !productMap[n]);

            if (missingProducts.length > 0) {
                const confirmed = await this._confirmCreateProducts(missingProducts);
                if (!confirmed) {
                    this.notification.add(_t("Sync cancelled"), {type: "info"});
                    return;
                }
                const createdIds = await this.orm.create(
                    "product.product",
                    missingProducts.map((name) => ({name}))
                );
                missingProducts.forEach((name, i) => {
                    productMap[name] = createdIds[i];
                });
            }

            // ---- 4. Build ORM commands ----
            const writeCommands = [];

            for (const [lineId, data] of Object.entries(existingUpdates)) {
                const vals = {...data.values};
                if (data.productName && productMap[data.productName]) {
                    vals.product_id = productMap[data.productName];
                }
                if (Object.keys(vals).length > 0) {
                    writeCommands.push([1, parseInt(lineId), vals]);
                }
            }

            for (const row of newRows) {
                const vals = {...row.values};
                if (row.productName && productMap[row.productName]) {
                    vals.product_id = productMap[row.productName];
                }
                if (Object.keys(vals).length > 0) {
                    writeCommands.push([0, 0, vals]);
                }
            }

            // ---- 5. Execute ----
            if (writeCommands.length) {
                await this.orm.call(
                    "sale.order",
                    "action_sync_spreadsheet_order_lines",
                    [[orderId], writeCommands]
                );

                const updated = writeCommands.filter((c) => c[0] === 1).length;
                const created = writeCommands.filter((c) => c[0] === 0).length;
                const parts = [];
                if (updated) {
                    parts.push(_t("%s line(s) updated", updated));
                }
                if (created) {
                    parts.push(_t("%s line(s) created", created));
                }
                this.notification.add(parts.join(", "), {type: "success"});
            } else {
                this.notification.add(_t("No values to sync"), {type: "info"});
            }
        } catch (e) {
            this.notification.add(
                _t("Error syncing: %s", this._getRpcErrorMessage(e)),
                {type: "danger"}
            );
        } finally {
            this.state.saving = false;
        }
    }
}

sidePanelRegistry.add("FieldSyncPanel", {
    title: _t("Field Sync"),
    Body: FieldSyncPanel,
});
