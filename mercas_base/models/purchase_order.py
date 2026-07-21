from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    mercas_origin_country = fields.Boolean(related="company_id.origin_country")
    mercas_origin_state = fields.Boolean(related="company_id.origin_state")

    @api.model
    def action_mercas_box_returns_menu(self):
        box_type = self.env.company.box_purchase_type_id
        if not box_type:
            raise UserError(_("Configure el tipo de compra de envases en la empresa."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Cajas"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("order_type", "=", box_type.id)],
            "context": {"default_order_type": box_type.id},
        }

    def action_open_box_delivery(self):
        """Open a new sale order to deliver boxes back to this purchase's supplier."""
        self.ensure_one()
        box_type = self.company_id.box_sale_type_id
        if not box_type:
            raise UserError(_("Configure el tipo de venta de envases en la empresa."))
        new_so = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "box_delivery_purchase_id": self.id,
            "type_id": box_type.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": new_so.id,
            "view_mode": "form",
            "target": "current",
        }

    mercas_is_box_return = fields.Boolean(
        compute="_compute_mercas_box_fields",
        string="Es devolución de envases",
    )
    mercas_box_categ_ids = fields.Many2many(
        comodel_name="product.category",
        compute="_compute_mercas_box_fields",
        string="Categorías de cajas permitidas",
    )

    @api.depends("order_type", "company_id", "company_id.box_purchase_type_id",
                 "company_id.box_categ_ids")
    def _compute_mercas_box_fields(self):
        for order in self:
            box_type = order.company_id.box_purchase_type_id
            if box_type and order.order_type == box_type:
                order.mercas_is_box_return = True
                order.mercas_box_categ_ids = order.company_id.box_categ_ids
            else:
                order.mercas_is_box_return = False
                order.mercas_box_categ_ids = self.env["product.category"]

    def button_confirm(self):
        # Pre-confirm: auto-create lots for tracked lines without one
        for order in self:
            if order.company_id.purchase_lot_autocomplete:
                order._mercas_autocreate_lots()

        # Regular purchases (not box-return): ensure supplier location and
        # auto-create box lines before confirming, same treatment as sales,
        # so the box product is included in the receipt generated on confirm.
        regular_orders = self.filtered(lambda o: not o.mercas_is_box_return)
        for order in regular_orders:
            order.partner_id.mercas_ensure_supplier_location(order.company_id)
            order._mercas_prepare_box_lines()

        result = super().button_confirm()

        # Sync partner to all lots on confirmed lines that still lack it
        for order in self:
            for line in order.order_line.filtered(
                lambda l: l.lot_id and not l.lot_id.partner_id
            ):
                line.lot_id.partner_id = order.partner_id

        # Post-confirm: full automated flow for box return orders
        box_orders = self.filtered(lambda o: o.mercas_is_box_return)
        if not box_orders:
            return result

        actions = [order._mercas_box_confirm_flow() for order in box_orders]
        invoice_actions = [a for a in actions if isinstance(a, dict)]
        return invoice_actions[-1] if invoice_actions else result

    def _mercas_prepare_box_lines(self):
        """Add PRODUCTOS/Envases sections and one box line per product line with
        box_qty > 0, using the box product's purchase price (same logic as sales)."""
        PurchaseLine = self.env["purchase.order.line"]

        product_lines = self.order_line.filtered(
            lambda l: not l.display_type and not l.box_purchase_line_id
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
            PurchaseLine.create({
                "order_id": self.id,
                "display_type": "line_section",
                "name": "PRODUCTOS",
                "sequence": min_seq - 1,
                "product_qty": 0,
            })

        # --- Envases section after all non-box lines ---
        has_envases = self.order_line.filtered(
            lambda l: l.display_type == "line_section" and l.name == "Envases"
        )
        non_box_lines = self.order_line.filtered(lambda l: not l.box_purchase_line_id)
        max_seq = max(non_box_lines.mapped("sequence")) if non_box_lines else 10

        if not has_envases:
            envases_seq = max_seq + 10
            PurchaseLine.create({
                "order_id": self.id,
                "display_type": "line_section",
                "name": "Envases",
                "sequence": envases_seq,
                "product_qty": 0,
            })
        else:
            envases_seq = has_envases[0].sequence

        # --- Create / update box lines ---
        existing_by_parent = {
            bl.box_purchase_line_id.id: bl
            for bl in self.order_line.filtered(lambda l: l.box_purchase_line_id)
        }
        for i, line in enumerate(box_lines_needed):
            if line.id in existing_by_parent:
                existing_by_parent[line.id].write({
                    "product_id": line.box_product_id.id,
                    "product_qty": line.box_qty,
                })
            else:
                PurchaseLine.create({
                    "order_id": self.id,
                    "product_id": line.box_product_id.id,
                    "product_qty": line.box_qty,
                    "box_purchase_line_id": line.id,
                    "sequence": envases_seq + (i + 1) * 10,
                })

    def _mercas_autocreate_lots(self):
        """Auto-assign new lots to tracked lines that have no lot set."""
        Lot = self.env["stock.lot"]
        for line in self.order_line:
            if line.product_id.tracking in ("lot", "serial") and not line.lot_id:
                line.lot_id = Lot.create({
                    "product_id": line.product_id.id,
                    "company_id": self.company_id.id,
                    "partner_id": self.partner_id.id,
                    "origin_country_id": line.origin_country_id.id,
                    "origin_state_id": line.origin_state_id.id,
                })

    def _mercas_box_confirm_flow(self):
        """Receive boxes from customer location, create vendor bill and post it."""
        self.ensure_one()

        # Ensure the partner has a sub-location under the mercas parent (same logic as sales)
        self.partner_id.mercas_ensure_customer_location(self.company_id)

        partner = self.partner_id.commercial_partner_id
        customer_loc = partner.with_company(self.company_id).property_stock_customer

        pending = self.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        for picking in pending:
            active_moves = picking.move_ids.filtered(
                lambda m: m.state not in ("done", "cancel")
            )
            # Set done qty to trigger move_line creation
            for move in active_moves:
                move.quantity = move.product_uom_qty
            # Redirect source from virtual supplier to the customer's physical location
            if customer_loc:
                picking.move_line_ids.write({"location_id": customer_loc.id})
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
            ).button_validate()

        # Create and immediately post the vendor bill (deposit refund)
        self.action_create_invoice()
        invoice = self.invoice_ids.filtered(lambda i: i.state == "draft")[:1]
        if not invoice:
            return True
        invoice.invoice_date = fields.Date.context_today(self)
        invoice.action_post()

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def button_purchase_and_receive(self):
        """Confirm the PO and validate receipts.
        Invoice is only created automatically for box return orders (handled inside
        button_confirm → _mercas_box_confirm_flow). For regular orders the invoice
        is created manually by the user."""
        self.button_confirm()
        if not self.mercas_is_box_return:
            self._mercas_auto_receive()

    def _mercas_auto_receive(self):
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


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    box_qty = fields.Integer(string="Cajas", default=0)
    box_purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Línea de producto",
        ondelete="cascade",
        copy=False,
        index=True,
    )
    box_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Caja",
        compute="_compute_box_product_id",
        store=True,
        readonly=False,
    )
    origin_country_id = fields.Many2one(
        comodel_name="res.country",
        string="País origen",
    )
    origin_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Provincia origen",
        domain="[('country_id', '=', origin_country_id)]",
    )

    @api.depends("product_id")
    def _compute_box_product_id(self):
        for line in self:
            if line.display_type or line.box_purchase_line_id:
                line.box_product_id = False
            else:
                line.box_product_id = line.product_id.product_tmpl_id.box_product_id

    def _prepare_account_move_line(self, move=False):
        vals = super()._prepare_account_move_line(move)
        if self.lot_id:
            vals["lot_id"] = self.lot_id.id
        return vals

    def write(self, vals):
        result = super().write(vals)
        if "lot_id" in vals and vals.get("lot_id"):
            for line in self.filtered(lambda l: l.lot_id and not l.lot_id.partner_id):
                line.lot_id.partner_id = line.order_id.partner_id
            for line in self.filtered(
                lambda l: l.lot_id and (l.origin_country_id or l.origin_state_id)
            ):
                update = {}
                if line.origin_country_id:
                    update["origin_country_id"] = line.origin_country_id.id
                if line.origin_state_id:
                    update["origin_state_id"] = line.origin_state_id.id
                line.lot_id.write(update)
        if "origin_country_id" in vals or "origin_state_id" in vals:
            for line in self.filtered(lambda l: l.lot_id):
                update = {}
                if "origin_country_id" in vals:
                    update["origin_country_id"] = line.origin_country_id.id or False
                if "origin_state_id" in vals:
                    update["origin_state_id"] = line.origin_state_id.id or False
                line.lot_id.write(update)
        if "box_qty" in vals or "box_product_id" in vals or "product_id" in vals:
            for line in self.filtered(lambda l: not l.display_type and not l.box_purchase_line_id):
                box_lines = self.env["purchase.order.line"].search(
                    [("box_purchase_line_id", "=", line.id)]
                )
                if not box_lines:
                    continue
                if "box_qty" in vals and line.box_qty == 0:
                    box_lines.unlink()
                    continue
                update = {}
                if "box_qty" in vals:
                    update["product_qty"] = line.box_qty
                if ("box_product_id" in vals or "product_id" in vals) and line.box_product_id:
                    update["product_id"] = line.box_product_id.id
                if update:
                    box_lines.write(update)
        return result

    @api.constrains("product_id", "order_id")
    def _check_mercas_box_product_category(self):
        for line in self:
            if not line.product_id:
                continue
            order = line.order_id
            if not order.mercas_is_box_return:
                continue
            allowed = order.company_id.box_categ_ids
            if allowed and line.product_id.categ_id not in allowed:
                raise ValidationError(
                    _("En pedidos de devolución de envases solo se permiten productos "
                      "de las categorías: %s")
                    % ", ".join(allowed.mapped("name"))
                )
