import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useExternalListener, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { isDisplayStandalone } from "@web/core/browser/feature_detection";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { deserializeDate, deserializeDateTime, formatDate, formatDateTime } from "@web/core/l10n/dates";
import { normalize } from "@web/core/l10n/utils";
import { registry } from "@web/core/registry";
// Resolución especial para móvil: the breakpoints of the screen
import { SIZES } from "@web/core/ui/ui_service";
import { useBus, useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { imageUrl } from "@web/core/utils/urls";
import { parseFloat } from "@web/views/fields/parsers";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { applyNumpadKey, evalNumpadExpression, isNumpadExpression, TouchNumpad } from "./touch_numpad";
import { localization } from "@web/core/l10n/localization";

const MODEL = "mercas.touch";
// Sent by the server when the stock of some lots changes
const LOTS_CHANGED = "mercas_touch/lots_changed";
// The fields of the line being added or changed, as Enter goes through them (see
// entryFieldOrder), and the inputs of each one
const ENTRY_INPUTS = {
    gross: ".o_mercas_touch_entry .o_mercas_touch_gross",
    qty: ".o_mercas_touch_entry .o_mercas_touch_qty",
    price: ".o_mercas_touch_entry .o_mercas_touch_price",
    boxQty: ".o_mercas_touch_entry .o_mercas_touch_box_qty_input",
    boxProduct: ".o_mercas_touch_entry .o_mercas_touch_box_search",
    lotName: ".o_mercas_touch_entry .o_mercas_touch_lot_name",
    salePrice: ".o_mercas_touch_entry .o_mercas_touch_sale_price",
    country: ".o_mercas_touch_entry .o_mercas_touch_origin_country",
    state: ".o_mercas_touch_entry .o_mercas_touch_origin_state",
    firm: ".o_mercas_touch_entry .o_mercas_touch_firm",
};
// Fields of the line not written with the keypad: Enter goes through them, the keypad stays
const ENTRY_NOT_KEYPAD = ["boxProduct", "country", "state", "firm"];
const ARROW_KEYS = { ArrowUp: true, ArrowDown: true, ArrowLeft: true, ArrowRight: true };
const ENTRY_FLOAT_FIELDS = ["gross", "qty", "price", "salePrice"];
// Fields of numbers with decimals: quantities, weights, prices and amounts
const DECIMAL_INPUTS = 'input[inputmode="decimal"], .o_mercas_touch_price_edit_input';
// Sent by Discuss: a new message in a channel of the user, and the read messages
const NEW_MESSAGE = "discuss.channel/new_message";
const MAIL_RECORDS = "mail.record/insert";
// Time to wait before reloading the dashboard after the messages change
const MESSAGES_DELAY = 1000;
// Time to wait after typing before searching partners or lots
const SEARCH_DELAY = 300;
// Resolución especial para móvil: whether the catalog is hidden, remembered on the device
const HIDE_CATALOG_KEY = "mercas_touch.hide_catalog";
const HIDE_HOME_KEY = "mercas_touch.hide_home";
// Kinds of box listed at once while looking for the box of a line
const BOX_CHOICES_LIMIT = 50;
// The home dashboard is also reloaded on its own, for the sales made in the backend
const HOME_REFRESH_DELAY = 5 * 60 * 1000;

/** A random uuid (version 4); crypto.randomUUID() needs HTTPS, the counter may use plain HTTP. */
function randomUuid() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * Counter screen of the wholesale market, made for touch screens.
 *
 * One mode per task, also opened with the function keys: F1 sale, F2 purchase, F3 boxes,
 * F4 lots and F5 payments. Each operation is a single call to the server, which runs the flows
 * of mercas_base; it carries a uuid so that a double tap or a retry doesn't duplicate it.
 * The screen works online only: the stock of the lots must be the real one.
 */
export class TouchScreen extends Component {
    static template = "mercas_touch.TouchScreen";
    static components = { TouchNumpad };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.pwa = useService("pwa");
        // Resolución especial para móvil: the screen size (ui.isSmall, ui.size), followed when
        // it is turned or resized
        this.ui = useState(useService("ui"));
        // The home menu of Odoo Enterprise; Community has none
        this.homeMenu = "home_menu" in this.env.services ? useService("home_menu") : null;
        this.modes = [
            { key: "sale", fkey: "F1", name: _t("Sale"), icon: "fa-shopping-basket", help: _t("Sell and deliver with lots and boxes") },
            { key: "purchase", fkey: "F2", name: _t("Purchase"), icon: "fa-truck", help: _t("Buy and receive, with new lots and labels") },
            { key: "boxes", fkey: "F3", name: _t("Boxes"), icon: "fa-cubes", help: _t("Boxes given back by customers or to suppliers") },
            { key: "lots", fkey: "F4", name: _t("Lots"), icon: "fa-th-large", help: _t("Stock of the lots, scrap and settlement") },
            { key: "payment", fkey: "F5", name: _t("Payments"), icon: "fa-money", help: _t("Collect the invoices of a customer") },
            { key: "labels", fkey: "F6", name: _t("Damaged label"), icon: "fa-tags", help: _t("Reprint the labels of a lot"), short: _t("Labels") },
        ];
        this.state = useState({
            // false (main menu) or the key of a mode
            mode: false,
            data: null,
            // Dashboard of the main menu (see loadHome)
            home: null,
            sending: false,
            // Sale and purchase: the drafts to resume, or the partner of a new one
            drafts: [],
            draftSearch: "",
            // "draft" (in progress), "to_invoice" or "all"
            draftFilter: "draft",
            choosingCustomer: false,
            // Draft of the sale or purchase being made, saved after each change: { id, name }
            order: null,
            // false, "saving", "saved" or "error"
            saveState: false,
            // Partner of the sale, purchase, boxes or payment, with their debt, risk and boxes
            partnerSearch: "",
            partners: [],
            partner: null,
            // Catalog of the sale and the purchase
            categoryId: false,
            productSearch: "",
            // Product being added: its lots, then the line being edited
            product: null,
            lots: [],
            lotsLoading: false,
            entry: null,
            // Lines of the sale or the purchase
            lines: [],
            // States of origin of each country, loaded when the country is chosen
            originStates: {},
            // Price of a line being changed from the ticket: { key, value, fresh }
            priceEdit: null,
            // Pallets of the sale being arranged (see openPallets)
            pallets: null,
            // Resolución especial para móvil: catalog hidden to reach the ticket and its buttons
            hideCatalog: this.loadHideCatalog(),
            // The dashboard of the main menu can be hidden on each device (see onToggleHome)
            hideHome: this.loadHideHome(),
            // Result of the last operation, shown until the next one starts
            done: null,
            // Boxes
            boxDirection: "return",
            boxQty: {},
            boxListSearch: "",
            // Boxes given back by a customer: "compensate" (a credit for the next invoices) or
            // "pay" (paid now from boxJournalId); chosen when they give them back
            boxSettle: false,
            boxJournalId: false,
            // Lots
            lotSearch: "",
            lotList: [],
            lotSelection: {},
            scrap: null,
            // Sale price of a lot being changed on the screen of the lots: { lot, price }
            lotPrice: null,
            // Damaged label: the lots found by the code scanned or typed
            labelSearch: "",
            labelLots: [],
            // Payments
            invoiceIds: [],
            // Credits of the customer applied first to the invoices chosen
            creditIds: [],
            amount: "",
            journalId: false,
            memo: "",
        });
        this.searchTimeout = null;
        // Saves of the draft being made, one after the other; a new operation starts a
        // new token, so that a late answer doesn't change it
        this.saveToken = {};
        this.saveDirty = false;
        this.savePromise = null;
        // The price field is focused and selected each time the editor moves to a line, so
        // that a keyboard or a scale replaces the price
        this.focusPrice = false;
        // The code of a damaged label is typed or scanned as soon as its screen opens
        this.focusLabelSearch = false;
        // An element to focus once the screen is drawn again (see focusAfterRender)
        this.pendingFocus = null;
        // The screen shown last, to give the focus to the first field of a new one, and the
        // last mode opened, focused back in the main menu
        this.screenKey = null;
        this.lastMode = null;
        // The lot scrapped or priced, focused back in the list of lots
        this.lastLotId = null;
        onMounted(() => this.focusFirstField());
        onPatched(() => {
            this.focusFirstField();
            if (this.focusPrice) {
                this.focusPrice = false;
                const input = document.querySelector(".o_mercas_touch_price_edit_input");
                input?.focus();
                input?.select();
            }
            if (this.pendingFocus) {
                // The first of the selectors found (or of the elements given by a function)
                const element = this.pendingFocus
                    .map((selector) => (typeof selector === "function" ? selector() : document.querySelector(selector)))
                    .find(Boolean);
                element?.focus();
                element?.select?.();
                this.pendingFocus = null;
            }
            if (this.focusLabelSearch) {
                this.focusLabelSearch = false;
                const input = document.querySelector(".o_mercas_touch_label_search");
                input?.focus();
                input?.select();
            }
        });

        onWillStart(async () => {
            const [data] = await Promise.all([this.orm.call(MODEL, "get_screen_data", []), this.loadHome()]);
            this.state.data = data;
            this.state.journalId = this.state.data.journals[0]?.id || false;
        });
        this.homeInterval = browser.setInterval(() => {
            if (!this.state.mode) {
                this.loadHome();
            }
        }, HOME_REFRESH_DELAY);

        // F1-F5 open the modes, Escape goes back. Captured on the window, before the shortcuts
        // of mercas_keys, which open the backend lists with the same keys.
        useExternalListener(window, "keydown", (ev) => this.onKeydown(ev), { capture: true });
        // A scanner in keyboard mode: the code of a box label is the name of its lot
        useBus(useService("barcode").bus, "barcode_scanned", (ev) =>
            this.onBarcodeScanned(ev.detail.barcode)
        );
        // Sales and scraps made on other screens change the stock of the lots shown
        const bus = useService("bus_service");
        const onLotsChanged = (payload) => this.onLotsChanged(payload);
        bus.subscribe(LOTS_CHANGED, onLotsChanged);
        // The messages of the dashboard, read or arrived on any screen (or in the top bar)
        const onNewMessage = () => this.onMessagesChanged();
        const onMailRecords = (payload) => {
            if (payload?.["discuss.channel.member"]) {
                this.onMessagesChanged();
            }
        };
        bus.subscribe(NEW_MESSAGE, onNewMessage);
        bus.subscribe(MAIL_RECORDS, onMailRecords);
        onWillUnmount(() => {
            bus.unsubscribe(LOTS_CHANGED, onLotsChanged);
            bus.unsubscribe(NEW_MESSAGE, onNewMessage);
            bus.unsubscribe(MAIL_RECORDS, onMailRecords);
            browser.clearTimeout(this.messagesTimeout);
            browser.clearTimeout(this.searchTimeout);
            browser.clearInterval(this.homeInterval);
        });
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    onKeydown(ev) {
        const mode = this.modes.find((mode) => mode.fkey === ev.key);
        if (this.isNumpadDecimalPoint(ev)) {
            // The point of the numeric keypad of the keyboard is the decimal comma, in Spain
            ev.preventDefault();
            const input = ev.target;
            input.setRangeText(localization.decimalPoint, input.selectionStart, input.selectionEnd, "end");
            input.dispatchEvent(new Event("input", { bubbles: true }));
        } else if (mode) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.openMode(mode.key);
        } else if (ev.key === "Escape" && this.state.entry && this.state.entry.boxSearch !== null) {
            // Escape closes the list of boxes, it doesn't leave the line
            ev.preventDefault();
            ev.stopImmediatePropagation();
            document.activeElement?.blur();
        } else if (ev.key === "F8" && this.isOrderScreen()) {
            // F8: to the ticket, to change or remove its lines (see onTicketKeydown)
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.focusTicket();
        } else if (ev.key === "F9" && this.canOpenPallets()) {
            // F9: the pallets of the sale
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.onOpenPallets();
        } else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && !document.querySelector(".modal")) {
            // Ctrl+Enter: the button that ends what is being done (sell, purchase, save the
            // pallets, print or send), from anywhere on the screen
            const button = this.mainActionButton();
            const settle = !button && this.boxesToSettle();
            if (button || settle) {
                ev.preventDefault();
                ev.stopImmediatePropagation();
                // Boxes given back still to settle: the focus to how to settle them, not chosen
                button ? button.click() : settle.focus();
            }
        } else if (ev.key === "Escape" && this.closeDonePanel()) {
            // Escape closes the printing, the sending or the bills, not the screen
            ev.preventDefault();
            ev.stopImmediatePropagation();
        } else if (ev.key in ARROW_KEYS && this.state.done && !this.state.pallets &&
                   document.activeElement === document.body && !document.querySelector(".modal")) {
            // The focus lost (its button gone, as Create invoice once invoiced): the main button
            ev.preventDefault();
            this.focusDoneAction();
        } else if (ev.key === "Escape" && this.state.pallets?.selected && !document.querySelector(".modal")) {
            // Escape leaves the boxes chosen to move, not the pallets
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.state.pallets.selected = null;
            this.focusAfterRender(".o_mercas_touch_pallet_chip");
        } else if (ev.key === "Escape" && this.state.mode && !document.querySelector(".modal")) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.onBack();
        }
    }

    /** The decimal key of the numeric keypad of the keyboard in a field of numbers, when it
     * doesn't write the decimal point of the user (a point, with a comma as decimal point). */
    isNumpadDecimalPoint(ev) {
        const input = ev.target;
        return (
            ev.code === "NumpadDecimal" &&
            ev.key !== localization.decimalPoint &&
            !ev.ctrlKey && !ev.metaKey && !ev.altKey &&
            input instanceof HTMLInputElement &&
            !input.readOnly &&
            input.matches(DECIMAL_INPUTS)
        );
    }

    /** The sale or the purchase being made, with its catalog and its ticket. */
    isOrderScreen() {
        const state = this.state;
        return this.hasDrafts() && Boolean(state.partner) && !state.pallets && !state.done;
    }

    /** The pallets of the sale can be opened (F9): from the sale with boxes, or from the sale done. */
    canOpenPallets() {
        const state = this.state;
        if (state.sending || state.pallets || state.mode !== "sale") {
            return false;
        }
        if (state.done) {
            return state.done.kind === "sale" && state.done.state === "sale" && Boolean(state.done.box_count);
        }
        return this.isOrderScreen() && !state.entry && this.linesBoxes() > 0;
    }

    /** The lines of the ticket can be reached (F8). */
    canFocusTicket() {
        return this.isOrderScreen() && this.state.lines.length > 0;
    }

    /** The boxes of the partner of the operation done: given back by the customer of a sale
     * (`direction` "return") or to the supplier of a purchase ("deliver"). */
    async onOpenBoxes(direction) {
        const partnerId = this.state.partner.id;
        await this.flushSave();
        this.resetOperation();
        this.state.mode = "boxes";
        this.state.partner = await this.orm.call(MODEL, "get_partner_info", [partnerId]);
        this.state.boxDirection = direction;
    }

    /** The button pressed by Ctrl+Enter on the screen shown, if it can be pressed. */
    mainActionButton() {
        const state = this.state;
        let selector = null;
        if (state.pallets) {
            selector = ".o_mercas_touch_pallets_save";
        } else if (state.done?.printPanel) {
            selector = ".o_mercas_touch_print_send";
        } else if (state.done?.mailPanel) {
            selector = ".o_mercas_touch_mail_send";
        } else if (this.isOrderScreen()) {
            selector = state.mode === "sale" ? ".o_mercas_touch_sell" : ".o_mercas_touch_purchase";
        } else if (state.mode === "boxes" && state.partner && !state.done) {
            selector = ".o_mercas_touch_move_boxes";
        } else if (state.mode === "payment" && state.partner && !state.done) {
            selector = ".o_mercas_touch_register_payment";
        }
        return selector && document.querySelector(`${selector}:not(:disabled)`);
    }

    /** How to settle the boxes given back, when some are typed and it isn't chosen yet: the
     * first choice, or the first journal to pay them with; null otherwise. */
    boxesToSettle() {
        const state = this.state;
        if (state.mode !== "boxes" || !state.partner || state.done || state.boxDirection !== "return" ||
            !this.boxTotal() || this.boxesReady()) {
            return null;
        }
        return document.querySelector(state.boxSettle === "pay"
            ? ".o_mercas_touch_box_journal"
            : ".o_mercas_touch_box_settle .btn:not(:disabled)");
    }

    /** Close the printing, the sending or the bills of the screen of an operation done, back
     * to their button; false if none is open. */
    closeDonePanel() {
        const done = this.state.done;
        if (!done || this.state.pallets || document.querySelector(".modal")) {
            return false;
        }
        if (done.printPanel) {
            done.printPanel = null;
            this.focusAfterRender(".o_mercas_touch_print");
        } else if (done.mailPanel) {
            done.mailPanel = null;
            this.focusAfterRender(".o_mercas_touch_mail");
        } else if (done.invoiceList) {
            done.invoiceList = null;
            this.focusAfterRender(".o_mercas_touch_purchase_invoices");
        } else {
            return false;
        }
        return true;
    }

    /**
     * The arrows over rows of buttons: left and right in the row, up and down to the row
     * before or after, at the same place (or its last button).
     *
     * @param {KeyboardEvent} ev
     * @param {Element[]} rows
     * @param {(row: Element) => Element[]} items the buttons of a row that can be focused
     * @returns {boolean|string} true when the focus moved; the key when there is nothing
     *      further that way (for the caller to go out of the rows); false if not handled
     */
    moveInRows(ev, rows, items) {
        if (!(ev.key in ARROW_KEYS)) {
            return false;
        }
        const row = rows.find((other) => other.contains(ev.target));
        const rowItems = row ? items(row) : [];
        const index = rowItems.indexOf(ev.target);
        if (index < 0) {
            return false;
        }
        ev.preventDefault();
        let next = null;
        if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
            next = rowItems[index + (ev.key === "ArrowRight" ? 1 : -1)];
        } else {
            const other = rows[rows.indexOf(row) + (ev.key === "ArrowDown" ? 1 : -1)];
            const otherItems = other ? items(other) : [];
            next = otherItems[Math.min(index, otherItems.length - 1)];
        }
        if (next) {
            next.focus();
            return true;
        }
        return ev.key;
    }

    async openMode(mode) {
        if (this.state.sending) {
            return;
        }
        await this.flushSave();
        this.resetOperation();
        this.state.partner = null;
        this.state.partnerSearch = "";
        this.state.partners = [];
        this.state.mode = mode;
        if (mode === "sale") {
            // Lots received or sold elsewhere since the screen was opened
            this.loadSellableProducts();
        }
        if (mode === "lots") {
            await this.loadLots();
        } else if (mode === "labels") {
            this.state.labelSearch = "";
            this.focusLabelSearch = true;
            await this.loadLabelLots();
        } else if (this.hasDrafts()) {
            await this.loadDrafts();
        } else {
            await this.searchPartners();
        }
    }

    resetOperation() {
        this.state.product = null;
        this.state.lots = [];
        this.state.entry = null;
        this.state.lines = [];
        this.state.priceEdit = null;
        this.state.pallets = null;
        this.state.done = null;
        this.state.categoryId = false;
        this.state.productSearch = "";
        this.state.boxQty = {};
        this.state.boxListSearch = "";
        this.state.boxDirection = "return";
        // The boxes shown: "stock" (those the partner holds, or we hold of them), "all", or
        // null: stock when there is any (see boxFilter)
        this.state.boxFilter = null;
        this.state.boxSettle = false;
        this.state.invoiceIds = [];
        this.state.creditIds = [];
        this.state.amount = "";
        this.state.memo = "";
        this.state.scrap = null;
        this.state.lotPrice = null;
        this.state.lotSelection = {};
        this.state.order = null;
        this.state.saveState = false;
        this.state.choosingCustomer = false;
        this.operationUuid = null;
        this.saveToken = {};
        this.saveDirty = false;
        this.savePromise = null;
    }

    async onBack() {
        if (this.state.sending) {
            return;
        }
        if (this.state.pallets) {
            this.onClosePallets();
        } else if (this.state.priceEdit) {
            this.onClosePriceEdit();
        } else if (this.state.entry) {
            this.state.entry = null;
            if (!this.state.lots.length) {
                this.state.product = null;
            }
        } else if (this.state.product) {
            this.state.product = null;
            this.state.lots = [];
        } else if (this.state.scrap) {
            this.state.scrap = null;
        } else if (this.state.lotPrice) {
            this.state.lotPrice = null;
        } else if (this.hasDrafts() && (this.state.partner || this.state.choosingCustomer)) {
            // The draft is saved: back to the list, to resume it or another one later
            await this.flushSave();
            this.resetOperation();
            this.state.partner = null;
            await this.loadDrafts();
        } else if (this.state.partner && !this.state.done && this.hasWork()) {
            this.notification.add(_t("Finish or clear the current operation first."), { type: "warning" });
        } else if (this.state.partner) {
            this.resetOperation();
            this.state.partner = null;
            this.searchPartners();
        } else {
            this.state.mode = false;
            this.loadHome();
        }
    }

    // ------------------------------------------------------------------
    // Home dashboard
    // ------------------------------------------------------------------

    /** Sales of the day, products on promotion, lots that expire or have no date, pending sales. */
    async loadHome() {
        if (this.state.hideHome) {
            return;
        }
        try {
            this.state.home = await this.orm.silent.call(MODEL, "get_home_dashboard", []);
        } catch {
            // Only informative: the menu works without it, it is loaded again later
        }
    }

    homeSalesText() {
        const { count, boxes } = this.state.home.sales;
        const sales = count === 1 ? _t("1 sale") : _t("%s sales", count);
        return `${sales} · ${boxes === 1 ? _t("1 box") : _t("%s boxes", boxes)}`;
    }

    homeDraftsText() {
        const drafts = this.state.home.pending.drafts;
        return drafts === 1 ? _t("1 quotation in progress") : _t("%s quotations in progress", drafts);
    }

    get homeShowLabel() {
        return _t("Show the dashboard");
    }

    get homeHideLabel() {
        return _t("Hide the dashboard");
    }

    homeToDeliverText() {
        const sales = this.state.home.pending.to_deliver;
        return sales === 1 ? _t("1 sale to deliver") : _t("%s sales to deliver", sales);
    }

    /** Class of the badge of the days left of a lot: expired, expires today or soon. */
    expiryClass(lot) {
        if (lot.days_left < 0) {
            return "text-bg-danger";
        }
        return lot.days_left === 0 ? "text-bg-warning" : "text-bg-info";
    }

    expiryText(lot) {
        if (lot.days_left < 0) {
            return _t("Expired");
        }
        if (lot.days_left === 0) {
            return _t("Today");
        }
        return lot.days_left === 1 ? _t("Tomorrow") : _t("In %s days", lot.days_left);
    }

    onMessagesChanged() {
        if (this.state.mode || this.state.hideHome) {
            return;
        }
        browser.clearTimeout(this.messagesTimeout);
        this.messagesTimeout = browser.setTimeout(() => this.loadHome(), MESSAGES_DELAY);
    }

    get markReadLabel() {
        return _t("Mark as read");
    }

    messageIcon(message) {
        return { chat: "fa-user", group: "fa-users" }[message.type] || "fa-hashtag";
    }

    /** The time of a message of today, else its date. */
    formatMessageDate(value) {
        const date = deserializeDateTime(value);
        return date.hasSame(luxon.DateTime.now(), "day")
            ? date.toLocaleString(luxon.DateTime.TIME_SIMPLE)
            : formatDate(date);
    }

    /** The conversation in a chat window, to read it all and answer. */
    async onHomeMessage(message) {
        const store = this.env.services["mail.store"];
        if (!store) {
            return;
        }
        const thread = await store.Thread.getOrFetch({ model: "discuss.channel", id: message.id });
        thread?.open({ focus: true, bypassCompact: true });
    }

    async onMarkMessagesRead(message) {
        await this.orm.call(MODEL, "mark_messages_read", [message ? [message.id] : null]);
        await this.loadHome();
        // On with the keyboard: the next message, or else the dashboard
        this.focusAfterRender(".o_mercas_touch_home_message button", ".o_mercas_touch_home_dashboard button");
    }

    /** The form of a lot of the dashboard, to change its data or set its expiry date. */
    onHomeLot(lot) {
        this.onOpenLot(lot, () => this.loadHome());
    }

    hasWork() {
        return (
            this.state.lines.length > 0 ||
            Object.values(this.state.boxQty).some((qty) => qty > 0) ||
            this.state.invoiceIds.length > 0
        );
    }

    onClearOperation() {
        if (this.hasDrafts() && this.state.order) {
            this.onCancelDraft();
            return;
        }
        const partner = this.state.partner;
        this.resetOperation();
        this.state.partner = partner;
    }

    clearTitle() {
        if (!this.hasDrafts() || !this.state.order) {
            return _t("Clear");
        }
        return this.state.mode === "sale" ? _t("Cancel the quotation") : _t("Cancel the purchase");
    }

    draftSearchPlaceholder() {
        return this.state.mode === "sale"
            ? _t("Search a quotation or a customer")
            : _t("Search a purchase or a supplier");
    }

    /** The sale and the purchase are saved as drafts while they are made. */
    hasDrafts() {
        return this.state.mode === "sale" || this.state.mode === "purchase";
    }

    // ------------------------------------------------------------------
    // Focus and Enter in the searches
    // ------------------------------------------------------------------

    /** What identifies the screen shown: when it changes, its first field gets the focus. */
    currentScreenKey() {
        const state = this.state;
        return JSON.stringify([
            state.mode, state.partner?.id || false, state.choosingCustomer, state.product?.id || false,
            // The lots of the product arrive after it is chosen
            state.product ? state.lots.length : 0,
            state.entry ? [state.entry.product.id, state.entry.line?.key || false] : false,
            Boolean(state.priceEdit), Boolean(state.pallets), Boolean(state.scrap), Boolean(state.lotPrice),
            Boolean(state.done),
        ]);
    }

    /**
     * The first field of a screen that opens gets the focus (the search of the quotations, of
     * the customers or of the products, the gross weight or the quantity of the line...), to
     * go on with the keyboard. Not on a touch screen: it would open the keyboard of the device.
     */
    focusFirstField() {
        const key = this.currentScreenKey();
        if (key === this.screenKey) {
            return;
        }
        this.screenKey = key;
        // The price editor focuses its own field
        if (this.state.priceEdit || browser.matchMedia?.("(pointer: coarse)").matches) {
            return;
        }
        // Or, in the lots of a product, the first lot that can be sold (see onGridKeydown)
        if (!this.state.mode) {
            // The main menu: the mode left (back from it), or the first one
            const modes = document.querySelector(".o_mercas_touch_home_menu");
            const mode = (this.lastMode && modes?.querySelector(`.o_mercas_touch_mode_${this.lastMode}`)) ||
                modes?.querySelector(".o_mercas_touch_mode");
            mode?.focus();
            return;
        }
        this.lastMode = this.state.mode;
        // The pallets: the first chip of boxes, those not on a pallet first (see onPalletsKeydown)
        if (this.state.pallets) {
            this.focusPalletChip();
            return;
        }
        // An operation done: its main button, New or Back to the list (see focusDoneAction)
        if (this.state.done) {
            this.focusDoneAction();
            return;
        }
        // A line with attributes (quality, size): they are chosen first (see onAttributeValueKeydown)
        if (this.state.entry && this.entryAttributes().length) {
            this.attributeButton(document.querySelector(".o_mercas_touch_entry .o_mercas_touch_attribute"))?.focus();
            return;
        }
        // Collecting, the first invoice to choose (see onPaymentCheckKeydown); without any, the amount
        const invoice = this.state.mode === "payment" && document.querySelector(
            ".o_mercas_touch_body .o_mercas_touch_invoice input, .o_mercas_touch_body .o_mercas_touch_credit input"
        );
        if (invoice) {
            invoice.focus();
            return;
        }
        // Back to the lots from scrapping one or changing its price, the lot left
        const lotList = this.state.mode === "lots" && !this.state.scrap && !this.state.lotPrice;
        const lot = lotList && this.lastLotId && document.querySelector(
            `.o_mercas_touch_body .o_mercas_touch_lot_card[data-lot-id="${this.lastLotId}"] .o_mercas_touch_lot_select`
        );
        if (lotList) {
            this.lastLotId = null;
        }
        if (lot) {
            lot.focus();
            return;
        }
        const field = document.querySelector(".o_mercas_touch_body")?.querySelector(
            "input:not([type=checkbox]):not([type=radio]):not([readonly]):not([disabled]), " +
            ".o_mercas_touch_lot:not(:disabled)"
        );
        if (field && document.activeElement !== field) {
            field.focus();
            field.select?.();
        }
    }

    /** The value after (step 1) or before (-1) `value` in `values`, going round. */
    cycle(values, value, step) {
        const index = values.indexOf(value);
        return values[(Math.max(index, 0) + step + values.length) % values.length];
    }

    /**
     * Enter in a search chooses the only record found (`records`, the result of the search);
     * with several, it asks to narrow the search. With none it does nothing: the code may be a
     * label scanned, handled by the scanner.
     */
    chooseOnEnter(records, choose, exact = null) {
        const record = records.length === 1 ? records[0] : exact;
        if (record) {
            choose(record);
        } else if (records.length > 1) {
            this.notification.add(_t("%s results: keep typing until only one is left.", records.length), {
                type: "info",
            });
        }
    }

    async onDraftSearchKeydown(ev) {
        if (ev.key === "PageDown" || ev.key === "PageUp") {
            // The filter of the quotations: In progress, To invoice, All
            ev.preventDefault();
            const keys = this.draftFilters.map((filter) => filter.key);
            await this.onDraftFilter(this.cycle(keys, this.state.draftFilter, ev.key === "PageDown" ? 1 : -1));
            return;
        }
        if (this.focusFirstTile(ev, ".o_mercas_touch_draft") || ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        browser.clearTimeout(this.searchTimeout);
        await this.loadDrafts();
        this.chooseOnEnter(this.state.drafts, (draft) => this.onResumeDraft(draft));
    }

    async onPartnerSearchKeydown(ev) {
        if (this.focusFirstTile(ev, ".o_mercas_touch_partner") || ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        browser.clearTimeout(this.searchTimeout);
        await this.searchPartners();
        this.chooseOnEnter(this.state.partners, (partner) => this.onSelectPartner(partner.id));
    }

    onProductSearchKeydown(ev) {
        if (ev.key === "PageDown" || ev.key === "PageUp") {
            // The category of the catalog, All first
            ev.preventDefault();
            const ids = [false, ...this.categories().map((category) => category.id)];
            this.onSelectCategory(this.cycle(ids, this.state.categoryId, ev.key === "PageDown" ? 1 : -1));
            return;
        }
        if (this.focusFirstTile(ev, ".o_mercas_touch_product") || ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        const products = this.visibleProducts();
        // The internal reference or the barcode typed whole chooses its product
        const code = normalize(this.state.productSearch.trim());
        const exact = products.filter(
            (product) => code && [product.default_code, product.barcode].some((value) => normalize(value || "") === code)
        );
        this.chooseOnEnter(products, (product) => this.onSelectProduct(product), exact.length === 1 ? exact[0] : null);
    }

    async onLotSearchKeydown(ev) {
        if (this.focusFirstTile(ev, ".o_mercas_touch_lot_select") || ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        browser.clearTimeout(this.searchTimeout);
        await this.loadLots();
        this.chooseOnEnter(this.state.lotList, (lot) => {
            this.state.lotSelection = { ...this.state.lotSelection, [lot.id]: true };
        });
    }

    // ------------------------------------------------------------------
    // Drafts: the sale or purchase being made is saved as a quotation or a request for
    // quotation in draft
    // ------------------------------------------------------------------

    onDraftSearchInput(ev) {
        this.state.draftSearch = ev.target.value;
        browser.clearTimeout(this.searchTimeout);
        this.searchTimeout = browser.setTimeout(() => this.loadDrafts(), SEARCH_DELAY);
    }

    async loadDrafts() {
        const mode = this.state.mode;
        const drafts = await this.orm.call(MODEL, "get_drafts", [
            mode,
            this.state.draftSearch,
            this.state.draftFilter,
        ]);
        if (this.state.mode === mode && !this.state.partner) {
            this.state.drafts = drafts;
        }
    }

    get draftFilters() {
        return [
            { key: "draft", name: _t("In progress") },
            { key: "to_invoice", name: _t("To invoice") },
            { key: "all", name: _t("All") },
        ];
    }

    async onDraftFilter(filter) {
        this.state.draftFilter = filter;
        await this.loadDrafts();
    }

    async onNewDraft() {
        this.resetOperation();
        this.state.choosingCustomer = true;
        this.state.partnerSearch = "";
        await this.searchPartners();
    }

    async onResumeDraft(draft) {
        if (draft.state !== "draft") {
            await this.openOrderSummary(draft);
            return;
        }
        const [data, partner] = await Promise.all([
            this.orm.call(MODEL, "get_draft", [this.state.mode, draft.id]),
            this.orm.call(MODEL, "get_partner_info", [draft.partner_id]),
        ]);
        this.resetOperation();
        this.state.partner = partner;
        this.state.order = { id: data.id, name: data.name };
        this.state.saveState = "saved";
        this.state.lines = data.lines.map((line) => ({
            key: `line-${line.line_id}`,
            lineId: line.line_id,
            product: line.product,
            lot: line.lot || null,
            attributeValueIds: line.attribute_value_ids || [],
            qty: line.qty,
            price: line.price,
            boxQty: line.box_qty || 0,
            boxProductId: line.box_product_id || false,
            note: line.note || "",
            origNote: line.note || "",
            originCountryId: line.origin_country_id || false,
            originStateId: line.origin_state_id || false,
            firm: Boolean(line.firm),
            lotName: line.lot_name || "",
            salePrice: line.sale_price || 0,
        }));
    }

    /** A confirmed sale or purchase, to look it up, print it or invoice it. */
    async openOrderSummary(draft) {
        const mode = this.state.mode;
        const [summary, partner] = await Promise.all([
            this.orm.call(MODEL, "get_order_summary", [mode, draft.id]),
            this.orm.call(MODEL, "get_partner_info", [draft.partner_id]),
        ]);
        this.resetOperation();
        this.state.partner = partner;
        this.state.done = { ...summary, reviewing: true };
    }

    async refreshOrderSummary() {
        const done = this.state.done;
        if (!done) {
            return;
        }
        const summary = await this.orm.call(MODEL, "get_order_summary", [done.kind, done.id]);
        // The bills listed change as well: posted (to print) or deleted
        const invoices = done.invoiceList && await this.orm.call(MODEL, "get_purchase_invoices", [done.id]);
        if (this.state.done === done) {
            Object.assign(done, summary);
            if (invoices) {
                done.invoiceList = invoices.length ? invoices : null;
            }
        }
        await this.reloadPartner();
    }

    onCancelDraft() {
        const order = this.state.order;
        const mode = this.state.mode;
        this.dialog.add(ConfirmationDialog, {
            title: this.clearTitle(),
            body: _t("%s will be cancelled.", order.name),
            confirmLabel: this.clearTitle(),
            cancelLabel: _t("Keep it"),
            confirm: async () => {
                await this.flushSave();
                await this.orm.call(MODEL, "cancel_draft", [mode, order.id]);
                this.resetOperation();
                this.state.partner = null;
                await this.loadDrafts();
            },
            cancel: () => {},
        });
    }

    /** The lines of the sale or the purchase, as the server saves them in the draft. */
    linesPayload(lines) {
        const isPurchase = this.state.mode === "purchase";
        return lines.map((line) => ({
            ...(line.lineId ? { line_id: line.lineId } : {}),
            product_id: line.product.id,
            qty: line.qty,
            price_unit: line.price,
            ...(!isPurchase && line.lot ? { lot_id: line.lot.id } : {}),
            ...(!isPurchase ? { attribute_value_ids: line.attributeValueIds || [] } : {}),
            box_qty: line.boxQty || 0,
            ...(line.boxProductId ? { box_product_id: line.boxProductId } : {}),
            ...(isPurchase
                ? {
                      firm: line.firm,
                      sale_price: line.salePrice || 0,
                      ...(line.lotName ? { lot_name: line.lotName } : {}),
                      ...(line.originCountryId ? { origin_country_id: line.originCountryId } : {}),
                      ...(line.originStateId ? { origin_state_id: line.originStateId } : {}),
                  }
                : {}),
            // The text replaces the description under the product only when it changed
            ...(line.note !== (line.lineId ? line.origNote : "") ? { note: line.note } : {}),
        }));
    }

    /** Save the draft after a change of the lines, in the background. */
    scheduleSave() {
        if (!this.hasDrafts() || !this.state.partner || this.state.done) {
            return;
        }
        this.saveDirty = true;
        if (!this.savePromise) {
            const token = this.saveToken;
            this.savePromise = this.runSaves(token).finally(() => {
                if (token === this.saveToken) {
                    this.savePromise = null;
                }
            });
        }
    }

    async runSaves(token) {
        while (this.saveDirty && token === this.saveToken) {
            this.saveDirty = false;
            await this.saveDraft(token);
        }
    }

    async saveDraft(token) {
        const lines = [...this.state.lines];
        const notes = lines.map((line) => line.note);
        const vals = {
            uuid: this.newUuid(),
            partner_id: this.state.partner.id,
            ...(this.state.order ? { order_id: this.state.order.id } : {}),
            lines: this.linesPayload(lines),
        };
        this.state.saveState = "saving";
        let result;
        try {
            result = await this.orm.silent.call(MODEL, "save_draft", [this.state.mode, vals]);
        } catch (error) {
            if (token === this.saveToken) {
                this.state.saveState = "error";
                this.notification.add(error.data?.message || _t("The changes couldn't be saved."), {
                    title: _t("Not saved"),
                    type: "danger",
                });
            }
            return;
        }
        if (token !== this.saveToken) {
            return;
        }
        this.state.order = { id: result.id, name: result.name };
        lines.forEach((line, index) => {
            line.lineId = result.line_ids[index];
            line.origNote = notes[index];
        });
        this.state.saveState = this.saveDirty ? "saving" : "saved";
    }

    /** Wait for the saves in progress. */
    async flushSave() {
        while (this.savePromise) {
            await this.savePromise;
        }
    }

    onOdooHome() {
        if (this.homeMenu) {
            this.homeMenu.toggle(true);
        } else {
            browser.location.href = "/odoo";
        }
    }

    canInstall() {
        return this.pwa.isAvailable && !isDisplayStandalone();
    }

    onInstall() {
        this.pwa.show();
    }

    get currentMode() {
        return this.modes.find((mode) => mode.key === this.state.mode);
    }

    // ------------------------------------------------------------------
    // Partners
    // ------------------------------------------------------------------

    partnerKind() {
        return this.state.mode === "purchase" ? "supplier" : "customer";
    }

    partnerPlaceholder() {
        return this.partnerKind() === "supplier" ? _t("Search a supplier") : _t("Search a customer");
    }

    onPartnerSearchInput(ev) {
        this.state.partnerSearch = ev.target.value;
        browser.clearTimeout(this.searchTimeout);
        this.searchTimeout = browser.setTimeout(() => this.searchPartners(), SEARCH_DELAY);
    }

    async searchPartners() {
        const mode = this.state.mode;
        const partners = await this.orm.call(MODEL, "search_partners", [
            this.state.partnerSearch,
            this.partnerKind(),
        ]);
        if (this.state.mode === mode && !this.state.partner) {
            this.state.partners = partners;
        }
    }

    async onSelectPartner(partnerId) {
        this.resetOperation();
        this.state.partner = await this.orm.call(MODEL, "get_partner_info", [partnerId]);
        // In a sale or a purchase, the draft is created with its first line
        if (this.state.mode === "boxes") {
            this.state.boxDirection = this.state.partner.boxes.some((box) => box.supplier < 0) &&
                !this.state.partner.boxes.some((box) => box.customer > 0) ? "deliver" : "return";
        }
    }

    async reloadPartner() {
        const partner = this.state.partner;
        if (!partner) {
            return;
        }
        const info = await this.orm.call(MODEL, "get_partner_info", [partner.id]);
        // Only if the screen is still on that partner: back to the list meanwhile, it would
        // open a new operation for them
        if (this.state.partner === partner) {
            this.state.partner = info;
        }
    }

    debtTotal() {
        const debt = this.state.partner?.debt;
        return debt ? debt.overdue + debt.not_due : 0;
    }

    isOverLimit() {
        const partner = this.state.partner;
        if (!partner) {
            return false;
        }
        if (partner.risk) {
            return partner.risk.exception;
        }
        return partner.credit_limit > 0 && this.debtTotal() > partner.credit_limit;
    }

    /**
     * Credit used and granted to show in the risk warning, or null without a credit limit
     * (the risk can be exceeded by other limits, like the one of open invoices).
     */
    creditUsage() {
        const partner = this.state.partner;
        const [used, limit] = partner?.risk
            ? [partner.risk.total, partner.risk.limit]
            : [this.debtTotal(), partner?.credit_limit];
        return limit > 0 ? { used, limit } : null;
    }

    // ------------------------------------------------------------------
    // Catalog and lines of the sale and the purchase
    // ------------------------------------------------------------------

    isProductAllowed(product) {
        if (product.is_box) {
            return false;
        }
        if (this.state.mode === "purchase") {
            return product.purchase_ok;
        }
        // Tracked by lot, only with a lot to sell: otherwise it couldn't be sold
        return product.sale_ok && (!product.tracking || this.state.data.sellable_product_ids.includes(product.id));
    }

    /** Products with a lot to sell, after a sale, a purchase or a reception changed them. */
    async loadSellableProducts() {
        this.state.data.sellable_product_ids = await this.orm.call(MODEL, "get_sellable_product_ids", []);
    }

    categories() {
        const used = new Set(
            this.state.data.products.filter((p) => this.isProductAllowed(p)).map((p) => p.categ_id)
        );
        return this.state.data.categories.filter((category) => used.has(category.id));
    }

    visibleProducts() {
        const search = normalize(this.state.productSearch.trim());
        const products = this.state.data.products.filter(
            (product) =>
                this.isProductAllowed(product) &&
                (search
                    ? normalize(`${product.default_code} ${product.name} ${product.barcode}`).includes(search)
                    : !this.state.categoryId || product.categ_id === this.state.categoryId)
        );
        if (this.state.mode === "purchase") {
            return products;
        }
        // The products on promotion (favourite) first, in the order of the catalog
        return [...products.filter((p) => p.is_favorite), ...products.filter((p) => !p.is_favorite)];
    }

    boxProducts() {
        return this.state.data.products.filter((product) => product.is_box);
    }

    /** Kinds of box whose internal reference, name or barcode contains the text typed. */
    searchBoxes(text) {
        const search = normalize((text || "").trim());
        return this.boxProducts().filter(
            (box) => !search || normalize(`${box.default_code || ""} ${box.name} ${box.barcode || ""}`).includes(search)
        );
    }

    productById(productId) {
        return this.state.data.products.find((product) => product.id === productId);
    }

    productImage(product) {
        return imageUrl("product.product", product.id, "image_128", { unique: product.image_unique });
    }

    onSelectCategory(categoryId) {
        this.state.categoryId = categoryId;
        this.state.productSearch = "";
    }

    onProductSearchInput(ev) {
        this.state.productSearch = ev.target.value;
    }

    async onSelectProduct(product) {
        if (this.state.priceEdit) {
            if (!this.commitPrice()) {
                return;
            }
            this.state.priceEdit = null;
        }
        this.state.product = product;
        this.state.lots = [];
        if (this.state.mode === "sale" && product.tracking) {
            await this.loadProductLots();
            if (!this.state.lots.length) {
                this.notification.add(_t("%s has no lot with stock.", product.name), { type: "warning" });
            }
        } else {
            this.openEntry(product, null);
        }
    }

    async loadProductLots() {
        const product = this.state.product;
        this.state.lotsLoading = true;
        try {
            const lots = await this.orm.call(MODEL, "get_product_lots", [product.id]);
            if (this.state.product === product) {
                this.state.lots = lots;
            }
        } finally {
            this.state.lotsLoading = false;
        }
    }

    /** The modes of the main menu chosen with the keyboard: the arrows move between them, Enter
     * (on the button focused) opens it. */
    onModeMenuKeydown(ev) {
        // Right goes to the dashboard, when it is shown (see onHomeDashboardKeydown)
        const dashboard = ev.key === "ArrowRight" &&
            document.querySelector(".o_mercas_touch_home_dashboard button:not(:disabled)");
        if (dashboard) {
            ev.preventDefault();
            dashboard.focus();
            return;
        }
        const moves = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
        if (!(ev.key in moves)) {
            return;
        }
        ev.preventDefault();
        const modes = [...ev.currentTarget.querySelectorAll(".o_mercas_touch_mode")];
        const index = modes.indexOf(document.activeElement);
        const next = index < 0 ? 0 : (index + moves[ev.key] + modes.length) % modes.length;
        modes[next]?.focus();
    }

    /**
     * The dashboard of the main menu with the keyboard: up and down between its rows (the
     * quotations in progress, the messages, the lots about to expire or without date), left
     * and right in a message (open it, mark it as read), and Enter opens; left from the first
     * button of a row goes back to the modes.
     */
    onHomeDashboardKeydown(ev) {
        const buttons = [...ev.currentTarget.querySelectorAll("button:not(:disabled)")];
        const rows = [...new Set(buttons.map((button) => button.closest(".o_mercas_touch_home_message") || button))];
        const items = (row) => (row.matches("button") ? [row] : [...row.querySelectorAll("button:not(:disabled)")]);
        if (this.moveInRows(ev, rows, items) === "ArrowLeft") {
            const modes = document.querySelector(".o_mercas_touch_home_menu");
            ((this.lastMode && modes?.querySelector(`.o_mercas_touch_mode_${this.lastMode}`)) ||
                modes?.querySelector(".o_mercas_touch_mode"))?.focus();
        }
    }

    /**
     * The tiles of a grid chosen with the keyboard (the partners, the products, the lots of a
     * product, the lots of a damaged label): the arrows move the focus between them (up and
     * down by a row of the grid), Enter chooses the one focused (its button). The tiles
     * disabled, as the lots without stock left, are skipped. Up from the first row goes back to
     * the search of the screen.
     *
     * @param {KeyboardEvent} ev on the grid
     * @param {string} selector the tiles of the grid
     */
    onGridKeydown(ev, selector) {
        const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: "row", ArrowUp: "-row" };
        if (!(ev.key in moves)) {
            return;
        }
        const tiles = [...ev.currentTarget.querySelectorAll(`${selector}:not(:disabled)`)];
        if (!tiles.length) {
            return;
        }
        ev.preventDefault();
        // Tiles in a row of the grid: those as high as the first one
        const columns = tiles.filter((tile) => tile.offsetTop === tiles[0].offsetTop).length || 1;
        const move = { row: columns, "-row": -columns }[moves[ev.key]] ?? moves[ev.key];
        const index = tiles.indexOf(document.activeElement);
        if (index >= 0 && index + move < 0 && moves[ev.key] === "-row") {
            const search = document.querySelector(".o_mercas_touch_body .o_mercas_touch_search input");
            if (search) {
                search.focus();
                search.select();
                return;
            }
        }
        const next = index < 0 ? 0 : Math.min(tiles.length - 1, Math.max(0, index + move));
        tiles[next].focus();
    }

    /**
     * Down from a search goes to the first tile of the results (see onGridKeydown).
     *
     * @returns {boolean} whether the key was handled
     */
    focusFirstTile(ev, selector) {
        if (ev.key !== "ArrowDown") {
            return false;
        }
        const tile = document.querySelector(`.o_mercas_touch_body ${selector}:not(:disabled)`);
        if (tile) {
            ev.preventDefault();
            tile.focus();
        }
        return true;
    }

    /** Quantity of the lot already in the lines of the sale. */
    lotQtyInLines(lotId, exceptLine = null) {
        return this.state.lines
            .filter((line) => line.lot && line.lot.id === lotId && line !== exceptLine)
            .reduce((total, line) => total + line.qty, 0);
    }

    lotAvailable(lot, exceptLine = null) {
        return lot.available - this.lotQtyInLines(lot.id, exceptLine);
    }

    openEntry(product, lot, line = null) {
        const partner = this.state.partner;
        const defaultBox = product.box_product_id || false;
        this.state.entry = {
            line,
            product,
            lot,
            qty: line ? this.formatInput(line.qty) : "",
            // The price of the order line for the partner (see loadLinePrice)
            price: line ? this.formatInput(line.price) : partner ? "" : this.formatInput(lot?.sale_price || product.price),
            boxQty: line ? line.boxQty : 0,
            boxProductId: line ? line.boxProductId : defaultBox,
            // Weight on the scale, with the boxes: the net weight (qty) is worked out from it.
            // Empty when the net weight is typed
            gross: "",
            // Text typed to look for a box; null while the list of boxes is closed
            boxSearch: null,
            note: line ? line.note : "",
            showNote: Boolean(line?.note),
            // A new line of a purchase: from where the supplier is
            originCountryId: line ? line.originCountryId : partner?.origin_country_id || false,
            originStateId: line ? line.originStateId : partner?.origin_state_id || false,
            firm: line ? line.firm : Boolean(partner?.firm_negotiation),
            lotName: line ? line.lotName : "",
            // On a purchase, the sale price of the lot received; empty: the one of the product
            salePrice: line?.salePrice ? this.formatInput(line.salePrice) : "",
            attributeValueIds: line ? [...(line.attributeValueIds || [])] : [],
            // Field written by the keypad: a new line of goods sold by weight starts with the
            // weight on the scale
            field: !line && product.weighed ? "gross" : "qty",
        };
        const entry = this.state.entry;
        if (line && product.weighed && entry.boxQty && this.entryTare(entry)) {
            entry.gross = this.formatInput(line.qty + this.entryTare(entry));
        }
        this.loadOriginStates(this.state.entry.originCountryId);
        if (!line && partner) {
            this.loadLinePrice(this.state.entry);
        }
    }

    /** What the proposed price depends on, besides the partner and the product. */
    linePriceKey(entry) {
        return JSON.stringify([
            this.parseNumber(entry.qty) || 1, [...entry.attributeValueIds].sort(), entry.lot?.id || false,
        ]);
    }

    /**
     * The price of a new line, as the order proposes it: for a purchase, the vendor price list
     * of the supplier for the quantity, or else the cost of the product; for a sale, the price
     * list of the customer with the extra price of the attributes, or else the sale price. Only
     * while the price is still the proposed one: a price typed by hand stays.
     *
     * @returns {Promise<boolean>} whether the price of the entry was set
     */
    async loadLinePrice(entry) {
        const key = this.linePriceKey(entry);
        const proposed = entry.proposedPrice ?? "";
        const price = await this.orm.call(MODEL, "get_line_price", [
            this.state.mode,
            this.state.partner.id,
            entry.product.id,
            this.parseNumber(entry.qty) || 1,
            entry.attributeValueIds,
            entry.lot?.id || false,
        ]);
        if (this.state.entry !== entry || entry.price !== proposed) {
            return false;
        }
        entry.price = entry.proposedPrice = this.formatInput(price);
        entry.proposedKey = key;
        return true;
    }

    onSelectLot(lot) {
        if (this.lotAvailable(lot) <= 0) {
            this.notification.add(_t("All the stock of the lot %s is already in the sale.", lot.name), {
                type: "warning",
            });
            return;
        }
        this.openEntry(this.state.product, lot);
    }

    onEntryField(field) {
        this.state.entry.field = field;
    }

    onEntryInput(field, ev) {
        this.state.entry[field] = ev.target.value;
        this.state.entry.field = field;
        this.onEntryWeightChanged(field);
    }

    onNumpadInput(value) {
        const entry = this.state.entry;
        if (entry.field === "boxQty") {
            entry.boxQty = Math.max(0, parseInt(value || "0", 10) || 0);
        } else {
            entry[entry.field] = value;
        }
        this.onEntryWeightChanged(entry.field);
    }

    /**
     * Tare of the boxes of the line being added, in the unit of its product: boxes × weight of
     * the box product.
     */
    entryTare(entry) {
        const box = entry.boxQty && entry.boxProductId ? this.productById(entry.boxProductId) : null;
        return box ? entry.boxQty * (box.weight || 0) * (entry.product.uom_per_weight || 1) : 0;
    }

    /**
     * The scale weighs the goods with their boxes: with a gross weight, the net weight (the
     * quantity of the line) is the gross one less the tare of the boxes, also when the boxes
     * change. Typing the net weight leaves the gross one empty.
     */
    onEntryWeightChanged(field) {
        const entry = this.state.entry;
        if (!entry || !entry.product.weighed) {
            return;
        }
        if (field === "qty") {
            entry.gross = "";
            return;
        }
        if (!String(entry.gross || "").trim()) {
            return;
        }
        const gross = this.parseNumber(entry.gross);
        if (Number.isFinite(gross)) {
            entry.qty = this.formatInput(Math.max(0, gross - this.entryTare(entry)));
        }
    }


    /**
     * A key of the keypad, applied to the field being edited: the price of a line of the
     * ticket, the field of the line being added, the quantity to scrap or the amount to collect.
     */
    onNumpadKey(key) {
        const priceEdit = this.state.priceEdit;
        const entry = this.state.entry;
        const pallets = this.state.pallets;
        if (pallets) {
            // Boxes to move: whole boxes only
            if (pallets.selected && (/^[0-9]$/.test(key) || ["backspace", "clear"].includes(key))) {
                pallets.moveQty = applyNumpadKey(pallets.moveFresh ? "" : pallets.moveQty, key);
                pallets.moveFresh = false;
            }
        } else if (priceEdit) {
            // The first digit replaces the price, as on a till; an operator works on it
            const replace = priceEdit.fresh && (/^[0-9]$/.test(key) || key === localization.decimalPoint);
            priceEdit.value = applyNumpadKey(replace ? "" : priceEdit.value, key);
            priceEdit.fresh = false;
        } else if (entry) {
            if (entry.field === "boxQty") {
                if (/^[0-9]$/.test(key) || ["backspace", "clear"].includes(key)) {
                    this.onNumpadInput(applyNumpadKey(String(entry.boxQty || ""), key));
                }
            } else {
                entry[entry.field] = applyNumpadKey(entry[entry.field], key);
                this.onEntryWeightChanged(entry.field);
            }
        } else if (this.state.scrap) {
            this.state.scrap.qty = applyNumpadKey(this.state.scrap.qty, key);
        } else if (this.state.lotPrice) {
            this.state.lotPrice.price = applyNumpadKey(this.state.lotPrice.price, key);
        } else if (this.state.mode === "payment") {
            this.state.amount = applyNumpadKey(this.state.amount, key);
        }
    }

    onBoxQtyStep(step) {
        this.state.entry.boxQty = Math.max(0, (this.state.entry.boxQty || 0) + step);
        this.onEntryWeightChanged("boxQty");
    }

    /**
     * Kinds of box matching what is typed in the box of the line, at most BOX_CHOICES_LIMIT
     * of them: there are hundreds, too many for a selection.
     */
    boxChoices() {
        const boxes = this.searchBoxes(this.state.entry.boxSearch);
        return {
            boxes: boxes.slice(0, BOX_CHOICES_LIMIT),
            more: Math.max(0, boxes.length - BOX_CHOICES_LIMIT),
        };
    }

    onBoxSearchFocus(ev) {
        // An empty search shows all the boxes; the one chosen stays until another is picked
        this.state.entry.boxSearch = "";
        ev.target.value = "";
    }

    onBoxSearchBlur(ev) {
        // A little later: on some tablets the tap on a result blurs the field before its click
        const entry = this.state.entry;
        const input = ev.target;
        browser.setTimeout(() => {
            // No line any more when the field is left because the line was added (Enter)
            if (entry && this.state.entry === entry && document.activeElement !== input) {
                entry.boxSearch = null;
            }
        }, 200);
    }

    onBoxSearchInput(ev) {
        this.state.entry.boxSearch = ev.target.value;
    }

    /** Enter chooses the first box of the search, or keeps the one chosen when nothing is
     * typed, and goes on to the next field of the line (see onEntryKeydown). */
    onBoxSearchKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        const entry = this.state.entry;
        if (!ev.shiftKey && (entry.boxSearch || "").trim()) {
            const [box] = this.boxChoices().boxes;
            if (!box) {
                ev.preventDefault();
                return;
            }
            this.onSelectBox(box.id);
        }
        this.onEntryKeydown(ev, "boxProduct");
    }

    onSelectBox(boxProductId) {
        this.state.entry.boxProductId = boxProductId || false;
        this.state.entry.boxSearch = null;
        this.onEntryWeightChanged("boxProductId");
        document.activeElement?.blur();
    }

    onEntryCountry(ev) {
        this.state.entry.originCountryId = parseInt(ev.target.value, 10) || false;
        this.state.entry.originStateId = false;
        this.loadOriginStates(this.state.entry.originCountryId);
    }

    onEntryState(ev) {
        const stateId = parseInt(ev.target.value, 10) || false;
        this.state.entry.originStateId = stateId;
        const state = this.originStates().find((s) => s.id === stateId);
        if (state) {
            this.state.entry.originCountryId = state.country_id;
        }
    }

    async loadOriginStates(countryId) {
        const origin = this.state.data.origin;
        if (this.state.mode !== "purchase" || !origin.state || !countryId ||
            this.state.originStates[countryId]) {
            return;
        }
        const states = await this.orm.call(MODEL, "get_origin_states", [countryId]);
        this.state.originStates = { ...this.state.originStates, [countryId]: states };
    }

    /** States of origin to choose: those of the country chosen. */
    originStates() {
        const countryId = this.state.entry?.originCountryId;
        return (countryId && this.state.originStates[countryId]) || [];
    }

    /** Attributes chosen on each sale of the product, as the quality and the size of bulk goods. */
    entryAttributes() {
        return this.state.mode === "sale" ? this.state.entry.product.attributes || [] : [];
    }

    /** A value of an attribute of the line: it replaces the other value of the attribute, and
     * touched again it is removed. */
    onEntryAttributeValue(attribute, value) {
        const entry = this.state.entry;
        const selected = entry.attributeValueIds.includes(value.id);
        const otherIds = attribute.values.map((v) => v.id);
        entry.attributeValueIds = entry.attributeValueIds.filter((id) => !otherIds.includes(id));
        if (!selected) {
            entry.attributeValueIds.push(value.id);
        }
    }

    /** The value chosen of an attribute (`group`, its block on the screen), or else its first one. */
    attributeButton(group) {
        return group && (group.querySelector(".o_mercas_touch_attribute_value.btn-primary") ||
            group.querySelector(".o_mercas_touch_attribute_value"));
    }

    /** The first field of the line written after the attributes (the gross weight or the
     * quantity), selected. */
    focusEntryInput(field = this.entryFieldOrder()[0]) {
        const input = document.querySelector(ENTRY_INPUTS[field]);
        input?.focus();
        input?.select?.();
        return input;
    }

    /**
     * The attributes of the line with the keyboard: left and right between the values of an
     * attribute, up and down to the attribute before or after (down from the last one, to the
     * first field), and Enter chooses the value focused (it isn't removed if it was chosen
     * already) and goes on to the next attribute, or to the first field of the line.
     */
    onAttributeValueKeydown(ev, attribute, value) {
        const groups = [...document.querySelectorAll(".o_mercas_touch_entry .o_mercas_touch_attribute")];
        const group = ev.currentTarget.closest(".o_mercas_touch_attribute");
        const position = groups.indexOf(group);
        if (ev.key === "Enter") {
            ev.preventDefault();
            if (!this.state.entry.attributeValueIds.includes(value.id)) {
                this.onEntryAttributeValue(attribute, value);
            }
            this.focusAfterRender(() =>
                this.attributeButton(document.querySelectorAll(".o_mercas_touch_entry .o_mercas_touch_attribute")[position + 1]) ||
                document.querySelector(ENTRY_INPUTS[this.entryFieldOrder()[0]])
            );
        } else if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
            ev.preventDefault();
            const values = [...group.querySelectorAll(".o_mercas_touch_attribute_value")];
            const index = values.indexOf(ev.currentTarget);
            values[(index + (ev.key === "ArrowRight" ? 1 : -1) + values.length) % values.length].focus();
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
            ev.preventDefault();
            const other = groups[position + (ev.key === "ArrowDown" ? 1 : -1)];
            if (other) {
                this.attributeButton(other).focus();
            } else if (ev.key === "ArrowDown") {
                this.focusEntryInput();
            }
        }
    }

    /** Values chosen on the line, as "Extra · 70-75". */
    lineAttributes(line) {
        const names = [];
        for (const attribute of line.product.attributes || []) {
            for (const value of attribute.values) {
                if ((line.attributeValueIds || []).includes(value.id)) {
                    names.push(value.name);
                }
            }
        }
        return names.join(" · ");
    }

    onEntryFirm(ev) {
        this.state.entry.firm = ev.target.checked;
    }

    toggleEntryNote() {
        this.state.entry.showNote = !this.state.entry.showNote;
    }

    /**
     * The text of a float field when it's left or on Enter: an operation typed on the keyboard
     * ("50*2-3", "12,5x3") or on the keypad ("12,5×3") becomes its result. The "=" in front of
     * the fields of Odoo ("=(50*2-3)^2") is also understood, for parentheses and powers. An operation that can't be
     * worked out stays, to be corrected.
     */
    resolveFloatInput(value) {
        if (!isNumpadExpression(value)) {
            return value;
        }
        const number = evalNumpadExpression(value);
        return Number.isNaN(number) ? value : this.formatInput(number);
    }

    /** A float field left: `record[key]` gets the result of the operation it holds. */
    onFloatChange(record, key) {
        // The editor may be closed already (Enter on the last price), its field leaving
        if (!record) {
            return;
        }
        record[key] = this.resolveFloatInput(record[key]);
        if (record === this.state.entry && key === "gross") {
            this.onEntryWeightChanged(key);
        }
    }

    /** Fields of the line in the order Enter goes through them (after the attributes, see
     * onAttributeValueKeydown): the gross weight of the goods weighed, the quantity, the price,
     * the boxes and, with boxes, their kind; on a purchase, the origin, the lot, its sale price
     * and the firm negotiation. */
    entryFieldOrder() {
        const entry = this.state.entry;
        const fields = entry.product.weighed ? ["gross"] : [];
        fields.push("qty", "price", "boxQty");
        if (entry.boxQty) {
            fields.push("boxProduct");
        }
        if (this.state.mode === "purchase") {
            const origin = this.state.data.origin;
            if (origin.country) {
                fields.push("country");
            }
            // The states of the country, when it has any
            if (origin.state && this.originStates().length) {
                fields.push("state");
            }
            fields.push("lotName", "salePrice", "firm");
        }
        return fields;
    }

    /**
     * Enter in a field of the line works out the operation typed ("12,5*3") and goes to the
     * next field; in the last one, it adds the line, as the button. Shift+Enter goes back (from
     * the first field, to the attributes). A whole line is entered with the keyboard (or a
     * scale that ends with Enter). The selects of the origin change with the arrows.
     */
    onEntryKeydown(ev, field) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        const entry = this.state.entry;
        if (ENTRY_FLOAT_FIELDS.includes(field)) {
            this.onFloatChange(entry, field);
        }
        const order = this.entryFieldOrder();
        let position = order.indexOf(field);
        if (position < 0 && field === "boxProduct") {
            // The kind of box chosen without boxes: as from the boxes
            position = order.indexOf("boxQty");
        }
        const index = position + (ev.shiftKey ? -1 : 1);
        if (index < 0) {
            const groups = document.querySelectorAll(".o_mercas_touch_entry .o_mercas_touch_attribute");
            this.attributeButton(groups[groups.length - 1])?.focus();
            return;
        }
        if (index >= order.length) {
            this.onAddEntry();
            return;
        }
        // The kind of box, the origin and the firm negotiation aren't written with the keypad:
        // it stays on the field it was
        if (!ENTRY_NOT_KEYPAD.includes(order[index])) {
            entry.field = order[index];
        }
        this.focusEntryInput(order[index]);
    }

    /** Enter in a float field works out the operation typed, without leaving the field. */
    /**
     * Enter in a decimal field works out the operation typed; with `next`, it also goes to that
     * button (Scrap, Save...), which Enter then presses: a field doesn't confirm by itself.
     */
    onFloatKeydown(ev, record, key, next = null) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onFloatChange(record, key);
            if (next) {
                document.querySelector(`${next}:not(:disabled)`)?.focus();
            }
        }
    }

    /** The number of a field, also when it holds an operation of the keypad ("12,5×3"). */
    parseNumber(value) {
        if (isNumpadExpression(value)) {
            return evalNumpadExpression(value);
        }
        try {
            return parseFloat(String(value || "").trim() || "0");
        } catch {
            return NaN;
        }
    }

    async onAddEntry() {
        const entry = this.state.entry;
        const qty = this.parseNumber(entry.qty);
        // The price lists may have another price for the quantity or the attributes chosen
        // after opening
        if (!entry.line && this.state.partner && qty > 0 && entry.proposedKey !== this.linePriceKey(entry)
            && entry.price === (entry.proposedPrice ?? "")) {
            await this.loadLinePrice(entry);
            if (this.state.entry !== entry) {
                return;
            }
        }
        const price = this.parseNumber(entry.price);
        if (!(qty > 0)) {
            this.notification.add(_t("Enter the quantity."), { type: "warning" });
            entry.field = "qty";
            return;
        }
        if (!(price >= 0)) {
            this.notification.add(_t("Enter a valid price."), { type: "warning" });
            entry.field = "price";
            return;
        }
        if (entry.lot && qty > this.lotAvailable(entry.lot, entry.line) + 1e-6) {
            this.notification.add(
                _t("The lot %(lot)s only has %(qty)s %(uom)s available.", {
                    lot: entry.lot.name,
                    qty: this.formatQty(this.lotAvailable(entry.lot, entry.line)),
                    uom: entry.product.uom,
                }),
                { type: "warning" }
            );
            return;
        }
        const salePrice = this.parseNumber(entry.salePrice);
        if (this.state.mode === "purchase" && !(salePrice >= 0)) {
            this.notification.add(_t("Enter a valid sale price."), { type: "warning" });
            entry.field = "salePrice";
            return;
        }
        const values = {
            product: entry.product,
            lot: entry.lot,
            qty,
            price,
            boxQty: entry.boxQty || 0,
            boxProductId: entry.boxQty ? entry.boxProductId : false,
            note: entry.note.trim(),
            originCountryId: entry.originCountryId,
            originStateId: entry.originStateId,
            firm: entry.firm,
            lotName: entry.lotName.trim(),
            salePrice: this.state.mode === "purchase" ? salePrice : 0,
            attributeValueIds: [...entry.attributeValueIds],
        };
        if (entry.line) {
            Object.assign(entry.line, values);
        } else {
            this.state.lines.push({ key: `${Date.now()}-${this.state.lines.length}`, ...values });
        }
        this.scheduleSave();
        this.state.entry = null;
        this.state.product = null;
        this.state.lots = [];
    }

    onEditLine(line) {
        if (this.state.sending || !this.commitPrice()) {
            return;
        }
        this.state.priceEdit = null;
        this.state.product = line.product;
        this.state.lots = line.lot ? [line.lot] : [];
        this.openEntry(line.product, line.lot, line);
    }

    /** The ticket with the keyboard (F8): the line being changed, or else the last one. */
    focusTicket() {
        const infos = [...document.querySelectorAll(".o_mercas_touch_lines .o_mercas_touch_line_info")];
        const editing = this.state.entry?.line || this.priceEditLine();
        const index = editing ? this.state.lines.indexOf(editing) : -1;
        (infos[index] || infos[infos.length - 1])?.focus();
    }

    /** The elements of a line of the ticket that can be focused, in a row: the product (the
     * line itself), its price and its trash. */
    ticketLineItems(row) {
        return [...row.querySelectorAll(
            ".o_mercas_touch_line_info, .o_mercas_touch_line_price:not(:disabled), .o_mercas_touch_remove_line:not(:disabled)"
        )];
    }

    /**
     * A line of the ticket with the keyboard, as a row: the product, the price and the trash.
     * Left and right go along the row (left from the product, back to the product search), up
     * and down to the line before or after, at the same place. Enter on the product changes
     * the line, on the price changes it (see onPriceKeydown) and on the trash removes it, as
     * a tap. From anywhere on the line, P changes its price and Delete removes it, once
     * confirmed.
     */
    onTicketKeydown(ev) {
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        const rows = [...ev.currentTarget.querySelectorAll(".o_mercas_touch_line")];
        const row = rows.find((other) => other.contains(ev.target));
        const line = this.state.lines[rows.indexOf(row)];
        if (!line || !this.ticketLineItems(row).includes(ev.target)) {
            return;
        }
        if (ev.key === "Enter" && ev.target.matches(".o_mercas_touch_line_info")) {
            ev.preventDefault();
            this.onEditLine(line);
        } else if (ev.key === "p" || ev.key === "P") {
            ev.preventDefault();
            this.onEditPrice(line);
        } else if (ev.key === "Delete") {
            ev.preventDefault();
            this.confirmRemoveLine(line);
        } else if (this.moveInRows(ev, rows, (other) => this.ticketLineItems(other)) === "ArrowLeft") {
            const search = document.querySelector(".o_mercas_touch_body .o_mercas_touch_search input");
            search?.focus();
            search?.select();
        }
    }

    /** Remove a line with the keyboard, once confirmed: the focus goes to the line after (or
     * before), or to the product search. */
    confirmRemoveLine(line) {
        if (this.state.sending) {
            return;
        }
        const index = this.state.lines.indexOf(line);
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove the line"),
            body: _t("%s will be removed from the ticket.", line.product.name),
            confirmLabel: _t("Remove"),
            cancelLabel: _t("Keep it"),
            confirm: () => {
                this.onRemoveLine(line);
                this.focusAfterRender(() => {
                    const infos = document.querySelectorAll(".o_mercas_touch_lines .o_mercas_touch_line_info");
                    return infos[Math.min(index, infos.length - 1)] ||
                        document.querySelector(".o_mercas_touch_body .o_mercas_touch_search input");
                });
            },
            cancel: () => {},
        });
    }

    onRemoveLine(line) {
        // Removed from the ticket with the keyboard (its trash focused): on with the same
        // place of the line after (or before), or the product search
        const focused = document.activeElement?.closest?.(".o_mercas_touch_line");
        if (focused) {
            const index = this.state.lines.indexOf(line);
            const column = this.ticketLineItems(focused).indexOf(document.activeElement);
            this.focusAfterRender(() => {
                const rows = document.querySelectorAll(".o_mercas_touch_lines .o_mercas_touch_line");
                const row = rows[Math.min(index, rows.length - 1)];
                const items = row ? this.ticketLineItems(row) : [];
                return items[Math.min(column, items.length - 1)] ||
                    document.querySelector(".o_mercas_touch_body .o_mercas_touch_search input");
            });
        }
        if (this.state.priceEdit?.key === line.key) {
            this.state.priceEdit = null;
        }
        this.state.lines = this.state.lines.filter((l) => l !== line);
        this.scheduleSave();
        if (this.state.entry?.line === line) {
            this.state.entry = null;
            this.state.product = null;
        }
    }

    // ------------------------------------------------------------------
    // Quick price change from the ticket, line after line
    // ------------------------------------------------------------------

    onEditPrice(line) {
        if (this.state.sending || (this.state.priceEdit && !this.commitPrice())) {
            return;
        }
        // The line being added is left aside: the price is changed on the ticket
        this.state.entry = null;
        this.state.product = null;
        this.state.lots = [];
        this.openPriceEdit(line);
    }

    openPriceEdit(line) {
        this.state.priceEdit = { key: line.key, value: this.formatInput(line.price), fresh: true };
        this.focusPrice = true;
    }

    priceEditLine() {
        const key = this.state.priceEdit?.key;
        return this.state.lines.find((line) => line.key === key);
    }

    priceEditIndex() {
        return this.state.lines.indexOf(this.priceEditLine());
    }

    /** The price typed, with the quantity of the line, as the subtotal shown while typing. */
    priceEditSubtotal() {
        const price = this.parseNumber(this.state.priceEdit.value);
        return price >= 0 ? this.priceEditLine().qty * price : 0;
    }


    onPriceInput(ev) {
        this.state.priceEdit.value = ev.target.value;
        this.state.priceEdit.fresh = false;
    }

    onPriceKeydown(ev) {
        if (ev.key === "Enter" || ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            this.onPriceStep(ev.key === "ArrowUp" || (ev.key === "Enter" && ev.shiftKey) ? -1 : 1);
        }
    }

    /** Write the price typed on its line; false if it isn't a valid price. */
    commitPrice() {
        const edit = this.state.priceEdit;
        const line = this.priceEditLine();
        if (!edit || !line) {
            return true;
        }
        const price = this.parseNumber(edit.value);
        if (!(price >= 0)) {
            this.notification.add(_t("Enter a valid price."), { type: "warning" });
            this.focusPrice = true;
            return false;
        }
        if (line.price !== price) {
            line.price = price;
            this.scheduleSave();
        }
        return true;
    }

    /** Write the price and go to the previous (-1) or next (1) line; past the last one, close. */
    onPriceStep(step) {
        if (!this.commitPrice()) {
            return;
        }
        const next = this.state.lines[this.priceEditIndex() + step];
        if (next) {
            this.openPriceEdit(next);
        } else if (step > 0) {
            this.state.priceEdit = null;
        }
    }

    onClosePriceEdit() {
        if (this.commitPrice()) {
            this.state.priceEdit = null;
        }
    }

    lineSubtotal(line) {
        return line.qty * line.price;
    }

    linesTotal() {
        return this.state.lines.reduce((total, line) => total + this.lineSubtotal(line), 0);
    }

    // ------------------------------------------------------------------
    // Resolución especial para móvil
    // ------------------------------------------------------------------

    /** A phone (under 768 px): no on-screen numpad, the keyboard of the phone instead. */
    isMobile() {
        return this.ui.isSmall;
    }

    /** The keypad on the screen, as chosen in the preferences of the user: automatically, only
     * on a touch screen (a finger as main pointer), not with a mouse and a keyboard. */
    showNumpad() {
        const numpad = this.state.data.numpad;
        if (numpad === "auto") {
            return Boolean(browser.matchMedia?.("(pointer: coarse)").matches);
        }
        return numpad !== "hide";
    }

    /** The fields only written with the keypad of the screen (to keep the keyboard of a tablet
     * hidden) are written with the keyboard of the device without it, or on a phone. */
    keypadOnly() {
        return this.showNumpad() && !this.isMobile();
    }

    /** The ticket under the products, not on their right: the screen is narrower than the
     * lg breakpoint (992 px) of the order (flex-lg-row), as a phone, turned or not, or a
     * small tablet upright. The products can be hidden then, and the total and buttons of
     * the order go to the bar at the bottom. */
    isStacked() {
        return this.ui.size < SIZES.LG;
    }

    catalogHidden() {
        return this.isStacked() && this.state.hideCatalog;
    }

    showMobileOrderBar() {
        const state = this.state;
        return (
            this.isStacked() &&
            (state.mode === "sale" || state.mode === "purchase") &&
            Boolean(state.partner) &&
            !state.pallets &&
            !state.done &&
            !state.entry &&
            !state.priceEdit
        );
    }

    loadHideCatalog() {
        try {
            return browser.localStorage.getItem(HIDE_CATALOG_KEY) === "1";
        } catch {
            return false;
        }
    }

    loadHideHome() {
        try {
            return browser.localStorage.getItem(HIDE_HOME_KEY) === "1";
        } catch {
            return false;
        }
    }

    onToggleHome() {
        this.state.hideHome = !this.state.hideHome;
        try {
            browser.localStorage.setItem(HIDE_HOME_KEY, this.state.hideHome ? "1" : "0");
        } catch {
            // Without the storage of the browser it isn't remembered
        }
        if (!this.state.hideHome) {
            this.loadHome();
        }
    }

    onToggleCatalog() {
        this.state.hideCatalog = !this.state.hideCatalog;
        try {
            browser.localStorage.setItem(HIDE_CATALOG_KEY, this.state.hideCatalog ? "1" : "0");
        } catch {
            // Without the storage of the browser it isn't remembered
        }
    }

    linesBoxes() {
        return this.state.lines.reduce((total, line) => total + (line.boxQty || 0), 0);
    }

    boxName(boxProductId, fallback = _t("boxes")) {
        return this.productById(boxProductId)?.name || fallback;
    }

    // ------------------------------------------------------------------
    // Pallets
    // ------------------------------------------------------------------

    /**
     * Arrange the boxes of the sale on pallets: from the ticket, while the sale is a draft, or
     * from the sale done, to correct them (its delivery is corrected then).
     */
    async onOpenPallets() {
        if (this.state.sending) {
            return;
        }
        let orderId = this.state.done?.id;
        if (!this.state.done) {
            if (!this.commitPrice()) {
                return;
            }
            this.state.entry = null;
            this.state.product = null;
            this.state.lots = [];
            await this.flushSave();
            if (!this.state.order || this.state.saveState === "error") {
                this.notification.add(_t("Save the sale first: add a line or try again."), { type: "warning" });
                return;
            }
            orderId = this.state.order.id;
        }
        const data = await this.run("get_pallets", [orderId]);
        if (data) {
            this.loadPallets(data);
        }
    }

    loadPallets(data) {
        this.palletKey = 0;
        this.state.pallets = {
            order: data.order,
            lines: data.lines,
            types: data.types,
            lengthUom: data.length_uom,
            pallets: data.pallets.map((pallet) => this.newPallet(pallet)),
            // Chip chosen to move: { lineId, from: key of its pallet or null (not on a pallet) }
            selected: null,
            moveQty: "",
            moveFresh: true,
            quickCount: Math.max(1, data.pallets.length),
            quickTypeId: data.pallets[0]?.package_type_id || data.types[0]?.id || false,
            dirty: false,
        };
    }

    newPallet(vals = {}) {
        const items = {};
        for (const line of vals.lines || []) {
            items[line.sale_line_id] = (items[line.sale_line_id] || 0) + line.box_qty;
        }
        return {
            key: ++this.palletKey,
            id: vals.id || false,
            typeId: vals.package_type_id || this.state.pallets?.quickTypeId || this.state.pallets?.types[0]?.id,
            height: vals.height ? this.formatInput(vals.height) : "",
            package: vals.package || "",
            items,
        };
    }

    palletLine(lineId) {
        return this.state.pallets.lines.find((line) => line.id === lineId);
    }

    /** Boxes of a line on no pallet. */
    looseBoxes(line) {
        const onPallets = this.state.pallets.pallets.reduce((total, pallet) => total + (pallet.items[line.id] || 0), 0);
        return line.box_qty - onPallets;
    }

    /** The chips of a pallet, or of the boxes on no pallet (`pallet` null): [{ line, boxes }]. */
    palletChips(pallet) {
        return this.state.pallets.lines
            .map((line) => ({ line, boxes: pallet ? pallet.items[line.id] || 0 : this.looseBoxes(line) }))
            .filter((chip) => chip.boxes > 0);
    }

    palletBoxes(pallet) {
        return Object.values(pallet.items).reduce((total, boxes) => total + boxes, 0);
    }

    palletTypeName(typeId) {
        return this.state.pallets.types.find((type) => type.id === typeId)?.name || "";
    }

    totalPalletBoxes() {
        return this.state.pallets.lines.reduce((total, line) => total + line.box_qty, 0);
    }

    isChipSelected(pallet, chip) {
        const selected = this.state.pallets.selected;
        return Boolean(selected) && selected.lineId === chip.line.id && selected.from === (pallet ? pallet.key : null);
    }

    /** Tap a chip to move its boxes; tap it again to leave it. */
    onSelectChip(pallet, chip) {
        const pallets = this.state.pallets;
        if (this.isChipSelected(pallet, chip)) {
            pallets.selected = null;
            return;
        }
        pallets.selected = { lineId: chip.line.id, from: pallet ? pallet.key : null };
        pallets.moveQty = String(chip.boxes);
        pallets.moveFresh = true;
        this.focusAfterRender(".o_mercas_touch_pallets_move_qty");
    }

    /** The first chip of boxes not on a pallet, or else the first one, or else Save. */
    focusPalletChip() {
        const body = document.querySelector(".o_mercas_touch_body");
        const element = body?.querySelector(".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip") ||
            body?.querySelector(".o_mercas_touch_pallet_chip") ||
            body?.querySelector(".o_mercas_touch_pallets_save:not(:disabled)");
        element?.focus();
    }

    /**
     * The pallets with the keyboard. On a chip of boxes, up and down go to the chip before or
     * after on the same pallet, left and right to the pallet before or after (or "Not on a
     * pallet"); Enter chooses it, and the focus goes to the boxes to move (see
     * onMoveQtyKeydown). With some boxes chosen, the arrows go between the pallets where they
     * can be put ("Put here", "Take them off here", and the button of a new pallet) and Enter
     * puts them there.
     */
    onPalletsKeydown(ev) {
        const container = ev.currentTarget;
        const target = ev.target;
        if (ev.key === "Enter" && target.matches(".o_mercas_touch_pallet_type")) {
            // The type of a pallet, then its height (see onPalletHeightKeydown)
            ev.preventDefault();
            target.closest(".o_mercas_touch_pallet").querySelector(".o_mercas_touch_pallet_height")?.focus();
            return;
        }
        if (ev.key === "Delete" && target.matches(".o_mercas_touch_pallet_chip, .o_mercas_touch_pallet_type")) {
            // Delete on a pallet (one of its chips or its type): the pallet removed, once confirmed
            const cards = [...container.querySelectorAll(".o_mercas_touch_pallet:not(.o_mercas_touch_pallet_loose)")];
            const pallet = this.state.pallets.pallets[cards.indexOf(target.closest(".o_mercas_touch_pallet"))];
            if (pallet) {
                ev.preventDefault();
                this.confirmRemovePallet(pallet);
            }
            return;
        }
        const moves = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        if (!(ev.key in moves)) {
            return;
        }
        let next = null;
        if (target.matches(".o_mercas_touch_pallet_drop, .o_mercas_touch_pallet_add")) {
            const drops = [...container.querySelectorAll(
                ".o_mercas_touch_pallet_drop, .o_mercas_touch_pallet_add:not(:disabled)"
            )];
            next = drops[(drops.indexOf(target) + moves[ev.key] + drops.length) % drops.length];
        } else if (target.matches(".o_mercas_touch_pallet_chip")) {
            const card = target.closest(".o_mercas_touch_pallet");
            const chips = [...card.querySelectorAll(".o_mercas_touch_pallet_chip")];
            const index = chips.indexOf(target);
            if (ev.key === "ArrowUp" && index === 0) {
                // Up from the first chip: the type of the pallet, or the quick spreading
                next = card.querySelector(".o_mercas_touch_pallet_type") ||
                    document.querySelector(".o_mercas_touch_pallets_spread");
            } else if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
                next = chips[index + moves[ev.key]];
            } else {
                // The next pallet with boxes, at the same place or the last one
                const cards = [...container.querySelectorAll(".o_mercas_touch_pallet")];
                const step = moves[ev.key];
                for (let i = cards.indexOf(card) + step; i >= 0 && i < cards.length; i += step) {
                    const others = cards[i].querySelectorAll(".o_mercas_touch_pallet_chip");
                    if (others.length) {
                        next = others[Math.min(index, others.length - 1)];
                        break;
                    }
                }
            }
        } else {
            return;
        }
        ev.preventDefault();
        next?.focus();
    }

    /**
     * The height of a pallet with the keyboard: Enter works out the operation typed and goes to
     * the type of the next pallet, or to Save after the last one; down goes to its boxes.
     */
    onPalletHeightKeydown(ev, pallet) {
        const card = ev.currentTarget.closest(".o_mercas_touch_pallet");
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onFloatChange(pallet, "height");
            const cards = [...document.querySelectorAll(".o_mercas_touch_body .o_mercas_touch_pallet")];
            const next = cards.slice(cards.indexOf(card) + 1)
                .map((other) => other.querySelector(".o_mercas_touch_pallet_type")).find(Boolean);
            (next || document.querySelector(".o_mercas_touch_pallets_save:not(:disabled)"))?.focus();
        } else if (ev.key === "ArrowDown") {
            const chip = card.querySelector(".o_mercas_touch_pallet_chip");
            if (chip) {
                ev.preventDefault();
                chip.focus();
            }
        }
    }

    /** The quick spreading with the keyboard: + and - change the number of pallets, Enter on
     * the button spreads the boxes, and down goes to the boxes. */
    onPalletsQuickKeydown(ev) {
        if (ev.key === "+" || ev.key === "-") {
            ev.preventDefault();
            this.onQuickCount(ev.key === "+" ? 1 : -1);
        } else if (ev.key === "ArrowDown" && !ev.target.matches("select")) {
            ev.preventDefault();
            this.focusPalletChip();
        }
    }

    /**
     * The boxes to move with the keyboard: the digits (also with the keypad on the screen, when
     * the field takes only it), + and - add or take a box, and Enter or down go to the first
     * pallet where they can be put (see onPalletsKeydown).
     */
    onMoveQtyKeydown(ev) {
        if (/^[0-9]$/.test(ev.key) && ev.target.readOnly) {
            ev.preventDefault();
            this.onNumpadKey(ev.key);
        } else if (ev.key === "Backspace" && ev.target.readOnly) {
            ev.preventDefault();
            this.onNumpadKey("backspace");
        } else if (ev.key === "+" || ev.key === "-") {
            ev.preventDefault();
            this.onMoveStep(ev.key === "+" ? 1 : -1);
        } else if (ev.key === "Enter" || ev.key === "ArrowDown") {
            ev.preventDefault();
            document.querySelector(
                ".o_mercas_touch_body .o_mercas_touch_pallet_drop, .o_mercas_touch_body .o_mercas_touch_pallet_add:not(:disabled)"
            )?.focus();
        }
    }

    /** Boxes of the chip chosen still where they are. */
    selectedAvailable() {
        const pallets = this.state.pallets;
        const selected = pallets.selected;
        if (!selected) {
            return 0;
        }
        const from = pallets.pallets.find((pallet) => pallet.key === selected.from);
        return from ? from.items[selected.lineId] || 0 : this.looseBoxes(this.palletLine(selected.lineId));
    }

    /** Resolución especial para móvil: the boxes to move typed with the keyboard of the phone. */
    onMoveQtyInput(ev) {
        const pallets = this.state.pallets;
        const qty = parseInt(ev.target.value || "0", 10) || 0;
        pallets.moveQty = qty > 0 ? String(Math.min(this.selectedAvailable(), qty)) : "";
        pallets.moveFresh = false;
        // Owl doesn't patch the value when the clamped quantity is the one there was
        ev.target.value = pallets.moveQty;
    }

    onMoveStep(step) {
        const pallets = this.state.pallets;
        const qty = (parseInt(pallets.moveQty || "0", 10) || 0) + step;
        pallets.moveQty = String(Math.min(this.selectedAvailable(), Math.max(1, qty)));
        pallets.moveFresh = false;
    }

    /** Put the boxes of the chip chosen on `target` (a pallet, or null: on no pallet). */
    onDropOnPallet(target) {
        const pallets = this.state.pallets;
        const selected = pallets.selected;
        if (!selected || selected.from === (target ? target.key : null)) {
            return;
        }
        const qty = Math.min(parseInt(pallets.moveQty || "0", 10) || 0, this.selectedAvailable());
        if (qty <= 0) {
            this.notification.add(_t("Enter how many boxes to move."), { type: "warning" });
            return;
        }
        const from = pallets.pallets.find((pallet) => pallet.key === selected.from);
        if (from) {
            from.items[selected.lineId] -= qty;
            if (!from.items[selected.lineId]) {
                delete from.items[selected.lineId];
            }
        }
        if (target) {
            target.items[selected.lineId] = (target.items[selected.lineId] || 0) + qty;
        }
        pallets.selected = null;
        pallets.dirty = true;
        // On with the boxes left out of the pallets, or else to Save
        if (!browser.matchMedia?.("(pointer: coarse)").matches) {
            this.pendingFocus = [".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip", ".o_mercas_touch_pallets_save"];
        }
    }

    onAddPallet() {
        const pallets = this.state.pallets;
        const pallet = this.newPallet();
        pallets.pallets.push(pallet);
        pallets.dirty = true;
        // With a chip chosen, the new pallet takes its boxes
        if (pallets.selected) {
            this.onDropOnPallet(pallet);
        }
    }

    /** Remove a pallet with the keyboard, once confirmed: the focus goes back to the boxes. */
    confirmRemovePallet(pallet) {
        const number = this.state.pallets.pallets.indexOf(pallet) + 1;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove the pallet"),
            body: _t("Pallet %(number)s will be removed: its %(boxes)s boxes go back to Not on a pallet.", {
                number,
                boxes: this.palletBoxes(pallet),
            }),
            confirmLabel: _t("Remove"),
            cancelLabel: _t("Keep it"),
            confirm: () => {
                this.onRemovePallet(pallet);
                this.focusAfterRender(() => {
                    const body = document.querySelector(".o_mercas_touch_body");
                    return body?.querySelector(".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip") ||
                        body?.querySelector(".o_mercas_touch_pallet_chip") ||
                        body?.querySelector(".o_mercas_touch_pallets_save:not(:disabled)");
                });
            },
            cancel: () => {},
        });
    }

    /** Remove a pallet: its boxes go back to no pallet. */
    onRemovePallet(pallet) {
        const pallets = this.state.pallets;
        pallets.pallets = pallets.pallets.filter((other) => other !== pallet);
        if (pallets.selected?.from === pallet.key) {
            pallets.selected = null;
        }
        pallets.dirty = true;
    }

    onPalletType(pallet, ev) {
        pallet.typeId = parseInt(ev.target.value, 10) || false;
        this.state.pallets.dirty = true;
    }

    onPalletHeight(pallet, ev) {
        pallet.height = ev.target.value;
        this.state.pallets.dirty = true;
    }

    onQuickCount(step) {
        const pallets = this.state.pallets;
        pallets.quickCount = Math.min(Math.max(1, pallets.quickCount + step), Math.max(1, this.totalPalletBoxes()));
    }

    onQuickType(ev) {
        this.state.pallets.quickTypeId = parseInt(ev.target.value, 10) || false;
    }

    /**
     * Spread all the boxes over the number of pallets chosen: each line goes whole, the biggest
     * first, on the pallet with the fewest boxes; a line is split only when a pallet would be
     * left empty. The pallets already there keep their package, in order.
     */
    onQuickSpread() {
        const pallets = this.state.pallets;
        const total = this.totalPalletBoxes();
        if (!total) {
            return;
        }
        const count = Math.min(pallets.quickCount, total);
        const previous = pallets.pallets;
        const result = Array.from({ length: count }, (_, index) => ({
            ...this.newPallet({ id: previous[index]?.id, package: previous[index]?.package }),
            typeId: pallets.quickTypeId,
            height: previous[index]?.height || "",
        }));
        const loads = new Array(count).fill(0);
        const lines = [...pallets.lines].sort((a, b) => b.box_qty - a.box_qty);
        for (const line of lines) {
            const index = loads.indexOf(Math.min(...loads));
            result[index].items[line.id] = line.box_qty;
            loads[index] += line.box_qty;
        }
        // An empty pallet takes half of the biggest line of the fullest one
        let empty = loads.indexOf(0);
        while (empty >= 0) {
            const full = loads.indexOf(Math.max(...loads));
            const [lineId, boxes] = Object.entries(result[full].items).sort((a, b) => b[1] - a[1])[0];
            const take = Math.max(1, Math.floor(Math.min(boxes, loads[full]) / 2));
            result[full].items[lineId] -= take;
            if (!result[full].items[lineId]) {
                delete result[full].items[lineId];
            }
            result[empty].items[lineId] = take;
            loads[full] -= take;
            loads[empty] = take;
            empty = loads.indexOf(0);
        }
        pallets.pallets = result;
        pallets.selected = null;
        pallets.dirty = true;
        // On with the type and the height of the pallets, or Ctrl+Enter to save them
        this.focusAfterRender(".o_mercas_touch_pallet:not(.o_mercas_touch_pallet_loose) .o_mercas_touch_pallet_type",
            ".o_mercas_touch_pallets_save");
    }

    palletsPayload() {
        return this.state.pallets.pallets
            .filter((pallet) => this.palletBoxes(pallet) > 0)
            .map((pallet) => ({
                id: pallet.id || false,
                package_type_id: pallet.typeId,
                height: this.parseNumber(pallet.height) > 0 ? this.parseNumber(pallet.height) : 0,
                lines: Object.entries(pallet.items)
                    .filter(([, boxes]) => boxes > 0)
                    .map(([lineId, boxes]) => ({ sale_line_id: parseInt(lineId, 10), box_qty: boxes })),
            }));
    }

    async onSavePallets() {
        const pallets = this.state.pallets;
        if (pallets.pallets.some((pallet) => this.palletBoxes(pallet) > 0 && !pallet.typeId)) {
            this.notification.add(_t("Choose the type of each pallet."), { type: "warning" });
            return;
        }
        const result = await this.run("save_pallets", [pallets.order.id, this.palletsPayload()]);
        if (!result) {
            return;
        }
        this.notification.add(
            pallets.order.delivered ? _t("Pallets saved: the delivery has been corrected.") : _t("Pallets saved."),
            { type: "success" }
        );
        for (const mismatch of result.mismatch) {
            this.notification.add(
                _t("%(product)s: %(pallets)s on the pallets and %(sale)s on the sale. Register the difference in Boxes (F3).", mismatch),
                { title: _t("Returnable pallets"), type: "warning", sticky: true }
            );
        }
        if (this.state.done?.id === pallets.order.id) {
            this.state.done.pallet_count = result.pallet_count;
        }
        this.state.pallets = null;
    }

    onClosePallets() {
        if (!this.state.pallets.dirty) {
            this.state.pallets = null;
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Pallets"),
            body: _t("The changes of the pallets will be lost."),
            confirmLabel: _t("Discard"),
            cancelLabel: _t("Keep editing"),
            confirm: () => {
                this.state.pallets = null;
            },
            cancel: () => {},
        });
    }

    // ------------------------------------------------------------------
    // Operations
    // ------------------------------------------------------------------

    newUuid() {
        // Kept until the operation is done, so that a retry sends the same one
        if (!this.operationUuid) {
            this.operationUuid = randomUuid();
        }
        return this.operationUuid;
    }

    async run(method, args) {
        if (this.state.sending) {
            return null;
        }
        this.state.sending = true;
        try {
            return await this.orm.call(MODEL, method, args);
        } finally {
            this.state.sending = false;
        }
    }

    async onSell() {
        if (!this.state.lines.length || !this.commitPrice()) {
            return;
        }
        this.state.sending = true;
        try {
            await this.flushSave();
        } finally {
            this.state.sending = false;
        }
        const result = await this.run("sell", [
            {
                uuid: this.newUuid(),
                partner_id: this.state.partner.id,
                ...(this.state.order ? { order_id: this.state.order.id } : {}),
                lines: this.linesPayload(this.state.lines),
            },
        ]);
        if (!result) {
            return;
        }
        this.finishOperation({ kind: "sale", model: "sale.order", ...result.order });
        if (result.action) {
            // Risk exceeded: the standard dialog lets a risk manager go on
            await this.action.doAction(result.action, {
                onClose: () => this.refreshSaleAfterRisk(result.order.id),
            });
        }
    }

    async refreshSaleAfterRisk(orderId) {
        const [order] = await this.orm.read("sale.order", [orderId], ["name", "state"]);
        if (this.state.done?.id === orderId && order) {
            this.state.done.state = order.state;
            this.state.done.delivered = order.state === "sale";
        }
        await this.reloadPartner();
    }

    async onPurchase() {
        if (!this.state.lines.length || !this.commitPrice()) {
            return;
        }
        this.state.sending = true;
        try {
            await this.flushSave();
        } finally {
            this.state.sending = false;
        }
        const result = await this.run("purchase", [
            {
                uuid: this.newUuid(),
                partner_id: this.state.partner.id,
                ...(this.state.order ? { order_id: this.state.order.id } : {}),
                lines: this.linesPayload(this.state.lines),
            },
        ]);
        if (result) {
            this.finishOperation({ kind: "purchase", model: "purchase.order", ...result.order });
        }
    }

    finishOperation(done) {
        const partner = this.state.partner;
        this.resetOperation();
        this.state.partner = partner;
        this.state.done = done;
        this.reloadPartner();
    }

    /** Invoice the sale just made; the invoice can then be printed and collected. */
    async onInvoiceSale() {
        const done = this.state.done;
        const invoice = await this.run("invoice_sale", [done.id]);
        if (invoice?.action) {
            // Risk exceeded: the invoice stays in draft until a risk manager goes on
            Object.assign(done, invoice.order);
            await this.action.doAction(invoice.action, {
                onClose: () => this.refreshOrderSummary(),
            });
            return;
        }
        if (invoice && this.state.done === done) {
            Object.assign(done, invoice.order);
            done.invoice = invoice;
            // Its button gone, on to collecting it
            this.focusAfterRender(".o_mercas_touch_collect_invoice", ".o_mercas_touch_done_actions .o_mercas_touch_new");
            await this.reloadPartner();
        }
    }

    /** The bill of the lines without lot of a purchase, made from the order as in the backend,
     * reviewed in a dialog. */
    async onInvoicePurchase() {
        const action = await this.run("invoice_purchase", [this.state.done.id]);
        if (action) {
            await this.action.doAction(action, { onClose: () => this.refreshOrderSummary() });
        }
    }

    /** The invoice of the lots of a purchase, with their regime: settlement, advance or firm. */
    async onInvoicePurchaseLots(mode) {
        const action = await this.run("invoice_purchase_lots", [this.state.done.id, mode]);
        await this.refreshOrderSummary();
        if (action) {
            await this.action.doAction(action, { onClose: () => this.refreshOrderSummary() });
        }
    }

    /** The bills of a purchase, listed (even only one) to look them up, print them again or
     * delete the drafts. */
    async onShowPurchaseInvoices() {
        const done = this.state.done;
        if (done.invoiceList) {
            done.invoiceList = null;
            return;
        }
        const invoices = await this.orm.call(MODEL, "get_purchase_invoices", [done.id]);
        if (this.state.done === done) {
            done.invoiceList = invoices;
            this.focusAfterRender(".o_mercas_touch_open_invoice");
        }
    }

    /**
     * The bills of a purchase with the keyboard: up and down between them, left and right
     * between opening, printing or deleting it, Enter presses; down from the last one goes back
     * to the buttons. Escape closes the list.
     */
    onInvoiceListKeydown(ev) {
        const rows = [...ev.currentTarget.querySelectorAll(".o_mercas_touch_purchase_invoice")];
        const items = (row) => [...row.querySelectorAll("button:not(:disabled)")];
        if (this.moveInRows(ev, rows, items) === "ArrowDown") {
            document.querySelector(".o_mercas_touch_purchase_invoices")?.focus();
        }
    }

    async onPrintPurchaseInvoice(invoice) {
        const action = await this.run("get_purchase_invoice_print_action", [this.state.done.id, invoice.id]);
        if (action) {
            await this.action.doAction(action);
        }
    }

    onDeleteInvoice(invoice) {
        const done = this.state.done;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete the bill"),
            body: _t("The bill in draft of %(amount)s will be deleted.", {
                amount: this.formatAmount(invoice.amount_total),
            }),
            confirmLabel: _t("Delete"),
            cancelLabel: _t("Keep it"),
            confirm: async () => {
                if (await this.run("delete_purchase_invoice", [done.id, invoice.id])) {
                    await this.refreshOrderSummary();
                    this.focusAfterRender(".o_mercas_touch_open_invoice", ".o_mercas_touch_purchase_invoices",
                        ".o_mercas_touch_done_actions .btn");
                }
            },
            cancel: () => {},
        });
    }

    async onOpenInvoice(invoiceId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: invoiceId,
            views: [[false, "form"]],
            target: "new",
        }, { onClose: () => this.refreshOrderSummary() });
    }

    /** Collect the invoice of the sale just made, in the payments of the customer. */
    async onCollectInvoice() {
        const invoice = this.state.done.invoice;
        const partnerId = this.state.partner.id;
        await this.flushSave();
        this.resetOperation();
        this.state.mode = "payment";
        this.state.partner = await this.orm.call(MODEL, "get_partner_info", [partnerId]);
        if (this.state.partner.invoices.some((inv) => inv.id === invoice.id)) {
            this.state.invoiceIds = [invoice.id];
            this.state.amount = this.formatInput(invoice.residual);
        }
    }

    async onPrint(kind) {
        const done = this.state.done;
        const action = await this.orm.call(MODEL, "get_print_action", [done.model, done.id, kind]);
        await this.action.doAction(action);
    }

    /** The DeCA of the delivery: its carrier and licence plates, proposed, and then printed. */
    async onDeca() {
        const action = await this.orm.call(MODEL, "get_deca_action", [this.state.done.id]);
        // Completed, the DeCA can be sent by email
        await this.action.doAction(action, { onClose: () => this.refreshOrderSummary() });
    }

    /** The comments of the sale being typed, or the ones saved. */
    commentValue(done) {
        return done.commentEdit ?? done.comment;
    }

    /** Save the comments of the sale: printed on the order, the delivery slip and the invoice. */
    async onSaveComment(done) {
        const result = await this.run("set_sale_comment", [done.id, this.commentValue(done)]);
        if (result && this.state.done === done) {
            Object.assign(done, result);
            delete done.commentEdit;
        }
    }

    mailDocumentLabel(kind) {
        return { delivery: _t("Delivery slip"), deca: _t("DeCA"), invoice: _t("Invoice") }[kind];
    }

    /** The invoice goes to the contact of invoicing; the delivery slip and the DeCA, of delivery. */
    mailEmail(done, kind) {
        return done.mail.emails[kind === "invoice" ? "invoice" : "shipping"];
    }

    mailName(done, kind) {
        return done.mail.names[kind === "invoice" ? "invoice" : "shipping"];
    }

    printDocumentLabel(kind) {
        return {
            delivery: _t("Delivery slip"),
            deca: _t("DeCA"),
            packing: _t("Packing list"),
            invoice: _t("Invoice"),
        }[kind];
    }

    /** Open (with the documents available, checked) or close the printing. */
    async onTogglePrint() {
        const done = this.state.done;
        if (done.printPanel) {
            done.printPanel = null;
            this.focusAfterRender(".o_mercas_touch_print");
            return;
        }
        done.mailPanel = null;
        // An invoice, a DeCA or pallets made meanwhile
        await this.refreshOrderSummary();
        if (this.state.done !== done || !done.print) {
            return;
        }
        done.printPanel = { kinds: [...done.print.documents] };
        this.focusAfterRender(".o_mercas_touch_print_panel input:not(:disabled)", ".o_mercas_touch_print_send:not(:disabled)");
    }

    onTogglePrintKind(kind) {
        const panel = this.state.done.printPanel;
        panel.kinds = panel.kinds.includes(kind)
            ? panel.kinds.filter((other) => other !== kind)
            : [...panel.kinds, kind];
    }

    /** The documents checked, in a single PDF for the A4 printer. */
    async onPrintDocuments() {
        const done = this.state.done;
        const kinds = ["delivery", "deca", "packing", "invoice"].filter((kind) => done.printPanel.kinds.includes(kind));
        const action = await this.run("get_sale_documents_print_action", [done.id, kinds]);
        if (!action) {
            return;
        }
        await this.action.doAction(action);
        if (this.state.done === done) {
            done.printPanel = null;
            this.focusAfterRender(".o_mercas_touch_print");
            // The invoice printed keeps its PDF: its comments can't be changed anymore
            await this.refreshOrderSummary();
        }
    }

    /** Open (with the documents available and an email, checked) or close the sending. */
    async onToggleMail() {
        const done = this.state.done;
        if (done.mailPanel) {
            done.mailPanel = null;
            this.focusAfterRender(".o_mercas_touch_mail");
            return;
        }
        done.printPanel = null;
        // An invoice or a DeCA made meanwhile
        await this.refreshOrderSummary();
        if (this.state.done !== done || !done.mail) {
            return;
        }
        done.mailPanel = {
            kinds: done.mail.documents.filter((kind) => this.mailEmail(done, kind)),
        };
        this.focusAfterRender(".o_mercas_touch_mail_panel input:not(:disabled)", ".o_mercas_touch_mail_send:not(:disabled)");
    }

    /**
     * The printing or the sending with the keyboard: up and down (or left and right) between
     * the documents and the buttons, Enter checks the document focused or presses the button,
     * and Ctrl+Enter prints or sends from anywhere (see mainActionButton).
     */
    onDonePanelKeydown(ev) {
        const items = [...ev.currentTarget.querySelectorAll("input[type=checkbox]:not(:disabled), button:not(:disabled)")];
        const index = items.indexOf(ev.target);
        if (index < 0) {
            return;
        }
        if (ev.key === "Enter" && ev.target.matches("input")) {
            ev.preventDefault();
            ev.target.click();
        } else if (ev.key in ARROW_KEYS) {
            ev.preventDefault();
            items[index + (ev.key === "ArrowDown" || ev.key === "ArrowRight" ? 1 : -1)]?.focus();
        }
    }

    /** The main button of an operation done: New, or Back to the list. */
    focusDoneAction() {
        const actions = document.querySelector(".o_mercas_touch_done_actions");
        (actions?.querySelector(".o_mercas_touch_new, .o_mercas_touch_back_to_list") ||
            actions?.querySelector(".btn:not(:disabled)"))?.focus();
    }

    onToggleMailKind(kind) {
        const panel = this.state.done.mailPanel;
        panel.kinds = panel.kinds.includes(kind)
            ? panel.kinds.filter((other) => other !== kind)
            : [...panel.kinds, kind];
    }

    async onSendMail() {
        const done = this.state.done;
        const kinds = ["delivery", "deca", "invoice"].filter((kind) => done.mailPanel.kinds.includes(kind));
        const sent = await this.run("send_sale_documents", [done.id, kinds]);
        if (!sent) {
            return;
        }
        for (const mail of sent) {
            this.notification.add(
                _t("Sent to %(email)s: %(documents)s", {
                    email: mail.email,
                    documents: mail.documents.map((kind) => this.mailDocumentLabel(kind)).join(", "),
                }),
                { type: "success" }
            );
        }
        if (this.state.done === done) {
            done.mailPanel = null;
            this.focusAfterRender(".o_mercas_touch_mail");
            // The invoice sent: its comments can't be changed anymore
            await this.refreshOrderSummary();
        }
    }

    async onNewOperation() {
        this.state.done = null;
        if (this.hasDrafts()) {
            // A new sale or purchase starts again from the drafts
            this.state.partner = null;
            await this.loadDrafts();
        }
    }

    // ------------------------------------------------------------------
    // Boxes
    // ------------------------------------------------------------------

    onBoxDirection(direction) {
        this.state.boxDirection = direction;
        this.state.boxQty = {};
        this.state.boxFilter = null;
        this.focusAfterRender(".o_mercas_touch_box_list_search");
    }

    /** Who gives back the boxes with the keyboard: left and right between both, Enter chooses
     * and goes back to the search, as down. */
    onBoxDirectionKeydown(ev) {
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            document.querySelector(".o_mercas_touch_box_list_search")?.focus();
        } else {
            this.onButtonRowKeydown(ev);
        }
    }

    /** How the boxes given back by a customer are settled: chosen by the counter each time. */
    onBoxSettle(settle) {
        this.state.boxSettle = settle;
        if (settle === "pay" && !this.state.boxJournalId) {
            this.state.boxJournalId = this.state.journalId;
        }
        // Paid now, the journal is chosen next (the one proposed focused); as a credit, the boxes
        // can be moved
        this.focusAfterRender(...(settle === "pay"
            ? [".o_mercas_touch_box_journal.btn-primary", ".o_mercas_touch_box_journal"]
            : [".o_mercas_touch_move_boxes:not(:disabled)"]));
    }

    onSelectBoxJournal(journalId) {
        this.state.boxJournalId = journalId;
        this.focusAfterRender(".o_mercas_touch_move_boxes:not(:disabled)");
    }

    /** Focus the first of `selectors` found once the screen is drawn again, to go on with the
     * keyboard: what comes next after a choice. Not on a touch screen. */
    focusAfterRender(...selectors) {
        if (browser.matchMedia?.("(pointer: coarse)").matches) {
            return;
        }
        this.pendingFocus = selectors;
        this.render();
    }

    /** A row of buttons with the keyboard (how to settle the boxes, their journal): the arrows
     * move between them, going round, and Enter presses the one focused. */
    onButtonRowKeydown(ev) {
        const moves = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        if (!(ev.key in moves)) {
            return;
        }
        const buttons = [...ev.currentTarget.querySelectorAll("button:not(:disabled)")];
        const index = buttons.indexOf(document.activeElement);
        if (!buttons.length || index < 0) {
            return;
        }
        ev.preventDefault();
        buttons[(index + moves[ev.key] + buttons.length) % buttons.length].focus();
    }

    boxesReady() {
        const state = this.state;
        if (!this.boxTotal()) {
            return false;
        }
        if (state.boxDirection !== "return") {
            return true;
        }
        return state.boxSettle === "compensate" || (state.boxSettle === "pay" && Boolean(state.boxJournalId));
    }

    /**
     * Boxes of the tab, filtered by what is typed; those with a quantity typed stay in sight
     * so that what is going to be moved is always seen. The kinds the partner holds go first.
     */
    boxCards() {
        const found = new Set(this.searchBoxes(this.state.boxListSearch).map((box) => box.id));
        const stock = this.boxFilter() === "stock";
        const boxes = this.boxProducts().filter((box) =>
            (found.has(box.id) && (!stock || this.boxBalance(box.id) > 0)) || this.state.boxQty[box.id] > 0
        );
        const held = (box) => (this.boxBalance(box.id) ? 0 : 1);
        return boxes.sort((a, b) => held(a) - held(b));
    }

    /** The boxes shown: those in stock ("stock": the ones the customer holds, or we hold of
     * the supplier), or all of them ("all"). Until one is chosen, in stock when there is any. */
    boxFilter() {
        if (this.state.boxFilter) {
            return this.state.boxFilter;
        }
        return this.boxProducts().some((box) => this.boxBalance(box.id) > 0) ? "stock" : "all";
    }

    onBoxFilter(filter) {
        this.state.boxFilter = filter;
        this.focusAfterRender(".o_mercas_touch_box_list_search");
    }

    onBoxListSearchInput(ev) {
        this.state.boxListSearch = ev.target.value;
    }

    /** The boxes with the keyboard: Down or Enter in the search goes to the quantity of the
     * first box found (see onBoxQtyKeydown), Up to who gives them back, and Page Up or Page
     * Down changes it. */
    onBoxListSearchKeydown(ev) {
        if (ev.key === "PageDown" || ev.key === "PageUp") {
            // The customer gives back boxes, or we give them back to the supplier
            ev.preventDefault();
            this.onBoxDirection(this.state.boxDirection === "return" ? "deliver" : "return");
            return;
        }
        if (ev.key === "ArrowUp") {
            ev.preventDefault();
            document.querySelector(".o_mercas_touch_box_direction .btn-primary")?.focus();
            return;
        }
        if (ev.key !== "Enter" && ev.key !== "ArrowDown") {
            return;
        }
        ev.preventDefault();
        const input = document.querySelector(".o_mercas_touch_body .o_mercas_touch_box_move_qty");
        input?.focus();
        input?.select();
    }

    /**
     * The quantity of a box with the keyboard: up and down go to the box before or after (up
     * from the first one, to the search), + and - add or take a box, and Enter goes on to what
     * is left to choose (how to settle the amount, the journal) or to the button that moves the
     * boxes, which Enter then presses.
     */
    onBoxQtyKeydown(productId, ev) {
        if (ev.key === "+" || ev.key === "-") {
            ev.preventDefault();
            this.onBoxStep(productId, ev.key === "+" ? 1 : -1);
            return;
        }
        const inputs = [...document.querySelectorAll(".o_mercas_touch_body .o_mercas_touch_box_move_qty")];
        const index = inputs.indexOf(ev.target);
        let next = null;
        if (ev.key === "ArrowDown") {
            next = inputs[index + 1];
        } else if (ev.key === "ArrowUp") {
            next = index > 0 ? inputs[index - 1] : document.querySelector(".o_mercas_touch_box_list_search");
        } else if (ev.key === "Enter") {
            // The button when it can be pressed; otherwise a way to settle not chosen yet
            next = document.querySelector(".o_mercas_touch_move_boxes:not(:disabled)") ||
                document.querySelector(".o_mercas_touch_box_settle .btn-secondary:not(:disabled)");
        } else {
            return;
        }
        ev.preventDefault();
        if (next) {
            next.focus();
            next.select?.();
        }
    }

    boxBalance(productId) {
        const box = this.state.partner?.boxes.find((box) => box.product_id === productId);
        if (!box) {
            return 0;
        }
        return this.state.boxDirection === "return" ? box.customer : -box.supplier;
    }

    onBoxStep(productId, step) {
        const qty = Math.max(0, (this.state.boxQty[productId] || 0) + step);
        this.state.boxQty = { ...this.state.boxQty, [productId]: qty };
    }

    onBoxInput(productId, ev) {
        const qty = Math.max(0, parseInt(ev.target.value, 10) || 0);
        this.state.boxQty = { ...this.state.boxQty, [productId]: qty };
    }

    boxTotal() {
        return Object.values(this.state.boxQty).reduce((total, qty) => total + qty, 0);
    }

    async onMoveBoxes() {
        const lines = Object.entries(this.state.boxQty)
            .filter(([, qty]) => qty > 0)
            .map(([productId, qty]) => ({ product_id: parseInt(productId, 10), qty }));
        if (!lines.length || !this.boxesReady()) {
            return;
        }
        const giveBack = this.state.boxDirection === "return";
        const result = await this.run("move_boxes", [
            {
                uuid: this.newUuid(),
                partner_id: this.state.partner.id,
                direction: this.state.boxDirection,
                lines,
                ...(giveBack && { settle: this.state.boxSettle }),
                ...(giveBack && this.state.boxSettle === "pay" && { journal_id: this.state.boxJournalId }),
            },
        ]);
        if (!result) {
            return;
        }
        const direction = this.state.boxDirection;
        this.finishOperation({ kind: "boxes", direction, ...result.order });
        this.state.partner.boxes = result.boxes;
        this.state.boxDirection = direction;
        if (result.action) {
            await this.action.doAction(result.action, { onClose: () => this.reloadPartner() });
        }
    }

    async onOpenDocument() {
        const done = this.state.done;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: done.model,
            res_id: done.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ------------------------------------------------------------------
    // Lots
    // ------------------------------------------------------------------

    onLotSearchInput(ev) {
        this.state.lotSearch = ev.target.value;
        browser.clearTimeout(this.searchTimeout);
        this.searchTimeout = browser.setTimeout(() => this.loadLots(), SEARCH_DELAY);
    }

    async loadLots() {
        const lots = await this.orm.call(MODEL, "get_lots", [this.state.lotSearch]);
        if (this.state.mode === "lots") {
            this.state.lotList = lots;
            const ids = new Set(lots.map((lot) => lot.id));
            this.state.lotSelection = Object.fromEntries(
                Object.entries(this.state.lotSelection).filter(([id]) => ids.has(parseInt(id, 10)))
            );
        }
    }

    lotProgress(lot) {
        const base = Math.max(lot.purchased, lot.received, lot.sold + lot.scrapped + lot.stock, 1);
        const percent = (value) => `${Math.max(0, Math.min(100, (value / base) * 100))}%`;
        return { sold: percent(lot.sold), scrapped: percent(lot.scrapped), stock: percent(lot.stock) };
    }

    toggleLotSelection(lot) {
        const selection = { ...this.state.lotSelection };
        if (selection[lot.id]) {
            delete selection[lot.id];
        } else {
            selection[lot.id] = true;
        }
        this.state.lotSelection = selection;
    }

    /**
     * The lots with the keyboard. Each lot is a row: its check and its buttons (price, details,
     * labels, scrap). Left and right move along the row; up and down go to the lot before or
     * after, at the same place of the row (up from the first lot, to the search; down from the
     * last one, to the buttons of the lots selected). Enter (or the space) on the check selects
     * the lot; on a button, presses it.
     */
    onLotListKeydown(ev) {
        const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: "next", ArrowUp: "previous" };
        const card = ev.target.closest(".o_mercas_touch_lot_card");
        if (!card) {
            return;
        }
        const row = (lotCard) => [...lotCard.querySelectorAll(".o_mercas_touch_lot_select, button")];
        if (ev.key === "Enter" && ev.target.matches(".o_mercas_touch_lot_select")) {
            ev.preventDefault();
            ev.target.click();
            return;
        }
        if (!(ev.key in moves)) {
            return;
        }
        ev.preventDefault();
        const items = row(card);
        const index = items.indexOf(ev.target);
        let next;
        if (moves[ev.key] === 1) {
            next = items.slice(index + 1).find((item) => !item.disabled);
        } else if (moves[ev.key] === -1) {
            next = items.slice(0, index).reverse().find((item) => !item.disabled);
        } else {
            const cards = [...ev.currentTarget.querySelectorAll(".o_mercas_touch_lot_card")];
            const other = cards[cards.indexOf(card) + (moves[ev.key] === "next" ? 1 : -1)];
            if (other) {
                const item = row(other)[index];
                next = item && !item.disabled ? item : row(other)[0];
            } else if (moves[ev.key] === "previous") {
                next = document.querySelector(".o_mercas_touch_lot_search");
            } else {
                next = document.querySelector(".o_mercas_touch_lot_actions button:not(:disabled)");
            }
        }
        next?.focus();
    }

    /** The buttons of the lots selected: left and right between them, up back to the last lot. */
    onLotActionsKeydown(ev) {
        if (ev.key === "ArrowUp") {
            const checks = document.querySelectorAll(".o_mercas_touch_body .o_mercas_touch_lot_select");
            if (checks.length) {
                ev.preventDefault();
                checks[checks.length - 1].focus();
            }
        } else if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
            this.onButtonRowKeydown(ev);
        }
    }

    selectedLotIds() {
        return Object.keys(this.state.lotSelection).map((id) => parseInt(id, 10));
    }

    /** The form of the lot of the Mercas menu: purchases, sales, invoices, scraps and its
     * buttons (inventory, scrap, labels...). The lots are reloaded when it is closed. */
    /** The form of the lot, in a dialog: its data, the expiry date... */
    async onOpenLot(lot, onClose = () => this.loadLots()) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: lot.name,
            res_model: "stock.lot",
            res_id: lot.id,
            views: [[false, "form"]],
            target: "new",
            context: { dialog_size: "extra-large" },
        }, { onClose });
    }

    onScrapLot(lot) {
        this.lastLotId = lot.id;
        this.state.scrap = { lot, qty: "" };
    }

    onScrapInput(value) {
        this.state.scrap.qty = value;
    }

    async onConfirmScrap() {
        const scrap = this.state.scrap;
        const qty = this.parseNumber(scrap.qty);
        if (!(qty > 0)) {
            this.notification.add(_t("Enter the quantity to scrap."), { type: "warning" });
            return;
        }
        const lot = await this.run("scrap_lot", [scrap.lot.id, qty]);
        if (lot) {
            this.state.scrap = null;
            this.notification.add(_t("%(qty)s %(uom)s of the lot %(lot)s scrapped.", {
                qty: this.formatQty(qty), uom: lot.uom, lot: lot.name,
            }), { type: "success" });
            await this.loadLots();
        }
    }

    onLotPrice(lot) {
        this.lastLotId = lot.id;
        this.state.lotPrice = { lot, price: lot.sale_price ? this.formatInput(lot.sale_price) : "" };
    }

    onLotPriceInput(value) {
        this.state.lotPrice.price = value;
    }

    async onConfirmLotPrice() {
        const lotPrice = this.state.lotPrice;
        const price = this.parseNumber(lotPrice.price);
        if (!(price >= 0)) {
            this.notification.add(_t("Enter a valid price."), { type: "warning" });
            return;
        }
        const lot = await this.run("set_lot_sale_price", [lotPrice.lot.id, price]);
        if (lot) {
            this.state.lotPrice = null;
            this.notification.add(
                price
                    ? _t("The lot %(lot)s is sold from %(price)s.", { lot: lot.name, price: this.formatAmount(price) })
                    : _t("The lot %s is sold at the price of the product.", lot.name),
                { type: "success" }
            );
            await this.loadLots();
        }
    }

    async onInvoiceLots(mode) {
        const lotIds = this.selectedLotIds();
        if (!lotIds.length) {
            this.notification.add(_t("Select the lots to invoice."), { type: "warning" });
            return;
        }
        const action = await this.run("invoice_lots", [lotIds, mode]);
        this.state.lotSelection = {};
        await this.loadLots();
        if (action) {
            await this.action.doAction(action);
        }
    }

    /** The box labels of the lots, as many as boxes were bought, in the wizard of mercas_base. */
    async onPrintLotLabels(lotIds) {
        const action = await this.run("get_lot_label_action", [lotIds]);
        if (action) {
            await this.action.doAction(action, {
                onClose: () => {
                    if (this.state.mode === "labels") {
                        this.focusLabelSearch = true;
                        this.render();
                    }
                },
            });
        }
    }

    // ------------------------------------------------------------------
    // Damaged label: reprint the labels of a lot, scanned or typed
    // ------------------------------------------------------------------

    onLabelSearchInput(ev) {
        this.state.labelSearch = ev.target.value;
        browser.clearTimeout(this.searchTimeout);
        this.searchTimeout = browser.setTimeout(() => this.loadLabelLots(), SEARCH_DELAY);
    }

    /** Enter ends a typed code, and a scanner in keyboard mode writing in the field. */
    async onLabelSearchKeydown(ev) {
        if (this.focusFirstTile(ev, ".o_mercas_touch_label_lot")) {
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            await this.findLabel(ev.target.value);
        }
    }

    async loadLabelLots() {
        const search = this.state.labelSearch;
        const lots = await this.orm.call(MODEL, "search_label_lots", [search]);
        if (this.state.mode === "labels" && this.state.labelSearch === search) {
            this.state.labelLots = lots;
        }
        return lots;
    }

    /** The lot named exactly as the code goes straight to print; otherwise the lots found. */
    async findLabel(code) {
        browser.clearTimeout(this.searchTimeout);
        this.state.labelSearch = code.trim();
        const lots = await this.loadLabelLots();
        const exact = lots.filter((lot) => lot.exact);
        if (exact.length === 1) {
            await this.onPrintLotLabels([exact[0].id]);
        } else if (this.state.labelSearch && !lots.length) {
            this.notification.add(_t("No lot found for %s.", this.state.labelSearch), { type: "warning" });
            this.focusLabelSearch = true;
            this.render();
        }
    }

    // ------------------------------------------------------------------
    // Payments
    // ------------------------------------------------------------------

    toggleInvoice(invoice) {
        const ids = this.state.invoiceIds.includes(invoice.id)
            ? this.state.invoiceIds.filter((id) => id !== invoice.id)
            : [...this.state.invoiceIds, invoice.id];
        this.state.invoiceIds = ids;
        this.proposePaymentAmount();
    }

    toggleCredit(credit) {
        const ids = this.state.creditIds;
        this.state.creditIds = ids.includes(credit.id) ? ids.filter((id) => id !== credit.id) : [...ids, credit.id];
        this.proposePaymentAmount();
    }

    /** Credits chosen, applied to the invoices: a positive amount. */
    creditTotal() {
        return -(this.state.partner.credits || [])
            .filter((credit) => this.state.creditIds.includes(credit.id))
            .reduce((sum, credit) => sum + credit.residual, 0);
    }

    /** Propose the amount of the invoices chosen, less the credits chosen. */
    proposePaymentAmount() {
        const total = this.state.partner.invoices
            .filter((inv) => this.state.invoiceIds.includes(inv.id))
            .reduce((sum, inv) => sum + inv.residual, 0) - this.creditTotal();
        this.state.amount = total > 0 ? this.formatInput(total) : "";
    }

    onAmountInput(value) {
        this.state.amount = value;
    }

    onMemoInput(ev) {
        this.state.memo = ev.target.value;
    }

    onSelectJournal(journalId) {
        this.state.journalId = journalId;
        this.focusAfterRender(".o_mercas_touch_memo");
    }

    /** The checks of the invoices and the credits to collect, with the keyboard */
    paymentChecks() {
        return [...document.querySelectorAll(
            ".o_mercas_touch_body .o_mercas_touch_invoice input, .o_mercas_touch_body .o_mercas_touch_credit input"
        )];
    }

    /**
     * An invoice or a credit with the keyboard: the arrows go to the one before or after (down
     * from the last one, to the amount), Enter (or the space) marks or unmarks it.
     */
    onPaymentCheckKeydown(ev) {
        const checks = this.paymentChecks();
        const index = checks.indexOf(ev.target);
        let next = null;
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.click();
            return;
        } else if (ev.key === "ArrowDown" || ev.key === "ArrowRight") {
            next = checks[index + 1] || document.querySelector(".o_mercas_touch_amount");
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") {
            next = checks[index - 1];
        } else {
            return;
        }
        ev.preventDefault();
        next?.focus();
        next?.select?.();
    }

    /**
     * The amount with the keyboard: Enter works out the operation typed and goes on to the
     * journal (it doesn't collect: the button does), up goes back to the last invoice or credit.
     */
    onAmountKeydown(ev) {
        if (ev.key === "Enter") {
            this.onFloatKeydown(ev, this.state, "amount");
            document.querySelector(".o_mercas_touch_journal.btn-primary, .o_mercas_touch_journal")?.focus();
        } else if (ev.key === "ArrowUp") {
            const last = this.paymentChecks().at(-1);
            if (last) {
                ev.preventDefault();
                last.focus();
            }
        }
    }

    /** Enter in the memo goes to the button that collects, which Enter then presses. */
    onMemoKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            document.querySelector(".o_mercas_touch_register_payment:not(:disabled)")?.focus();
        }
    }

    async onRegisterPayment() {
        const credits = this.state.creditIds;
        const amount = this.parseNumber(this.state.amount) || 0;
        if (!(amount > 0) && !(credits.length && amount === 0)) {
            this.notification.add(_t("Enter the amount."), { type: "warning" });
            return;
        }
        if (credits.length && !this.state.invoiceIds.length) {
            this.notification.add(_t("Choose the invoices to apply the credit to."), { type: "warning" });
            return;
        }
        if (amount > 0 && !this.state.journalId) {
            this.notification.add(_t("Choose a journal."), { type: "warning" });
            return;
        }
        const payment = await this.run("register_payment", [
            {
                uuid: this.newUuid(),
                partner_id: this.state.partner.id,
                amount,
                journal_id: this.state.journalId,
                invoice_ids: this.state.invoiceIds,
                credit_line_ids: credits,
                memo: this.state.memo,
            },
        ]);
        if (payment) {
            this.finishOperation({ kind: "payment", model: "account.payment", ...payment });
        }
    }

    // ------------------------------------------------------------------
    // Scanner and other screens
    // ------------------------------------------------------------------

    async onBarcodeScanned(barcode) {
        if (!["sale", "purchase", "lots", "labels"].includes(this.state.mode) || this.state.sending) {
            return;
        }
        if (this.state.mode === "labels") {
            await this.findLabel(barcode);
            return;
        }
        if (this.state.mode === "lots") {
            this.state.lotSearch = barcode;
            await this.loadLots();
            return;
        }
        if (!this.state.partner || this.state.done) {
            this.notification.add(
                _t("Choose an order in draft or start a new one first."),
                { type: "warning" }
            );
            return;
        }
        const found = await this.orm.call(MODEL, "find_by_barcode", [barcode]);
        const lots = found.lots.filter((lot) => this.productById(lot.product_id));
        if (this.state.mode === "sale" && lots.length) {
            const withStock = lots.filter((lot) => lot.available > 0);
            if (withStock.length === 1) {
                const lot = withStock[0];
                this.state.product = this.productById(lot.product_id);
                this.state.lots = [lot];
                this.onSelectLot(lot);
                return;
            }
            if (!withStock.length) {
                this.notification.add(_t("The lot %s has no stock.", barcode), { type: "warning" });
                return;
            }
        }
        const productId = lots[0]?.product_id || found.product_id;
        const product = productId && this.productById(productId);
        if (product && this.isProductAllowed(product)) {
            await this.onSelectProduct(product);
        } else {
            this.notification.add(_t("Nothing found for %s.", barcode), { type: "warning" });
        }
    }

    async onLotsChanged(payload) {
        if (payload.company_id !== this.state.data?.company_id) {
            return;
        }
        const product = this.state.product;
        if (this.state.mode === "sale") {
            await this.loadSellableProducts();
        }
        if (this.state.mode === "sale" && product?.tracking && payload.product_ids.includes(product.id)) {
            await this.loadProductLots();
        } else if (this.state.mode === "lots" && !this.state.scrap && !this.state.lotPrice) {
            await this.loadLots();
        } else if (!this.state.mode) {
            await this.loadHome();
        }
    }

    // ------------------------------------------------------------------
    // Formatting
    // ------------------------------------------------------------------

    formatAmount(amount) {
        return formatCurrency(amount, this.state.data.currency_id);
    }

    formatQty(qty) {
        return formatFloat(qty, { digits: [false, 3], trailingZeros: false });
    }

    /** A number to edit: without thousands separators, so that it reads well in a field. */
    formatInput(value) {
        return formatFloat(value, { digits: [false, 3], trailingZeros: false, thousandsSep: "" });
    }

    formatDateTimeShort(value) {
        return value ? formatDateTime(deserializeDateTime(value), { showSeconds: false }) : "";
    }

    formatDate(value) {
        return value ? formatDate(deserializeDateTime(value)) : "";
    }

    /** A date without time, as the date of an invoice. */
    formatDay(value) {
        return value ? formatDate(deserializeDate(value)) : "";
    }
}

registry.category("actions").add("mercas_touch.screen", TouchScreen);
