from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    manufacturer_id = fields.Many2one(
        "helpdesk.rag.manufacturer",
        string="Fabricante",
        help="Acota la búsqueda de documentación a este fabricante.",
    )
    model_ids = fields.Many2many(
        "helpdesk.rag.model",
        string="Modelos",
        help="Equipo del ticket. Es lo que de verdad acota la búsqueda: medido "
        "sobre tickets reales, en 7 de cada 10 no se puede deducir el producto "
        "de lo que escribe el cliente, porque quien tiene el aparato delante no "
        "lo nombra.",
    )
    # El bridge envía los campos con record.read(), y de un many2many eso
    # devuelve ids, que al flujo no le sirven de nada. Este campo lleva los
    # nombres, que es lo que se compara contra las etiquetas de los vectores.
    model_names = fields.Char(
        string="Modelos (nombres)",
        compute="_compute_model_names",
    )

    @api.depends("model_ids.name")
    def _compute_model_names(self):
        for ticket in self:
            ticket.model_names = ", ".join(ticket.model_ids.mapped("name"))

    @api.onchange("manufacturer_id")
    def _onchange_manufacturer_id(self):
        # Sin fabricante se puede elegir cualquier modelo, así que no hay nada
        # que descartar. Al fijar uno, los modelos de otro fabricante dejan de
        # tener sentido y además desaparecen del desplegable.
        if not self.manufacturer_id:
            return
        ajenos = self.model_ids.filtered(
            lambda m: m.manufacturer_id != self.manufacturer_id
        )
        if ajenos:
            self.model_ids -= ajenos

    @api.onchange("model_ids")
    def _onchange_model_ids(self):
        # Al revés: el modelo ya dice de quién es el aparato. Rellenar aquí el
        # fabricante no es solo comodidad, es lo que permite descartar en la
        # búsqueda los documentos de otras marcas que no llevan modelo puesto.
        if self.manufacturer_id or not self.model_ids:
            return
        fabricantes = self.model_ids.mapped("manufacturer_id")
        if len(fabricantes) == 1:
            self.manufacturer_id = fabricantes
