from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    user_single_session_enforce = fields.Boolean(
        string="Sesión única por usuario",
        config_parameter='user_single_session.enforce',
        help="Si un usuario inicia sesión mientras ya tiene otra sesión activa "
             "en otro dispositivo, deberá cerrar el resto de sesiones antes de "
             "poder acceder al backend. Se puede exceptuar a usuarios concretos "
             "desde su ficha (\"Permitir varias sesiones\").",
    )
