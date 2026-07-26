from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lote",
        index=True,
        ondelete="set null",
    )
    mercas_is_firm_line = fields.Boolean(
        string="Línea de suministro firme",
        copy=False,
        help=(
            "Marca las líneas de factura de proveedor que representan kg "
            "recibidos facturados en régimen de negociación en firme, para "
            "poder llevar la cuenta de kilos pendientes sin mezclarlas con "
            "anticipos o liquidaciones por venta."
        ),
    )
