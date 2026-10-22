from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    mercas_quality = fields.Char(string="Quality", readonly=True)
    mercas_size = fields.Char(string="Size", readonly=True)

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res["mercas_quality"] = self._mercas_role_value_sql("quality")
        res["mercas_size"] = self._mercas_role_value_sql("size")
        return res

    def _mercas_role_value_sql(self, role):
        """Values of the attributes with the Merca `role` of each line: of its
        variant, or chosen on the line (attributes that never create variants).
        By name, so that the same value of both kinds of attribute is added up
        together. Inside MAX() because the report groups the lines."""
        lang = self.env.cr.mogrify("%s", [self.env.lang or "en_US"]).decode()
        role = self.env.cr.mogrify("%s", [role]).decode()
        return f"""MAX((
                SELECT string_agg(
                    COALESCE(pav.name->>{lang}, pav.name->>'en_US'), ', '
                    ORDER BY pa.sequence, pav.sequence
                )
                FROM product_template_attribute_value ptav
                JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
                JOIN product_attribute pa ON pa.id = ptav.attribute_id
                WHERE pa.mercas_role = {role}
                  AND (
                    ptav.id IN (
                        SELECT pvc.product_template_attribute_value_id
                        FROM product_variant_combination pvc
                        WHERE pvc.product_product_id = l.product_id
                    )
                    OR ptav.id IN (
                        SELECT rel.product_template_attribute_value_id
                        FROM product_template_attribute_value_sale_order_line_rel rel
                        WHERE rel.sale_order_line_id = l.id
                    )
                  )
            ))"""
