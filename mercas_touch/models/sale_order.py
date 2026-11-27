from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mercas_touch_uuid = fields.Char(
        'Touch Screen Identifier', copy=False, readonly=True,
        help="Identifier given by the touch screen that made this document, so that sending it twice doesn't duplicate it.")

    mercas_touch_boxes = fields.Boolean(
        'Touch Screen Box Movement', copy=False, readonly=True,
        help="Boxes given back by a customer or to a supplier from the touch screen: it is "
             "resumed in Boxes, not among the sales or the purchases.")

    _mercas_touch_uuid_unique = models.Constraint(
        'UNIQUE (mercas_touch_uuid)',
        "This document was already received from the touch screen.",
    )
