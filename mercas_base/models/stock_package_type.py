from odoo import api, fields, models


class StockPackageType(models.Model):
    _inherit = "stock.package.type"

    mercas_is_pallet = fields.Boolean(
        string="Pallet",
        help="Package type of the pallets of a sale: the boxes of its lines "
             "are spread over pallets of these types, and the packing list "
             "shows each pallet as a package.",
    )
    mercas_box_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Box Product",
        domain=[("is_box", "=", True)],
        help="Returnable container of this package type. On a box type, its "
             "weight (tare) is the one of the boxes of this product. On a "
             "pallet type, each pallet of a sale adds one unit of this product "
             "to the sale, as the boxes do, so it counts in the box balance "
             "of the customer. Leave it empty for single-use pallets.",
    )

    @api.model
    def _mercas_box_types(self, box_products):
        """{box product: its (non-pallet) package type}, the first by sequence."""
        types = self.search(
            [("mercas_box_product_id", "in", box_products.ids), ("mercas_is_pallet", "=", False)],
            order="sequence, id",
        )
        result = {}
        for package_type in types:
            result.setdefault(package_type.mercas_box_product_id, package_type)
        return result
