from odoo import api, fields, models


class HelpdeskRagManufacturer(models.Model):
    _name = "helpdesk.rag.manufacturer"
    _description = "Fabricante de los equipos documentados"
    _order = "name"

    name = fields.Char(required=True)
    model_ids = fields.One2many("helpdesk.rag.model", "manufacturer_id")

    _sql_constraints = [
        # Sin esto acaban conviviendo "Yamaha", "YAMAHA" y "yamaha", y el
        # filtrado por fabricante deja de servir para nada.
        ("name_uniq", "unique(name)", "Ya existe un fabricante con ese nombre."),
    ]


class HelpdeskRagModel(models.Model):
    _name = "helpdesk.rag.model"
    _description = "Modelo o referencia de equipo"
    _order = "manufacturer_id, name"

    name = fields.Char(required=True, help="Referencia comercial: PSR-SX900, A57, MacBook Pro…")
    manufacturer_id = fields.Many2one(
        "helpdesk.rag.manufacturer", required=True, ondelete="cascade"
    )

    _sql_constraints = [
        ("name_manufacturer_uniq", "unique(name, manufacturer_id)",
         "Ese modelo ya existe para el mismo fabricante."),
    ]

    @api.depends("name", "manufacturer_id")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.manufacturer_id.name} {record.name}".strip()
