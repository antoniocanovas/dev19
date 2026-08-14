from odoo import fields, models
from odoo.http import STORED_SESSION_BYTES, request

SINGLE_SESSION_PARAM = 'user_single_session.enforce'


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_multi_session = fields.Boolean(
        string="Permitir varias sesiones",
        help="Si está marcado, este usuario puede tener varias sesiones activas "
             "a la vez, saltándose la política de sesión única (útil para "
             "usuarios técnicos o de integración).",
    )

    def _mfa_url(self):
        # Mirrors the pattern used by auth_totp: only take over the login
        # flow if no other module already claimed it (e.g. 2FA), and only
        # take our own decision once that chain is exhausted.
        url = super()._mfa_url()
        if url:
            return url
        if self._must_close_other_sessions():
            return '/web/login/single_session'
        return url

    def _must_close_other_sessions(self):
        self.ensure_one()
        if self.allow_multi_session or not self._is_internal():
            return False
        if not self.env['ir.config_parameter'].sudo().get_param(SINGLE_SESSION_PARAM):
            return False
        return bool(self._get_other_active_devices())

    def _get_other_active_devices(self):
        """res.device rows for this user, excluding the session currently
        being authenticated (there is no active uid yet at this point, so
        this is called against ``request.session.sid`` directly)."""
        self.ensure_one()
        domain = [('user_id', '=', self.id)]
        current_sid = request.session.sid if request and request.session.sid else False
        if current_sid:
            domain.append(('session_identifier', '!=', current_sid[:STORED_SESSION_BYTES]))
        return self.env['res.device'].sudo().search(domain)
