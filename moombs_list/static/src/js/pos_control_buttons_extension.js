/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class PosSaleSelectCreateDialog extends SelectCreateDialog {
    static props = {
        ...SelectCreateDialog.props,
        viewId: { type: Number, optional: true },
    };

    get viewProps() {
        const props = super.viewProps;
        if (this.props.viewId) {
            props.viewId = this.props.viewId;
        }
        return props;
    }
}

patch(ControlButtons.prototype, {
    async onClickQuotation() {
        const context = {};
        if (this.partner) {
            context["search_default_partner_id"] = this.partner.id;
        }

        let domain = [
            ["state", "!=", "cancel"],
            ["invoice_status", "!=", "invoiced"],
            ["currency_id", "=", this.pos.currency.id],
            ["amount_unpaid", ">", 0],
        ];
        if (this.pos.getOrder()?.getPartner()) {
            domain = [
                ...domain,
                ["partner_id", "any", [["id", "child_of", [this.pos.getOrder().getPartner().id]]]],
            ];
        }

        const [, viewId] = await this.env.services.orm.call(
            "ir.model.data",
            "check_object_reference",
            ["moombs_list", "view_quotation_tree_moombs"]
        );
        this.dialog.add(PosSaleSelectCreateDialog, {
            resModel: "sale.order",
            viewId,
            noCreate: true,
            multiSelect: false,
            domain,
            context,
            onSelected: async (resIds) => {
                await this.pos.onClickSaleOrder(resIds[0]);
            },
        });
    },
});
