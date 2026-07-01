from odoo import Command, _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_compensate(self):
        """Create a compensation journal entry that pays the vendor bill and generates
        an outstanding credit on the partner's customer invoices."""
        self.ensure_one()

        if self.payment_state in ("paid", "in_payment"):
            raise UserError(_("Esta factura ya está pagada o en proceso de pago."))
        if self.amount_residual <= 0:
            raise UserError(_("No hay importe pendiente en esta factura."))

        journal = self.company_id.compensation_journal_id
        if not journal:
            raise UserError(
                _("Configure el diario de compensación en la pestaña Mercas de la empresa.")
            )

        bill_payable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
            and not l.reconciled
        )[:1]
        if not bill_payable_line:
            raise UserError(
                _("No se encontró línea de cuenta a pagar pendiente en la factura.")
            )

        partner = self.partner_id.commercial_partner_id
        receivable_account = partner.property_account_receivable_id
        if not receivable_account:
            raise UserError(
                _("El partner '%s' no tiene cuenta a cobrar configurada.") % partner.name
            )

        amount = self.amount_residual
        label = _("Compensación %s") % self.name

        compensation = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": self.invoice_date or self.date,
            "ref": label,
            "line_ids": [
                Command.create({
                    "account_id": bill_payable_line.account_id.id,
                    "partner_id": partner.id,
                    "debit": amount,
                    "credit": 0.0,
                    "name": label,
                }),
                Command.create({
                    "account_id": receivable_account.id,
                    "partner_id": partner.id,
                    "debit": 0.0,
                    "credit": amount,
                    "name": label,
                }),
            ],
        })
        compensation.action_post()

        comp_payable_line = compensation.line_ids.filtered(
            lambda l: l.account_id == bill_payable_line.account_id
        )
        (comp_payable_line | bill_payable_line).reconcile()
