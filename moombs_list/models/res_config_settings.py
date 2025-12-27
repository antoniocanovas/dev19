# -*- coding: utf-8 -*-
"""
Sales Settings Extension for Gift List
======================================

Adds Gift List configuration section to Sales Settings.
Company-level setting for wallet program assignment.
"""

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Gift List Settings (Company-level)
    gift_list_wallet_program_id = fields.Many2one(
        'loyalty.program',
        string='Auto Wallet Assignment',
        domain=[('program_type', '=', 'ewallet'), ('active', '=', True)],
        help='Select the wallet program to automatically assign when creating a gift list. '
             'Only active eWallet programs are shown.',
    )

    @api.model
    def get_values(self):
        """Get current settings values (company-level)."""
        res = super().get_values()
        company = self.env.company
        # Get the config parameter value for this company
        wallet_program_id = self.env['ir.config_parameter'].sudo().get_param(
            f'moombs_list.gift_list_wallet_program_id.{company.id}'
        )
        res['gift_list_wallet_program_id'] = int(wallet_program_id) if wallet_program_id else False
        return res

    def set_values(self):
        """Save settings values (company-level)."""
        super().set_values()
        company = self.env.company
        # Save the config parameter for this company
        self.env['ir.config_parameter'].sudo().set_param(
            f'moombs_list.gift_list_wallet_program_id.{company.id}',
            self.gift_list_wallet_program_id.id or ''
        )

