# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    spreadsheet_id = fields.Many2one(
        "spreadsheet.spreadsheet",
        string="Quotation Calculator",
        copy=False,
    )
    has_spreadsheet = fields.Boolean(
        compute="_compute_has_spreadsheet",
    )

    @api.depends("spreadsheet_id")
    def _compute_has_spreadsheet(self):
        for order in self:
            order.has_spreadsheet = bool(order.spreadsheet_id)

    @api.onchange("sale_order_template_id")
    def _onchange_sale_order_template_id_spreadsheet(self):
        if self.sale_order_template_id and self.sale_order_template_id.spreadsheet_id:
            spreadsheet = self._copy_template_spreadsheet(
                self.sale_order_template_id.spreadsheet_id,
            )
            self.spreadsheet_id = spreadsheet
        elif not self.sale_order_template_id:
            self.spreadsheet_id = False

    def _copy_template_spreadsheet(self, template_spreadsheet):
        """Create a copy of the template spreadsheet for this sale order."""
        return template_spreadsheet.copy(
            {"name": self.env._("Calculator - %s", self.name or self.env._("New"))}
        )

    def _update_spreadsheet_filter(self):
        """Update the global filter default value in the spreadsheet JSON
        so the list is filtered to this sale order's id."""
        self.ensure_one()
        if not self.spreadsheet_id:
            return
        data = self.spreadsheet_id.spreadsheet_raw
        if not data:
            return

        for gf in data.get("globalFilters", []):
            if gf.get("type") == "relation" and gf.get("modelName") == "sale.order":
                gf["defaultValue"] = {"operator": "in", "ids": [self.id]}
                break

        self.spreadsheet_id.spreadsheet_raw = data

    def write(self, vals):
        res = super().write(vals)
        if "spreadsheet_id" in vals:
            for order in self.filtered("spreadsheet_id"):
                order._update_spreadsheet_filter()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders.filtered("spreadsheet_id"):
            order._update_spreadsheet_filter()
        return orders

    def action_open_spreadsheet_calculator(self):
        self.ensure_one()
        if self.spreadsheet_id:
            return self.spreadsheet_id.open_spreadsheet()
        return False

    def _check_spreadsheet_sync_allowed(self):
        self.ensure_one()
        if self.state == "cancel":
            raise UserError(self.env._("Cannot sync a cancelled quotation."))
        if self.state == "sale":
            raise UserError(self.env._("Cannot sync a confirmed sales order."))

    def action_sync_spreadsheet_order_lines(self, commands):
        """Sync sale order lines from the quotation calculator spreadsheet."""
        self.ensure_one()
        self._check_spreadsheet_sync_allowed()
        self.write({"order_line": commands})
        return True
