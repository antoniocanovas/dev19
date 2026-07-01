from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mercas_customer_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Almacén clientes",
        default=lambda self: self.env.ref(
            "stock.stock_location_customers", raise_if_not_found=False
        ),
        help=(
            "Ubicación padre sobre la que se creará automáticamente una ubicación "
            "por cliente al confirmar la venta, si no existe previamente."
        ),
    )
    purchase_lot_autocomplete = fields.Boolean(
        string="Purchase lot auto",
        default=True,
        help="Creación automática de lotes de compra al confirmar si no están establecidos.",
    )
    box_purchase_type_id = fields.Many2one(
        comodel_name="purchase.order.type",
        string="Tipo de compra envases",
        help="Tipo de compra para devolución de envases",
    )
    box_categ_ids = fields.Many2many(
        comodel_name="product.category",
        string="Categorías de cajas",
        help="Familias de productos permitidas para devolución de envases",
    )
    origin_country = fields.Boolean(
        string="Columna país origen",
        default=True,
        help="Muestra la columna de país de origen en las líneas de pedido de compra.",
    )
    origin_state = fields.Boolean(
        string="Columna provincia origen",
        default=True,
        help="Muestra la columna de provincia de origen en las líneas de pedido de compra.",
    )
    origin_filter = fields.Boolean(
        string="Filtro origen",
        default=False,
        help="Restringe la selección de país/provincia a los marcados como Origen Mercas.",
    )
    mercas_margin = fields.Float(
        string="Merca margin (%)",
        digits=(10, 2),
        help="General margin when not in partner.",
    )
    auto_confirm_supplier_invoice = fields.Boolean(
        string="Confirmar factura proveedor automáticamente",
        default=False,
    )
    compensation_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de compensación",
        domain=[("type", "=", "general")],
        help=(
            "Diario de operaciones diversas para compensar facturas de compra con "
            "facturas de venta del mismo partner. El asiento resultante aparece como "
            "crédito pendiente en las facturas de cliente."
        ),
    )
