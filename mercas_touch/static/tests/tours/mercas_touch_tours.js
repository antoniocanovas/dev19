import { registry } from "@web/core/registry";

// Data made by the Python test: a customer, a supplier, a pear tracked by lots with a lot in
// stock (TOUR-LOT) and a box product

registry.category("web_tour.tours").add("mercas_touch_sale_tour", {
    steps: () => [
        {
            content: "Open the sale",
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            content: "A new quotation: the customer is asked",
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            content: "Search the customer",
            trigger: ".o_mercas_touch_partner_search",
            run: "edit Tour Customer",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Customer)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner_name:contains(Tour Customer)",
        },
        {
            content: "Choose the product",
            trigger: ".o_mercas_touch_product:contains(Tour Pear)",
            run: "click",
        },
        {
            content: "Choose its lot",
            trigger: ".o_mercas_touch_lot:contains(TOUR-LOT)",
            run: "click",
        },
        {
            content: "Type the quantity with the keypad",
            trigger: ".o_mercas_touch_numpad_key:text(1)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_numpad_key:text(2)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_qty:value(12)",
        },
        {
            content: "Change the price",
            trigger: ".o_mercas_touch_price",
            run: "edit 1.5",
        },
        {
            content: "Two boxes",
            trigger: ".o_mercas_touch_box_qty button[title='One box more']",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_box_qty button[title='One box more']",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_box_qty_input:value(2)",
        },
        {
            content: "The box of the product is proposed",
            trigger: ".o_mercas_touch_box_search:value(Tour Box)",
        },
        {
            content: "Look for another kind of box by its internal reference",
            trigger: ".o_mercas_touch_box_search",
            run: "edit cj-77",
        },
        {
            trigger: ".o_mercas_touch_box_choices:not(:has(.o_mercas_touch_box_choice:contains(Tour Box)))",
        },
        {
            content: "Choose it among the results",
            trigger: ".o_mercas_touch_box_choice:contains(Tour Crate)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_box_search:value(Tour Crate)",
        },
        {
            trigger: ".o_mercas_touch_add",
            run: "click",
        },
        {
            content: "The line is in the ticket",
            trigger: ".o_mercas_touch_line:contains(TOUR-LOT):contains(12):contains(Tour Crate)",
        },
        {
            trigger: ".o_mercas_touch_total_boxes:text(2)",
        },
        {
            content: "Sell and deliver",
            trigger: ".o_mercas_touch_sell:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(delivered)",
        },
        {
            content: "The customer now holds the boxes",
            trigger: ".o_mercas_touch_partner_badges:contains(Tour Crate)",
        },
        {
            content: "Invoice the sale",
            trigger: ".o_mercas_touch_invoice_sale",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done_invoice:contains(to collect)",
        },
        {
            content: "And collect it: the payment opens with the invoice and its amount",
            trigger: ".o_mercas_touch_collect_invoice",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_invoice input:checked",
        },
        {
            trigger: ".o_mercas_touch_amount:value(18)",
        },
        {
            trigger: ".o_mercas_touch_register_payment",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(registered)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_purchase_tour", {
    steps: () => [
        {
            content: "Open the purchase with its function key",
            trigger: ".o_mercas_touch_home",
            run: "press F2",
        },
        {
            content: "A new purchase: the supplier is asked",
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner_search",
            run: "edit Tour Supplier",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Supplier)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_product:contains(Tour Pear)",
            run: "click",
        },
        {
            content: "No lots to choose: a new one is made",
            trigger: ".o_mercas_touch_qty",
            run: "edit 80",
        },
        {
            trigger: ".o_mercas_touch_price",
            run: "edit 0.9",
        },
        {
            trigger: ".o_mercas_touch_lot_name",
            run: "edit TOUR-NEW",
        },
        {
            content: "One box, to print its label",
            trigger: ".o_mercas_touch_box_qty button[title='One box more']",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_add",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_purchase:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done_lots:contains(TOUR-NEW)",
        },
        {
            content: "Print the box labels of the new lot",
            trigger: ".o_mercas_touch_print_labels",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:contains(TOUR-NEW)",
        },
        {
            trigger: ".modal button[name=action_print]",
            run: "click",
        },
        {
            content: "The wizard closes once the labels are downloaded",
            trigger: "body:not(:has(.modal)) .o_mercas_touch_done",
        },
        {
            content: "Go to the lots",
            trigger: ".o_mercas_touch_tabs button[title='Lots']",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_lot_search",
            run: "edit TOUR-NEW",
        },
        {
            trigger: ".o_mercas_touch_lot_card:contains(TOUR-NEW) .o_mercas_touch_scrap_lot",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_scrap_qty",
            run: "edit 5",
        },
        {
            trigger: ".o_mercas_touch_confirm_scrap",
            run: "click",
        },
        {
            content: "The scrap is in the lot",
            trigger: ".o_mercas_touch_lot_card:contains(TOUR-NEW):contains(Scrapped 5)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_payment_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_mode_payment",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner_search",
            run: "edit Tour Customer",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Customer)",
            run: "click",
        },
        {
            content: "Choose the invoice: its amount is proposed",
            trigger: ".o_mercas_touch_invoice input",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_amount:value(100)",
        },
        {
            content: "Collect only a part",
            trigger: ".o_mercas_touch_numpad_clear",
            run: "click",
        },
        {
            content: "60 as an operation of the keypad: 2 × 30 =",
            trigger: ".o_mercas_touch_numpad_key:text(2)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_numpad_operator:text(×)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_numpad_key:text(3)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_numpad_key:text(0)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_amount:value(2×30)",
        },
        {
            trigger: ".o_mercas_touch_numpad_equals",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_amount:value(60)",
        },
        {
            trigger: ".o_mercas_touch_register_payment",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(registered)",
        },
    ],
});

