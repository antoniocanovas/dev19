from odoo import fields, models
from odoo.tools import SQL

# Days overdue of each age of the debt, as the management summary (DEBT_AGES); the keys sort
# the ages from the most recent
AGES = [
    ("0_not_due", "Not due"),
    ("1_30", "1-30 days"),
    ("2_60", "31-60 days"),
    ("3_90", "61-90 days"),
    ("4_over_90", "Over 90 days"),
]


class MercasReportBalance(models.Model):
    """ What is owed today, entry by entry: the open debt of the customers, by days overdue, the
    open debt to the suppliers and the sales still to invoice (Dashboards > Mercas > Debt and
    Payments). The residual of the receivable and payable entries posted and not reconciled, and
    the untaxed amount to invoice of the lines of the confirmed sales, as the management summary
    on the day. """
    _name = "mercas.report.balance"
    _description = "Mercas: Open Debt of Customers and to Suppliers"
    _auto = False
    _rec_name = "partner_id"
    _order = "date_maturity"

    kind = fields.Selection(
        selection=[
            ("customer", "Customers owe us"),
            ("supplier", "We owe suppliers"),
            ("to_invoice", "To invoice to customers"),
        ],
        readonly=True,
    )
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)
    move_id = fields.Many2one("account.move", string="Entry", readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Sale", readonly=True)
    date = fields.Date(readonly=True)
    date_maturity = fields.Date(string="Due Date", readonly=True)
    overdue_days = fields.Integer(string="Days Overdue", readonly=True, aggregator="max")
    age = fields.Selection(selection=AGES, string="Age", readonly=True)
    residual = fields.Float(string="Amount Due", readonly=True)

    @property
    def _table_query(self):
        overdue = SQL("(CURRENT_DATE - COALESCE(aml.date_maturity, aml.date))")
        return SQL(
            """
            SELECT aml.id * 2 AS id,
                   CASE WHEN acc.account_type = 'asset_receivable' THEN 'customer' ELSE 'supplier' END AS kind,
                   aml.company_id, partner.commercial_partner_id AS partner_id, aml.move_id,
                   NULL::integer AS sale_order_id,
                   aml.date, aml.date_maturity, GREATEST(%(overdue)s, 0) AS overdue_days,
                   CASE WHEN %(overdue)s <= 0 THEN '0_not_due'
                        WHEN %(overdue)s <= 30 THEN '1_30'
                        WHEN %(overdue)s <= 60 THEN '2_60'
                        WHEN %(overdue)s <= 90 THEN '3_90'
                        ELSE '4_over_90'
                   END AS age,
                   CASE WHEN acc.account_type = 'asset_receivable' THEN aml.amount_residual
                        ELSE -aml.amount_residual END AS residual
              FROM account_move_line aml
              JOIN account_account acc ON acc.id = aml.account_id
              LEFT JOIN res_partner partner ON partner.id = aml.partner_id
             WHERE acc.account_type IN ('asset_receivable', 'liability_payable')
                   AND aml.parent_state = 'posted'
                   AND NOT aml.reconciled
                   AND aml.amount_residual != 0
            UNION ALL
            SELECT sol.id * 2 + 1, 'to_invoice', so.company_id, partner.commercial_partner_id,
                   NULL, so.id, so.date_order::date, NULL, 0, NULL, sol.untaxed_amount_to_invoice
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
              JOIN res_partner partner ON partner.id = so.partner_id
             WHERE so.state = 'sale' AND sol.untaxed_amount_to_invoice != 0
            """,
            overdue=overdue,
        )
