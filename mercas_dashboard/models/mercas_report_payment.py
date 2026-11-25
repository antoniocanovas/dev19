from odoo import fields, models
from odoo.tools import SQL


class MercasReportPayment(models.Model):
    """ The payments collected from the customers (Dashboards > Mercas > Debt and Payments), as
    the management summary: inbound payments of customers, in process or paid. """
    _name = "mercas.report.payment"
    _description = "Mercas: Payments Collected"
    _auto = False
    _rec_name = "date"
    _order = "date desc"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    journal_id = fields.Many2one("account.journal", string="Journal", readonly=True)
    payment_id = fields.Many2one(
        "account.payment", string="Payments", readonly=True, aggregator="count_distinct",
    )
    amount = fields.Float(string="Collected", readonly=True)

    @property
    def _table_query(self):
        return SQL(
            """
            SELECT pay.id, pay.date, pay.company_id, partner.commercial_partner_id AS partner_id,
                   pay.journal_id, pay.id AS payment_id, pay.amount
              FROM account_payment pay
              LEFT JOIN res_partner partner ON partner.id = pay.partner_id
             WHERE pay.payment_type = 'inbound' AND pay.partner_type = 'customer'
                   AND pay.state IN ('in_process', 'paid')
            """
        )
