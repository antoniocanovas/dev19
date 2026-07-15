from datetime import datetime, time, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class StockLotInvoiceWizard(models.TransientModel):
    _name = "stock.lot.invoice.wizard"
    _description = "Facturación de lotes completados"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor",
    )
    date_to = fields.Date(string="Fecha hasta")
    show_all = fields.Boolean(
        string="Mostrar todos",
        help="Muestra también los lotes con stock pendiente y no facturados, "
             "aunque no se pueden seleccionar para facturar.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        comodel_name="stock.lot.invoice.wizard.line",
        inverse_name="wizard_id",
        string="Lotes",
    )
    amount_total = fields.Monetary(
        string="Importe total",
        compute="_compute_amount_total",
        currency_field="currency_id",
        help="Importe de los lotes actualmente seleccionados en la lista.",
    )

    @api.depends("line_ids.selected", "line_ids.supplier_amount")
    def _compute_amount_total(self):
        for wizard in self:
            wizard.amount_total = sum(
                wizard.line_ids.filtered("selected").mapped("supplier_amount")
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" in fields_list:
            res["line_ids"] = self._prepare_lines(False, False, False)
        return res

    @api.onchange("partner_id", "date_to", "show_all")
    def _onchange_filters(self):
        self.line_ids = self._prepare_lines(self.partner_id, self.date_to, self.show_all)

    def _prepare_lines(self, partner, date_to, show_all):
        domain = [("supplier_invoice_id", "=", False)]
        if not show_all:
            domain.append(("completed", "=", True))
        if partner:
            domain.append(("partner_id", "=", partner.id))
        if date_to:
            upper_bound = datetime.combine(date_to + timedelta(days=1), time.min)
            domain.append(("create_date", "<", fields.Datetime.to_string(upper_bound)))
        lots = self.env["stock.lot"].search(domain)
        return [Command.clear()] + [
            Command.create({"lot_id": lot.id, "selected": lot.completed}) for lot in lots
        ]

    def action_invoice_all(self):
        return self._invoice_lots(self.line_ids.filtered("completed").lot_id)

    def action_invoice_selected(self):
        return self._invoice_lots(
            self.line_ids.filtered(lambda l: l.selected and l.completed).lot_id
        )

    def _invoice_lots(self, lots):
        self.ensure_one()
        if not lots:
            raise UserError(_("No hay lotes para facturar."))
        return lots.action_create_supplier_invoices()


class StockLotInvoiceWizardLine(models.TransientModel):
    _name = "stock.lot.invoice.wizard.line"
    _description = "Línea de facturación de lotes"

    wizard_id = fields.Many2one(
        comodel_name="stock.lot.invoice.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Seleccionado", default=True)
    lot_id = fields.Many2one(
        comodel_name="stock.lot", string="Lote", required=True, readonly=True
    )
    create_date = fields.Date(
        string="Fecha creación", compute="_compute_create_date", readonly=True
    )
    ref = fields.Char(related="lot_id.ref", readonly=True)
    company_id = fields.Many2one(
        related="lot_id.company_id", string="Compañía", readonly=True
    )
    partner_ids = fields.Many2many(
        related="lot_id.partner_ids", string="Transfer to", readonly=True
    )
    product_qty = fields.Float(
        related="lot_id.product_qty", string="Cantidad", readonly=True
    )
    completed = fields.Boolean(related="lot_id.completed", readonly=True)
    partner_id = fields.Many2one(
        related="lot_id.partner_id", string="Proveedor", readonly=True
    )
    product_id = fields.Many2one(
        related="lot_id.product_id", string="Producto", readonly=True
    )
    purchase_kg = fields.Float(
        related="lot_id.purchase_kg", string="Kg comprados", readonly=True
    )
    sale_kg = fields.Float(related="lot_id.sale_kg", string="Kg vendidos", readonly=True)
    scrap_kg = fields.Float(
        related="lot_id.scrap_kg", string="Kg desechados", readonly=True
    )
    sale_amount = fields.Float(
        related="lot_id.sale_amount", string="Importe vendido", readonly=True
    )
    mercas_margin = fields.Float(
        related="lot_id.mercas_margin", string="Margen (%)", readonly=False
    )
    supplier_price_kg = fields.Float(
        related="lot_id.supplier_price_kg", string="Precio/kg", readonly=True
    )
    supplier_amount = fields.Float(
        related="lot_id.supplier_amount", string="Importe", readonly=True
    )
    supplier_invoice_id = fields.Many2one(
        related="lot_id.supplier_invoice_id", string="Factura proveedor", readonly=True
    )

    @api.depends("lot_id.create_date")
    def _compute_create_date(self):
        for line in self:
            line.create_date = line.lot_id.create_date
