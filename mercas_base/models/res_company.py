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
    mercas_supplier_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Almacén proveedores",
        default=lambda self: self.env.ref(
            "stock.stock_location_suppliers", raise_if_not_found=False
        ),
        help=(
            "Ubicación padre sobre la que se creará automáticamente una ubicación "
            "por proveedor al confirmar la compra, si no existe previamente."
        ),
    )
    purchase_lot_autocomplete = fields.Boolean(
        string="Purchase lot auto",
        default=True,
        help="Creación automática de lotes de compra al confirmar si no están establecidos.",
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
    liquidation_mode = fields.Selection(
        selection=[
            ("average_price", "Precio medio (una línea)"),
            ("average_price_scrap_split", "Precio medio + desecho aparte"),
        ],
        string="Modo de liquidación",
        default="average_price",
        required=True,
        help=(
            "Cómo se genera la línea de venta en la factura de liquidación por venta "
            "(no afecta a lotes en facturación firme):\n"
            "- Precio medio: una única línea con el importe bruto repartido entre "
            "kg vendidos + desechados (el desecho diluye el precio/kg mostrado).\n"
            "- Precio medio + desecho aparte: el importe bruto se reparte solo entre "
            "los kg vendidos, y se añade una línea adicional a precio 0 por los kg "
            "desechados, para que quede explícito en la factura que no se pagan."
        ),
    )
    liquidation_show_sale_breakdown = fields.Boolean(
        string="Detalle de ventas en factura",
        default=False,
        help=(
            "Añade, en la descripción de la línea de venta de la factura de "
            "liquidación por venta, un desglose acumulado (fecha, pedido, "
            "cantidad y precio unitario) de cada venta del lote hasta la "
            "fecha. Solo texto informativo: no afecta al importe ni a la "
            "cantidad facturada. No aplica a lotes en facturación firme."
        ),
    )
