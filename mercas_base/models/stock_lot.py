from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor",
        index=True,
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
    purchase_line_ids = fields.One2many(
        comodel_name="purchase.order.line",
        inverse_name="lot_id",
        string="Líneas de compra",
    )
    sale_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="lot_id",
        string="Líneas de venta",
    )
    supplier_invoice_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="lot_id",
        string="Líneas factura proveedor",
        domain=[("move_id.move_type", "in", ["in_invoice", "in_refund"])],
    )
    customer_invoice_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="lot_id",
        string="Líneas factura cliente",
        domain=[("move_id.move_type", "in", ["out_invoice", "out_refund"])],
    )
    scrap_line_ids = fields.One2many(
        comodel_name="stock.scrap",
        inverse_name="lot_id",
        string="Desechos",
    )
    stock_move_line_ids = fields.One2many(
        comodel_name="stock.move.line",
        inverse_name="lot_id",
        string="Movimientos de stock",
    )

    # ── Liquidación ────────────────────────────────────────────────────────────

    purchase_kg = fields.Float(
        string="Kg comprados",
        compute="_compute_purchase_kg",
        digits=(16, 3),
    )
    sale_kg = fields.Float(
        string="Kg vendidos",
        compute="_compute_sale_fields",
        digits=(16, 3),
    )
    sale_amount = fields.Float(
        string="Importe vendido",
        compute="_compute_sale_fields",
        digits=(16, 2),
    )
    scrap_kg = fields.Float(
        string="Kg desechados",
        compute="_compute_scrap_kg",
        digits=(16, 3),
    )
    completed = fields.Boolean(
        string="Completado",
        compute="_compute_completed",
        store=True,
    )
    supplier_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura proveedor",
        readonly=True,
        copy=False,
    )

    mercas_margin = fields.Float(
        string="Margen (%)",
        digits=(10, 2),
    )
    can_edit_margin = fields.Boolean(
        compute="_compute_can_edit_margin",
    )
    supplier_amount = fields.Float(
        string="Importe proveedor",
        compute="_compute_supplier_fields",
        digits=(16, 2),
    )
    supplier_price_kg = fields.Float(
        string="Precio/kg proveedor",
        compute="_compute_supplier_fields",
        digits=(16, 4),
    )
    margin = fields.Float(
        string="Margen importe",
        compute="_compute_supplier_fields",
        digits=(16, 2),
    )

    @api.depends("product_qty")
    def _compute_completed(self):
        for lot in self:
            lot.completed = lot.product_qty <= 0

    @api.depends("purchase_line_ids.product_qty", "purchase_line_ids.order_id.state")
    def _compute_purchase_kg(self):
        for lot in self:
            lines = lot.purchase_line_ids.filtered(
                lambda l: l.order_id.state in ("purchase", "done")
            )
            lot.purchase_kg = sum(lines.mapped("product_qty"))

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.move_id.sale_line_id",
        "stock_move_line_ids.move_id.sale_line_id.price_unit",
        "stock_move_line_ids.move_id.sale_line_id.discount",
    )
    def _compute_sale_fields(self):
        for lot in self:
            sale_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done" and ml.move_id.sale_line_id
            )
            lot.sale_kg = sum(sale_mls.mapped("quantity"))
            amount = 0.0
            for ml in sale_mls:
                sl = ml.move_id.sale_line_id
                amount += ml.quantity * sl.price_unit * (1.0 - sl.discount / 100.0)
            lot.sale_amount = amount

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.location_id.usage",
        "stock_move_line_ids.location_dest_id.usage",
    )
    def _compute_scrap_kg(self):
        for lot in self:
            loss_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done"
                and ml.location_id.usage == "internal"
                and ml.location_dest_id.usage in ("production", "inventory")
            )
            gain_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done"
                and ml.location_id.usage == "inventory"
                and ml.location_dest_id.usage == "internal"
            )
            lot.scrap_kg = (
                sum(loss_mls.mapped("quantity")) - sum(gain_mls.mapped("quantity"))
            )

    @api.depends_context("uid")
    def _compute_can_edit_margin(self):
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")
        for lot in self:
            lot.can_edit_margin = is_manager

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.move_id.sale_line_id",
        "stock_move_line_ids.move_id.sale_line_id.price_unit",
        "stock_move_line_ids.move_id.sale_line_id.discount",
        "purchase_line_ids.product_qty",
        "purchase_line_ids.order_id.state",
        "mercas_margin",
    )
    def _compute_supplier_fields(self):
        for lot in self:
            supplier_amount = lot.sale_amount * (1.0 - lot.mercas_margin / 100.0)
            lot.supplier_amount = supplier_amount
            lot.supplier_price_kg = (
                supplier_amount / lot.purchase_kg if lot.purchase_kg else 0.0
            )
            lot.margin = lot.sale_amount - supplier_amount

    def action_view_supplier_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.supplier_invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_supplier_invoices(self):
        lots = self.filtered(
            lambda l: l.completed and not l.supplier_invoice_id and l.partner_id
        )
        if not lots:
            raise UserError(
                _("No hay lotes completados sin facturar con proveedor asignado.")
            )

        by_partner = {}
        for lot in lots:
            by_partner.setdefault(lot.partner_id.id, self.env["stock.lot"])
            by_partner[lot.partner_id.id] |= lot

        invoices = self.env["account.move"]
        for partner_id, partner_lots in by_partner.items():
            lines = []
            lot_extra = {}
            for lot in partner_lots:
                if not lot.purchase_kg:
                    continue
                purchase_line = lot.purchase_line_ids.filtered(
                    lambda l: l.order_id.state in ("purchase", "done")
                )[:1]
                extra_parts = []
                if purchase_line and purchase_line.order_id.date_order:
                    extra_parts.append(
                        purchase_line.order_id.date_order.strftime("%d/%m/%Y")
                    )
                if purchase_line and purchase_line.order_id.name:
                    extra_parts.append(purchase_line.order_id.name)
                if purchase_line and purchase_line.order_id.partner_ref:
                    extra_parts.append(purchase_line.order_id.partner_ref)
                extra_parts.append(lot.name)
                lot_extra[lot.id] = " | ".join(extra_parts)
                lines.append(Command.create({
                    "product_id": lot.product_id.id,
                    "quantity": lot.purchase_kg,
                    "price_unit": lot.supplier_price_kg,
                    "lot_id": lot.id,
                }))
            if not lines:
                continue

            invoice = self.env["account.move"].create({
                "move_type": "in_invoice",
                "partner_id": partner_id,
                "invoice_date": fields.Date.context_today(self),
                "invoice_line_ids": lines,
            })

            for line in invoice.invoice_line_ids.filtered("lot_id"):
                extra = lot_extra.get(line.lot_id.id)
                if extra:
                    line.name = (line.name or "") + "\n" + extra

            for lot in partner_lots:
                if lot.purchase_kg:
                    lot.supplier_invoice_id = invoice.id
                    lot._sync_sale_lines_cost()

            if self.env.company.auto_confirm_supplier_invoice:
                invoice.action_post()

            invoices |= invoice

        if not invoices:
            return

        if len(invoices) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": invoices.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "domain": [("id", "in", invoices.ids)],
            "view_mode": "list,form",
            "target": "current",
        }

    def _sync_sale_lines_cost(self):
        """Actualiza purchase_price en las líneas de venta si sale_margin está instalado."""
        if "purchase_price" not in self.env["sale.order.line"]._fields:
            return
        for lot in self:
            sale_lines = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done" and ml.move_id.sale_line_id
            ).mapped("move_id.sale_line_id")
            if sale_lines:
                sale_lines.write({"purchase_price": lot.supplier_price_kg})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "mercas_margin" not in vals:
                partner_id = vals.get("partner_id")
                company_id = vals.get("company_id", self.env.company.id)
                partner = (
                    self.env["res.partner"].browse(partner_id)
                    if partner_id
                    else self.env["res.partner"]
                )
                company = self.env["res.company"].browse(company_id)
                vals["mercas_margin"] = (
                    partner.mercas_margin
                    if partner and partner.mercas_margin
                    else company.mercas_margin
                )
        return super().create(vals_list)
