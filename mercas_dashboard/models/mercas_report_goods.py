from odoo import api, fields, models
from odoo.tools import SQL


class MercasReportGoods(models.Model):
    """ The goods sold, bought and scrapped, line by line: the data of the dashboards of Mercas
    (Dashboards > Mercas). Amounts untaxed and net kg, without the boxes, as the management
    summary (mercas.management.dashboard): confirmed sales and purchases at the date of their
    order, scraps at the date they were done. """
    _name = "mercas.report.goods"
    _description = "Mercas: Goods Sold, Bought and Scrapped"
    _auto = False
    _rec_name = "date"
    _order = "date desc"

    kind = fields.Selection(
        selection=[("sale", "Sale"), ("purchase", "Purchase"), ("scrap", "Scrap")],
        readonly=True,
    )
    date = fields.Datetime(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one(
        "res.partner", string="Partner", readonly=True,
        help="The customer of a sale, the supplier of a purchase or of the lot scrapped.",
    )
    product_id = fields.Many2one("product.product", readonly=True)
    categ_id = fields.Many2one("product.category", string="Product Category", readonly=True)
    lot_id = fields.Many2one("stock.lot", string="Lot", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson / Buyer", readonly=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="Sales", readonly=True, aggregator="count_distinct",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Purchases", readonly=True, aggregator="count_distinct",
    )
    amount = fields.Float(string="Amount", readonly=True)
    kg = fields.Float(string="Net Kg", readonly=True)
    boxes = fields.Float(string="Boxes", readonly=True)

    @api.model
    def _mercas_weight_uom(self):
        return self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()

    @api.model
    def _mercas_kg_sql(self, qty, uom, product_uom, template):
        """ Net kg of `qty` in the unit `uom`, as product.product._mercas_net_weight: converted
        when `uom` is a unit of weight (it shares the reference unit of the weight unit), with the
        weight of the product otherwise. """
        weight_uom = self._mercas_weight_uom()
        return SQL(
            """CASE WHEN split_part(%(uom)s.parent_path, '/', 1) = %(weight_root)s
                    THEN %(qty)s * %(uom)s.factor / %(weight_factor)s
                    ELSE %(qty)s * %(uom)s.factor / NULLIF(%(product_uom)s.factor, 0)
                         * COALESCE(%(template)s.weight, 0)
               END""",
            qty=qty, uom=uom, product_uom=product_uom, template=template,
            weight_root=weight_uom.parent_path.split("/")[0],
            weight_factor=weight_uom.factor,
        )

    @property
    def _table_query(self):
        kg = self._mercas_kg_sql
        return SQL(
            """
            SELECT sol.id * 3 AS id, 'sale' AS kind, so.date_order AS date, so.company_id,
                   partner.commercial_partner_id AS partner_id, sol.product_id, pt.categ_id,
                   sol.lot_id, so.user_id, so.id AS sale_order_id, NULL::integer AS purchase_order_id,
                   sol.price_subtotal AS amount, %(sale_kg)s AS kg, sol.box_qty AS boxes
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
              JOIN res_partner partner ON partner.id = so.partner_id
              JOIN product_product pp ON pp.id = sol.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              JOIN uom_uom u ON u.id = sol.product_uom_id
              JOIN uom_uom pu ON pu.id = pt.uom_id
             WHERE so.state = 'sale' AND sol.display_type IS NULL AND NOT COALESCE(pt.is_box, FALSE)
            UNION ALL
            SELECT pol.id * 3 + 1, 'purchase', po.date_order, po.company_id,
                   partner.commercial_partner_id, pol.product_id, pt.categ_id,
                   pol.lot_id, po.user_id, NULL, po.id,
                   pol.price_subtotal, %(purchase_kg)s, pol.box_qty
              FROM purchase_order_line pol
              JOIN purchase_order po ON po.id = pol.order_id
              JOIN res_partner partner ON partner.id = po.partner_id
              JOIN product_product pp ON pp.id = pol.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              JOIN uom_uom u ON u.id = pol.product_uom_id
              JOIN uom_uom pu ON pu.id = pt.uom_id
             WHERE po.state IN ('purchase', 'done') AND pol.display_type IS NULL
                   AND NOT COALESCE(pt.is_box, FALSE)
            UNION ALL
            SELECT scrap.id * 3 + 2, 'scrap', scrap.date_done, scrap.company_id,
                   lot_partner.commercial_partner_id, scrap.product_id, pt.categ_id,
                   scrap.lot_id, NULL, NULL, NULL,
                   0, %(scrap_kg)s, 0
              FROM stock_scrap scrap
              JOIN product_product pp ON pp.id = scrap.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              JOIN uom_uom u ON u.id = scrap.product_uom_id
              JOIN uom_uom pu ON pu.id = pt.uom_id
              LEFT JOIN stock_lot lot ON lot.id = scrap.lot_id
              LEFT JOIN res_partner lot_partner ON lot_partner.id = lot.partner_id
             WHERE scrap.state = 'done'
            """,
            sale_kg=kg(SQL("sol.product_uom_qty"), SQL("u"), SQL("pu"), SQL("pt")),
            purchase_kg=kg(SQL("pol.product_qty"), SQL("u"), SQL("pu"), SQL("pt")),
            scrap_kg=kg(SQL("scrap.scrap_qty"), SQL("u"), SQL("pu"), SQL("pt")),
        )