const addPearLine = (qty) => [
    {
        trigger: ".o_mercas_touch_product:contains(Tour Pear)",
        run: "click",
    },
    {
        trigger: ".o_mercas_touch_lot:contains(TOUR-LOT)",
        run: "click",
    },
    {
        trigger: ".o_mercas_touch_qty",
        run: `edit ${qty}`,
    },
    {
        trigger: ".o_mercas_touch_add",
        run: "click",
    },
];

registry.category("web_tour.tours").add("mercas_touch_price_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Customer)",
            run: "click",
        },
        ...addPearLine(10),
        ...addPearLine(5),
        {
            content: "Change the price of the second line from the ticket",
            trigger: ".o_mercas_touch_line:eq(1) .o_mercas_touch_line_price",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_price_editor:contains(Line 2 of 2)",
        },
        {
            content: "The first key replaces the price",
            trigger: ".o_mercas_touch_numpad_key:text(3)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_price_edit_input:value(3)",
        },
        {
            trigger: ".o_mercas_touch_price_edit_subtotal:contains(15.00)",
        },
        {
            content: "Previous line",
            trigger: ".o_mercas_touch_price_prev",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_price_editor:contains(Line 1 of 2)",
        },
        {
            content: "With the keyboard: Enter writes it and goes to the next line",
            trigger: ".o_mercas_touch_price_edit_input",
            run: "edit 2.5 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_price_editor:contains(Line 2 of 2)",
        },
        {
            trigger: ".o_mercas_touch_price_edit_input:value(3)",
        },
        {
            content: "Past the last line, the editor closes",
            trigger: ".o_mercas_touch_price_next",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_body:not(:has(.o_mercas_touch_price_editor))",
        },
        {
            trigger: ".o_mercas_touch_total:contains(40.00)",
        },
        {
            trigger: ".o_mercas_touch_sell:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(delivered)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_quotation_tour", {
    steps: () => [
        {
            content: "The sale starts from the quotations in draft",
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            content: "Resume the quotation made in the backend",
            trigger: ".o_mercas_touch_draft:contains(Tour Customer):contains(1 line)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_line:contains(TOUR-LOT):contains(7)",
        },
        {
            trigger: ".o_mercas_touch_order_name",
        },
        ...addPearLine(4),
        {
            content: "Each change is saved in the quotation (once the line is added)",
            trigger: ".o_mercas_touch_ticket:has(.o_mercas_touch_line:eq(1)) .o_mercas_touch_save_state:contains(Saved in)",
        },
        {
            content: "Leave it, to go on later",
            trigger: ".o_mercas_touch_back",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Tour Customer):contains(2 lines)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_line:eq(1):contains(4)",
        },
        {
            trigger: ".o_mercas_touch_sell:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(delivered)",
        },
        {
            content: "A new sale starts again from the quotations",
            trigger: ".o_mercas_touch_new",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
        },
        {
            trigger: ".o_mercas_touch_body:not(:has(.o_mercas_touch_draft:contains(Tour Customer)))",
        },
    ],
});

const addPurchaseLine = (qty, lotName) => [
    {
        trigger: ".o_mercas_touch_product:contains(Tour Pear)",
        run: "click",
    },
    {
        trigger: ".o_mercas_touch_qty",
        run: `edit ${qty}`,
    },
    {
        trigger: ".o_mercas_touch_lot_name",
        run: `edit ${lotName}`,
    },
    {
        trigger: ".o_mercas_touch_add",
        run: "click",
    },
    {
        trigger: `.o_mercas_touch_line:contains(${lotName})`,
    },
    {
        trigger: ".o_mercas_touch_save_state:contains(Saved in)",
    },
];

