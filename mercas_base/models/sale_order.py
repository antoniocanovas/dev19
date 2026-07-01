from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for order in self:
            order._mercas_ensure_customer_location()
            order._mercas_prepare_box_lines()
        return super().action_confirm()

    def _mercas_ensure_customer_location(self):
        self.partner_id.mercas_ensure_customer_location(self.company_id)

    def _mercas_prepare_box_lines(self):
        """Add PRODUCTOS/Envases sections and one box line per product line with box_qty > 0."""
        SaleLine = self.env["sale.order.line"]

        product_lines = self.order_line.filtered(
            lambda l: not l.display_type and not l.box_sale_line_id
        )
        box_lines_needed = product_lines.filtered(
            lambda l: l.box_qty > 0 and l.box_product_id
        )
        if not box_lines_needed:
            return

        # --- PRODUCTOS section before first product line ---
        has_productos = self.order_line.filtered(
            lambda l: l.display_type == "line_section" and l.name == "PRODUCTOS"
        )
        if not has_productos and product_lines:
            min_seq = min(product_lines.mapped("sequence"))
            SaleLine.create({
                "order_id": self.id,
                "display_type": "line_section",
                "name": "PRODUCTOS",
                "sequence": min_seq - 1,
            })

        # --- Envases section after all non-box lines ---
        has_envases = self.order_line.filtered(
            lambda l: l.display_type == "line_section" and l.name == "Envases"
        )
        non_box_lines = self.order_line.filtered(lambda l: not l.box_sale_line_id)
        max_seq = max(non_box_lines.mapped("sequence")) if non_box_lines else 10

        if not has_envases:
            envases_seq = max_seq + 10
            SaleLine.create({
                "order_id": self.id,
                "display_type": "line_section",
                "name": "Envases",
                "sequence": envases_seq,
            })
        else:
            envases_seq = has_envases[0].sequence

        # --- Create / update box lines ---
        existing_by_parent = {
            bl.box_sale_line_id.id: bl
            for bl in self.order_line.filtered(lambda l: l.box_sale_line_id)
        }
        for i, line in enumerate(box_lines_needed):
            if line.id in existing_by_parent:
                existing_by_parent[line.id].write({
                    "product_id": line.box_product_id.id,
                    "product_uom_qty": line.box_qty,
                })
            else:
                SaleLine.create({
                    "order_id": self.id,
                    "product_id": line.box_product_id.id,
                    "product_uom_qty": line.box_qty,
                    "box_sale_line_id": line.id,
                    "sequence": envases_seq + (i + 1) * 10,
                })

    def button_sold_and_sent(self):
        """Confirm the sale and immediately validate the delivery if all lots are assigned."""
        self.ensure_one()

        # 1. Lot check
        tracked_without_lot = self.order_line.filtered(
            lambda l: not l.display_type
            and not l.box_sale_line_id
            and l.product_id.tracking in ("lot", "serial")
            and not l.lot_id
        )
        if tracked_without_lot:
            names = ", ".join(tracked_without_lot.mapped("product_id.name"))
            raise UserError(
                _("Asigna lote a los siguientes productos antes de enviar: %s") % names
            )

        # 2. Financial risk check (sale_financial_risk / account_financial_risk)
        if hasattr(self, "evaluate_risk_message"):
            allow_overrisk = getattr(
                self.company_id, "allow_overrisk_sale_confirmation", True
            )
            if not allow_overrisk:
                partner = self.partner_invoice_id.commercial_partner_id
                exception_msg = self.evaluate_risk_message(partner)
                if exception_msg:
                    return (
                        self.env["partner.risk.exceeded.wiz"]
                        .create({
                            "exception_msg": exception_msg,
                            "partner_id": partner.id,
                            "origin_reference": f"{self._name},{self.id}",
                            "continue_method": "_mercas_sold_and_sent_execute",
                        })
                        .action_show()
                    )

        return self._mercas_sold_and_sent_execute()

    def _mercas_sold_and_sent_execute(self):
        """Confirm and auto-deliver. Called directly or via the risk wizard continue."""
        self.with_context(bypass_risk=True).action_confirm()
        self._mercas_auto_deliver()

    def action_open_box_return(self):
        """Open a new purchase order pre-filled for box return from this sale's customer."""
        self.ensure_one()
        company = self.company_id
        box_type = company.box_purchase_type_id
        if not box_type:
            raise UserError(_("Configure el tipo de compra de envases en la empresa."))
        new_po = self.env["purchase.order"].create({
            "partner_id": self.partner_id.id,
            "order_type": box_type.id,
            "origin": self.name,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": new_po.id,
            "view_mode": "form",
            "target": "current",
        }

    def _mercas_auto_deliver(self):
        pending = self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        for picking in pending:
            for move in picking.move_ids.filtered(
                lambda m: m.state not in ("done", "cancel")
            ):
                move.quantity = move.product_uom_qty
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
            ).button_validate()
