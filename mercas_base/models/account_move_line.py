from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lote",
        index=True,
        ondelete="set null",
    )