registry.category("web_tour.tours").add("mercas_touch_purchase_drafts_tour", {
    steps: () => [
        {
            content: "The purchase starts from the purchases in draft",
            trigger: ".o_mercas_touch_mode_purchase",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Supplier)",
            run: "click",
        },
        ...addPurchaseLine(30, "DRAFT-A"),
        {
            content: "Go to another purchase without closing this one",
            trigger: ".o_mercas_touch_back",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Backend Supplier)",
            run: "click",
        },
        ...addPurchaseLine(12, "DRAFT-B"),
        {
            trigger: ".o_mercas_touch_back",
            run: "click",
        },
        {
            content: "The first purchase is there as it was left",
            trigger: ".o_mercas_touch_draft:contains(Tour Supplier):contains(1 line)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_line:contains(DRAFT-A):contains(30)",
        },
        {
            trigger: ".o_mercas_touch_purchase:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done_lots:contains(DRAFT-A)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_to_invoice_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            content: "The sales still to invoice",
            trigger: ".o_mercas_touch_draft_filter_to_invoice",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Tour Customer)",
            run: "click",
        },
        {
            content: "Its summary, with its lines",
            trigger: ".o_mercas_touch_summary_lines:contains(TOUR-LOT)",
        },
        {
            trigger: ".o_mercas_touch_invoice_sale",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done_invoice:contains(to collect)",
        },
        {
            trigger: ".o_mercas_touch_back_to_list",
            run: "click",
        },
        {
            content: "Invoiced, it isn't to invoice anymore",
            trigger: ".o_mercas_touch_draft_filters .btn-primary:contains(To invoice)",
        },
        {
            trigger: ".o_mercas_touch_body:not(:has(.o_mercas_touch_draft:contains(Tour Customer)))",
        },
        {
            content: "All the sales",
            trigger: ".o_mercas_touch_draft_filter_all",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Tour Customer) .text-bg-success",
        },
        {
            content: "The purchases to invoice",
            trigger: ".o_mercas_touch_tabs button[title='Purchase']",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft_filter_to_invoice",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Tour Supplier)",
            run: "click",
        },
        {
            content: "Its lot, under sale settlement and with stock, takes an advance",
            trigger: ".o_mercas_touch_purchase_advance",
            run: "click",
        },
        {
            content: "The bill opens in a dialog to review it",
            trigger: ".modal .o_form_view",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_no_numpad_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Customer)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_product:contains(Tour Pear)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_lot:contains(TOUR-LOT)",
            run: "click",
        },
        {
            content: "Hidden in the preferences of the user: the line without the keypad",
            trigger: ".o_mercas_touch_qty",
        },
        {
            trigger: ".o_mercas_touch_body:not(:has(.o_mercas_touch_numpad))",
        },
        {
            trigger: ".o_mercas_touch_qty",
            run: "edit 4",
        },
        {
            trigger: ".o_mercas_touch_add",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_line .o_mercas_touch_line_price",
            run: "click",
        },
        {
            content: "The price is typed with the keyboard",
            trigger: ".o_mercas_touch_price_edit_input",
            run: "edit 2.5 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_body:not(:has(.o_mercas_touch_price_editor))",
        },
        {
            trigger: ".o_mercas_touch_total:contains(10.00)",
        },
        {
            trigger: ".o_mercas_touch_sell:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(delivered)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_enter_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_mode_sale",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner:contains(Tour Customer)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_product:contains(Tour Pear)",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_lot:contains(TOUR-LOT)",
            run: "click",
        },
        {
            content: "The gross weight of the scale, and Enter goes to the net weight",
            trigger: ".o_mercas_touch_gross",
            run: "edit 6*2 && press Enter",
        },
        {
            content: "The operation is worked out on the way",
            trigger: ".o_mercas_touch_gross:value(12)",
        },
        {
            trigger: ".o_mercas_touch_qty:focus",
            run: "press Enter",
        },
        {
            content: "Then the price",
            trigger: ".o_mercas_touch_price:focus",
            run: "edit 2.5 && press Enter",
        },
        {
            content: "Shift+Enter goes back to the price",
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "press Shift+Enter",
        },
        {
            trigger: ".o_mercas_touch_price:focus",
            run: "press Enter",
        },
        {
            content: "With boxes, Enter goes to their kind",
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "edit 2 && press Enter",
        },
        {
            content: "Enter keeps the kind of box of the product and, as the last field, adds the line",
            trigger: ".o_mercas_touch_box_search:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_line:contains(Tour Pear)",
        },
        {
            trigger: ".o_mercas_touch_total:contains(30.00)",
        },
        {
            trigger: ".o_mercas_touch_sell:enabled",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_done:contains(delivered)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_keyboard_tour", {
    steps: () => [
        {
            content: "The main menu has the focus on its first mode; the arrows move between them",
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_mode_purchase:focus",
            run: "press ArrowUp",
        },
        {
            content: "Enter opens the mode focused",
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press Enter",
        },
        {
            content: "The first field of the screen has the focus: the search of the quotations",
            trigger: ".o_mercas_touch_quotation_search:focus",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            content: "Enter in the search chooses the only customer found",
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "edit Tour Cust && press Enter",
        },
        {
            content: "Then the search of the products",
            trigger: ".o_mercas_touch_product_search:focus",
            run: "edit Tour Pe && press Enter",
        },
        {
            content: "The lots of the product: the first one has the focus, the arrows move to the next",
            trigger: ".o_mercas_touch_lot:focus:contains(TOUR-LOT)",
            run: "press ArrowRight",
        },
        {
            content: "Enter chooses the lot focused",
            trigger: ".o_mercas_touch_lot:focus:contains(TOUR-LOT-2)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_entry:contains(TOUR-LOT-2)",
        },
        {
            content: "The line starts in the gross weight",
            trigger: ".o_mercas_touch_gross:focus",
            run: "edit 3 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_qty:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_price:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "press Enter",
        },
        {
            content: "Added, the search of the products again for the next line",
            trigger: ".o_mercas_touch_product_search:focus",
        },
        {
            trigger: ".o_mercas_touch_line:contains(Tour Pear)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_keyboard_purchase_tour", {
    steps: () => [
        {
            content: "The purchase from the main menu, with the arrows and Enter",
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_mode_purchase:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_quotation_search:focus",
        },
        {
            trigger: ".o_mercas_touch_new_draft",
            run: "click",
        },
        {
            content: "Two suppliers found: Down goes to the first one, the arrows between them",
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "edit Tour Supplier",
        },
        {
            content: "The search done: only the two suppliers",
            trigger: ".o_mercas_touch_grid:has(.o_mercas_touch_partner:nth-child(2):contains(Tour Supplier Bis)):not(:has(.o_mercas_touch_partner:nth-child(3)))",
        },
        {
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_partner:focus:not(:contains(Bis))",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_partner:focus:contains(Tour Supplier Bis)",
            run: "press ArrowLeft",
        },
        {
            content: "Up from the first row goes back to the search",
            trigger: ".o_mercas_touch_partner:focus:not(:contains(Bis))",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "press ArrowDown",
        },
        {
            content: "Enter chooses the supplier focused",
            trigger: ".o_mercas_touch_partner:focus:not(:contains(Bis))",
            run: "press Enter",
        },
        {
            content: "Two products found: the same with the arrows",
            trigger: ".o_mercas_touch_product_search:focus",
            run: "edit Tour P",
        },
        {
            trigger: ".o_mercas_touch_product:contains(Tour Plum)",
        },
        {
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_product:focus:contains(Tour Pear)",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_product:focus:contains(Tour Plum)",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_product:focus:contains(Tour Pear)",
            run: "press Enter",
        },
        {
            content: "The line of the purchase with Enter, to the lot and the sale price",
            trigger: ".o_mercas_touch_gross:focus",
            run: "edit 20 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_qty:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_price:focus",
            run: "edit 1 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "press Enter",
        },
        {
            content: "The country of origin is in the way of Enter (its states, only with a country)",
            trigger: ".o_mercas_touch_origin_country:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_lot_name:focus",
            run: "edit TOUR-KEY && press Enter",
        },
        {
            trigger: ".o_mercas_touch_sale_price:focus",
            run: "press Enter",
        },
        {
            content: "The firm negotiation last: Enter adds the line",
            trigger: ".o_mercas_touch_firm:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_line:contains(TOUR-KEY)",
        },
        {
            trigger: ".o_mercas_touch_purchase:enabled",
            run: "click",
        },
        {
            content: "Done: the main button has the focus",
            trigger: ".o_mercas_touch_done_lots:contains(TOUR-KEY)",
        },
        {
            trigger: ".o_mercas_touch_done_actions .o_mercas_touch_new:focus",
            run: "press ArrowLeft",
        },
        {
            content: "The arrows go between the buttons",
            trigger: ".o_mercas_touch_done_actions .btn:not(.o_mercas_touch_new):focus",
        },
        {
            content: "Deliver boxes: the boxes of the supplier, given back to them",
            trigger: ".o_mercas_touch_deliver_boxes",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner_name:contains(Tour Supplier)",
        },
        {
            trigger: ".o_mercas_touch_box_direction_deliver.btn-primary",
        },
        {
            content: "The boxes: the customer chosen with Enter",
            trigger: ".o_mercas_touch_box_list_search",
            run: "press F3",
        },
        {
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "edit Tour Customer && press Enter",
        },
        {
            content: "Page Down changes who gives back the boxes, Page Up back",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press PageDown",
        },
        {
            trigger: ".o_mercas_touch_box_direction_deliver.btn-primary",
        },
        {
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press PageUp",
        },
        {
            trigger: ".o_mercas_touch_box_direction_return.btn-primary",
        },
        {
            content: "Up goes to who gives them back, down to the search again",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_box_direction_return:focus",
            run: "press ArrowDown",
        },
        {
            content: "Enter in the search goes to the quantity of the box found",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "edit CJ-77 && press Enter",
        },
        {
            content: "The only kind found: its boxes, + adds one",
            trigger: ".o_mercas_touch_box_entry:contains(Tour Crate) .o_mercas_touch_box_entry_qty:focus",
            // "press +" would be read as a combination of keys
            run() {
                for (let i = 0; i < 2; i++) {
                    this.anchor.dispatchEvent(new KeyboardEvent("keydown", { key: "+", bubbles: true }));
                }
            },
        },
        {
            content: "Enter adds the line, back to the search",
            trigger: ".o_mercas_touch_box_entry_qty:focus:value(2)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_line:contains(Tour Crate) .o_mercas_touch_box_line_qty:contains(2)",
        },
        {
            content: "A second kind, chosen with the arrows",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "edit Tour Box",
        },
        {
            content: "The search done: only that kind",
            trigger: ".o_mercas_touch_grid:has(.o_mercas_touch_box:contains(Tour Box)):not(:has(.o_mercas_touch_box:contains(Tour Crate)))",
        },
        {
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_box:focus:contains(Tour Box)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_entry_qty:focus",
            run: "press 3 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_lines:has(.o_mercas_touch_box_line:nth-child(2))",
        },
        {
            content: "F8 goes to the lines: Enter changes one, Delete removes it",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press F8",
        },
        {
            trigger: ".o_mercas_touch_box_line:nth-child(2) .o_mercas_touch_line_info:focus",
            run: "press ArrowRight",
        },
        {
            content: "Enter on the trash removes the line",
            trigger: ".o_mercas_touch_box_line:nth-child(2) .o_mercas_touch_remove_line:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_lines:not(:has(.o_mercas_touch_box_line:nth-child(2))) .o_mercas_touch_remove_line:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_box_line:contains(Tour Crate) .o_mercas_touch_line_info:focus",
            run: "press Enter",
        },
        {
            content: "Its boxes again; Escape leaves them as they were",
            trigger: ".o_mercas_touch_box_entry_qty:focus:value(2)",
            run: "press Escape",
        },
        {
            content: "Down from the last line goes to how to settle the amount, up back",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press F8",
        },
        {
            trigger: ".o_mercas_touch_box_line .o_mercas_touch_line_info:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_box_pay:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_box_line .o_mercas_touch_line_info:focus",
            run: "press ArrowDown",
        },
        {
            content: "Paid now",
            trigger: ".o_mercas_touch_box_pay:focus",
            run: "press Enter",
        },
        {
            content: "Then the journal proposed; the arrows go to another one",
            trigger: ".o_mercas_touch_box_journal.btn-primary:focus",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_box_journal.btn-secondary:focus",
            run: "press Enter",
        },
        {
            content: "The journal chosen, Enter goes to the button that moves the boxes",
            trigger: ".o_mercas_touch_box_journal.btn-primary:not(:focus)",
        },
        {
            content: "Up from the button goes to the journal, down back to the button",
            trigger: ".o_mercas_touch_move_boxes:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_box_journal.btn-primary:focus",
            run: "press ArrowDown",
        },
        {
            content: "Ctrl+Enter moves the boxes",
            trigger: ".o_mercas_touch_move_boxes:focus",
            run: "press Control+Enter",
        },
        {
            trigger: ".o_mercas_touch_done:contains(Boxes registered)",
        },
        {
            content: "The damaged label: the lots found with the arrows, Enter prints",
            trigger: ".o_mercas_touch_done",
            run: "press F6",
        },
        {
            trigger: ".o_mercas_touch_label_search:focus",
            run: "edit TOUR-KEY",
        },
        {
            content: "The search done: the lot named as typed is marked",
            trigger: ".o_mercas_touch_label_lot.border-primary:contains(TOUR-KEY)",
        },
        {
            trigger: ".o_mercas_touch_label_search:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_label_lot:focus",
            run: "press Enter",
        },
        {
            trigger: ".modal .o_data_row",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_keyboard_payment_tour", {
    steps: () => [
        {
            content: "The payments from the main menu: up from the first mode goes round",
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_mode_labels:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_mode_payment:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_partner_search:focus",
            run: "edit Tour Customer && press Enter",
        },
        {
            content: "The first invoice has the focus; down goes to the second one, Enter marks it",
            trigger: ".o_mercas_touch_invoice:eq(0) input:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_invoice:eq(1) input:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_amount:value(30)",
        },
        {
            content: "Down from the last invoice goes to the amount",
            trigger: ".o_mercas_touch_invoice:eq(1) input:focus:checked",
            run: "press ArrowDown",
        },
        {
            content: "Enter in the amount goes to the journal, without collecting",
            trigger: ".o_mercas_touch_amount:focus",
            run: "edit 20 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_journal.btn-primary:focus",
            run: "press ArrowRight",
        },
        {
            content: "Enter chooses the journal and goes to the memo",
            trigger: ".o_mercas_touch_journal.btn-secondary:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_memo:focus",
            run: "edit KEYBOARD && press Enter",
        },
        {
            content: "Enter in the memo goes to the button, Enter collects",
            trigger: ".o_mercas_touch_register_payment:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_done:contains(registered)",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_keyboard_lots_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_home",
            run: "press F4",
        },
        {
            trigger: ".o_mercas_touch_lot_search:focus",
            run: "edit TOUR-LOT",
        },
        {
            content: "The search done: only the two lots of the tour",
            trigger: ".o_mercas_touch_lot_grid:has(.o_mercas_touch_lot_card:eq(1)):not(:has(.o_mercas_touch_lot_card:not(:contains(TOUR-LOT))))",
        },
        {
            content: "Down from the search goes to the first lot, Enter selects it",
            trigger: ".o_mercas_touch_lot_search:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(0) .o_mercas_touch_lot_select:focus",
            run: "press Enter",
        },
        {
            content: "Right goes along the buttons of the lot, down to the same button of the next one",
            trigger: ".o_mercas_touch_lot_card:eq(0).border-primary .o_mercas_touch_lot_select:focus:checked",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(0) .o_mercas_touch_lot_price_button:focus",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(1) .o_mercas_touch_lot_price_button:focus",
            run: "press Enter",
        },
        {
            content: "Enter in the price goes to Save, Enter saves",
            trigger: ".o_mercas_touch_lot_price_input:focus",
            run: "edit 3 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_confirm_lot_price:focus",
            run: "press Enter",
        },
        {
            content: "Back in the list, the lot left has the focus",
            trigger: ".o_mercas_touch_lot_card:eq(1) .o_mercas_touch_lot_select:focus",
            run: "press ArrowLeft",
        },
        {
            content: "Left from the check stays; the scrap is the last button",
            trigger: ".o_mercas_touch_lot_card:eq(1) .o_mercas_touch_lot_select:focus",
            run: "press ArrowRight && press ArrowRight && press ArrowRight && press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(1) .o_mercas_touch_scrap_lot:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_scrap_qty:focus",
            run: "edit 1 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_confirm_scrap:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(1):contains(Scrapped 1) .o_mercas_touch_lot_select:focus",
            run: "press ArrowDown",
        },
        {
            content: "Down from the last lot goes to the buttons of the lots selected",
            trigger: ".o_mercas_touch_selected_labels:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(1) .o_mercas_touch_lot_select:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_lot_card:eq(0) .o_mercas_touch_lot_select:focus",
            run: "press ArrowUp",
        },
        {
            content: "Up from the first lot goes back to the search",
            trigger: ".o_mercas_touch_lot_search:focus",
        },
    ],
});

registry.category("web_tour.tours").add("mercas_touch_keyboard_pallets_tour", {
    steps: () => [
        {
            trigger: ".o_mercas_touch_home",
            run: "press F1",
        },
        {
            trigger: ".o_mercas_touch_quotation_search:focus",
            run: "edit Tour Customer && press Enter",
        },
        {
            trigger: ".o_mercas_touch_open_pallets:enabled",
            run: "click",
        },
        {
            content: "The first chip of the boxes not on a pallet has the focus; Enter chooses it",
            trigger: ".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip:focus",
            run: "press Enter",
        },
        {
            content: "The boxes to move, typed; Enter goes to where they can be put: a new pallet",
            trigger: ".o_mercas_touch_pallets_move_qty:focus:value(8)",
            run: "press 3",
        },
        {
            trigger: ".o_mercas_touch_pallets_move_qty:focus:value(3)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_pallet_add:focus",
            run: "press Enter",
        },
        {
            content: "Put there, back to the boxes left",
            trigger: ".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip:focus:contains(5)",
            run: "press Enter",
        },
        {
            content: "- takes a box",
            trigger: ".o_mercas_touch_pallets_move_qty:focus:value(5)",
            run() {
                this.anchor.dispatchEvent(new KeyboardEvent("keydown", { key: "-", bubbles: true }));
            },
        },
        {
            trigger: ".o_mercas_touch_pallets_move_qty:focus:value(4)",
            run: "press Enter",
        },
        {
            content: "The arrows go between the pallets where they can be put",
            trigger: ".o_mercas_touch_pallet_drop:focus:contains(Put 4 here)",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_pallet_add:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_pallet_drop:focus",
            run: "press Enter",
        },
        {
            content: "Right goes to the chip of the pallet",
            trigger: ".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip:focus:contains(1)",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_pallet:not(.o_mercas_touch_pallet_loose) .o_mercas_touch_pallet_chip:focus:contains(7)",
            run: "press Enter",
        },
        {
            content: "Escape leaves the boxes chosen, not the pallets",
            trigger: ".o_mercas_touch_pallets_move_qty:focus:value(7)",
            run: "press Escape",
        },
        {
            trigger: ".o_mercas_touch_pallets:not(:has(.o_mercas_touch_pallets_move)) .o_mercas_touch_pallet_chip:focus",
        },
        {
            content: "Delete on a pallet asks to remove it: kept",
            trigger: ".o_mercas_touch_pallet:not(.o_mercas_touch_pallet_loose) .o_mercas_touch_pallet_chip",
            run() {
                this.anchor.focus();
                this.anchor.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
            },
        },
        {
            trigger: ".modal:contains(7 boxes) .btn-secondary:contains(Keep it)",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
        {
            trigger: ".o_mercas_touch_pallets_save",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_ticket",
        },
    ],
});

const pressKey = (key) =>
    function () {
        // "press +" would be read as a combination of keys
        this.anchor.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    };

registry.category("web_tour.tours").add("mercas_touch_keyboard_order_tour", {
    steps: () => [
        {
            content: "Right from the modes goes to the dashboard, left back",
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_home_pending button:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_mode_sale:focus",
            run: "press ArrowRight",
        },
        {
            content: "Enter opens the quotations in progress",
            trigger: ".o_mercas_touch_home_pending button:focus",
            run: "press Enter",
        },
        {
            content: "Page Down and Page Up change the filter of the quotations",
            trigger: ".o_mercas_touch_quotation_search:focus",
            run: "press PageDown",
        },
        {
            trigger: ".o_mercas_touch_draft_filter_to_invoice.btn-primary",
        },
        {
            trigger: ".o_mercas_touch_quotation_search:focus",
            run: "press PageUp",
        },
        {
            trigger: ".o_mercas_touch_draft_filter_draft.btn-primary",
        },
        {
            trigger: ".o_mercas_touch_draft:contains(Tour Customer)",
        },
        {
            trigger: ".o_mercas_touch_quotation_search:focus",
            run: "edit Tour Customer && press Enter",
        },
        {
            content: "Page Down and Page Up change the category of the catalog",
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press PageDown",
        },
        {
            trigger: ".o_mercas_touch_category.btn-primary",
        },
        {
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press PageUp",
        },
        {
            trigger: ".o_mercas_touch_categories:not(:has(.o_mercas_touch_category.btn-primary))",
        },
        {
            content: "F8 and F9 in the header, with what they open",
            trigger: ".o_mercas_touch_tab_lines:enabled .o_mercas_touch_tab_label:contains(Lines)",
        },
        {
            trigger: ".o_mercas_touch_tab_pallets:enabled",
        },
        {
            content: "F8 goes to the ticket; P changes the price of the line",
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press F8",
        },
        {
            content: "The line is a row: right to the price and the trash, left back, and left from the product to the search",
            trigger: ".o_mercas_touch_line_info:focus",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_line_price:focus",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_remove_line:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_line_price:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_line_info:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press F8",
        },
        {
            trigger: ".o_mercas_touch_line_info:focus",
            run: "press p",
        },
        {
            trigger: ".o_mercas_touch_price_edit_input:focus",
            run: "edit 3 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_line_price:contains(3)",
        },
        {
            content: "Enter on the line changes it: the attributes first",
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press F8",
        },
        {
            trigger: ".o_mercas_touch_line_info:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_attribute_value:focus:contains(Extra)",
            run: "press ArrowRight",
        },
        {
            content: "Enter chooses the value and goes to the next attribute",
            trigger: ".o_mercas_touch_attribute_value:focus:contains(First)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_attribute_value:focus:contains(03)",
            run: "press ArrowRight",
        },
        {
            trigger: ".o_mercas_touch_attribute_value:focus:contains(04)",
            run: "press Enter",
        },
        {
            content: "Then the first field; Shift+Enter goes back to the attributes",
            trigger: ".o_mercas_touch_gross:focus",
            run: "press Shift+Enter",
        },
        {
            trigger: ".o_mercas_touch_attribute_value.btn-primary:focus:contains(04)",
            run: "press ArrowDown",
        },
        {
            trigger: ".o_mercas_touch_gross:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_qty:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_price:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_search:focus",
            run: "press Enter",
        },
        {
            content: "A second line, its attributes with Enter",
            trigger: ".o_mercas_touch_line_attributes:contains(First · 04)",
        },
        {
            trigger: ".o_mercas_touch_product_search:focus",
            run: "edit Tour Pe && press Enter",
        },
        {
            trigger: ".o_mercas_touch_lot:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_attribute_value:focus:contains(Extra)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_attribute_value:focus:contains(03)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_gross:focus",
            run: "edit 2 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_qty:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_price:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_qty_input:focus",
            run: "press Enter",
        },
        {
            content: "F8 goes to the last line; Delete removes it, once confirmed",
            trigger: ".o_mercas_touch_line:nth-child(2) .o_mercas_touch_line_attributes:contains(Extra · 03)",
        },
        {
            trigger: ".o_mercas_touch_product_search:focus",
            run: "press F8",
        },
        {
            trigger: ".o_mercas_touch_line:nth-child(2) .o_mercas_touch_line_info:focus",
            run: "press Delete",
        },
        {
            content: "Delete asks first: kept",
            trigger: ".modal .btn-secondary:contains(Keep it)",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "Up and down keep the place in the row",
            trigger: ".o_mercas_touch_line:nth-child(2) .o_mercas_touch_line_info",
            run() {
                document.querySelector(".o_mercas_touch_line:nth-child(2) .o_mercas_touch_remove_line").focus();
            },
        },
        {
            trigger: ".o_mercas_touch_line:nth-child(2) .o_mercas_touch_remove_line:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_line:nth-child(1) .o_mercas_touch_remove_line:focus",
            run: "press ArrowDown",
        },
        {
            content: "Enter on the trash removes the line, as a tap",
            trigger: ".o_mercas_touch_line:nth-child(2) .o_mercas_touch_remove_line:focus",
            run: "press Enter",
        },
        {
            content: "Removed, the trash of the line left has the focus",
            trigger: ".o_mercas_touch_lines:not(:has(.o_mercas_touch_line:nth-child(2))) .o_mercas_touch_remove_line:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: ".o_mercas_touch_line_price:focus",
            run: "press ArrowLeft",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "Ctrl+Enter sells",
            trigger: ".o_mercas_touch_line_info:focus",
            run: "press Control+Enter",
        },
        {
            content: "Done: the main button focused; Print opens with its first document focused",
            trigger: ".o_mercas_touch_done_actions .o_mercas_touch_new:focus",
        },
        {
            trigger: ".o_mercas_touch_print",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_print_panel input:checked:focus",
            run: "press Enter",
        },
        {
            content: "Enter unchecks it; Escape closes the printing, back to its button",
            trigger: ".o_mercas_touch_print_panel input:not(:checked):focus",
            run: "press Escape",
        },
        {
            trigger: ".o_mercas_touch_done:not(:has(.o_mercas_touch_print_panel)) .o_mercas_touch_print:focus",
            run: "press F9",
        },
        {
            content: "F9 opens the pallets; up from the first boxes, the quick spreading",
            trigger: ".o_mercas_touch_pallet_loose .o_mercas_touch_pallet_chip:focus",
            run: "press ArrowUp",
        },
        {
            trigger: ".o_mercas_touch_pallets_spread:focus",
            run: pressKey("+"),
        },
        {
            content: "+ adds a pallet; Enter spreads the boxes",
            trigger: ".o_mercas_touch_pallets_quick_count:contains(2)",
        },
        {
            trigger: ".o_mercas_touch_pallets_spread:focus",
            run: "press Enter",
        },
        {
            content: "Then the type and the height of each pallet with Enter",
            trigger: ".o_mercas_touch_pallet:not(.o_mercas_touch_pallet_loose) .o_mercas_touch_pallet_type:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_pallet_height:focus",
            run: "edit 1.5 && press Enter",
        },
        {
            trigger: ".o_mercas_touch_pallet_type:focus",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_pallet_height:focus",
            run: "press Enter",
        },
        {
            content: "Ctrl+Enter saves the pallets",
            trigger: ".o_mercas_touch_pallets_save:focus",
            run: "press Control+Enter",
        },
        {
            content: "Receive boxes: the boxes given back by the customer",
            trigger: ".o_mercas_touch_done_actions .o_mercas_touch_new:focus",
        },
        {
            trigger: ".o_mercas_touch_receive_boxes",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_partner_name:contains(Tour Customer)",
        },
        {
            trigger: ".o_mercas_touch_box_direction_return.btn-primary",
        },
        {
            content: "Only the boxes the customer holds, at first; All shows the others",
            trigger: ".o_mercas_touch_box_filter_stock.btn-primary",
        },
        {
            trigger: ".o_mercas_touch_grid:has(.o_mercas_touch_box:contains(Tour Box)):not(:has(.o_mercas_touch_box:contains(Tour Crate)))",
        },
        {
            trigger: ".o_mercas_touch_box_filter_all",
            run: "click",
        },
        {
            trigger: ".o_mercas_touch_grid .o_mercas_touch_box:contains(Tour Crate)",
        },
        {
            content: "Some boxes added: Ctrl+Enter goes to how to settle them, without choosing",
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "edit Tour Box && press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_entry:contains(Tour Box) .o_mercas_touch_box_entry_qty:focus",
            run: pressKey("+"),
        },
        {
            trigger: ".o_mercas_touch_box_entry_qty:focus:value(1)",
            run: "press Enter",
        },
        {
            trigger: ".o_mercas_touch_box_list_search:focus",
            run: "press Control+Enter",
        },
        {
            trigger: ".o_mercas_touch_box_settle .btn:focus:not(.btn-primary)",
        },
        {
            content: "The function keys show what they open",
            trigger: ".o_mercas_touch_tab_pallets:disabled .o_mercas_touch_tab_label:contains(Pallets)",
        },
    ],
});
