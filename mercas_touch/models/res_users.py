from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    mercas_touch_numpad = fields.Selection(
        selection=[
            ('auto', "Automatic"),
            ('show', "Show"),
            ('hide', "Hide"),
        ],
        string="Market Counter Keypad",
        default='auto',
        required=True,
        help="Keypad and calculator on the screen of the Market Counter. Automatic: shown on a "
             "touch screen, hidden with a mouse and a keyboard.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['mercas_touch_numpad']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['mercas_touch_numpad']
