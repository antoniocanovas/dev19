from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class StockLotChangeWizard(models.TransientModel):
    _name = "stock.lot.change.wizard"
    _description = "Corregir lote de una línea de venta, servida o pendiente"

    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Línea de venta",
        required=True,
        readonly=True,
    )
    order_id = fields.Many2one(related="sale_line_id.order_id", readonly=True)
    product_id = fields.Many2one(related="sale_line_id.product_id", readonly=True)
    line_ids = fields.One2many(
        comodel_name="stock.lot.change.wizard.line",
        inverse_name="wizard_id",
        string="Entregas",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" in fields_list and res.get("sale_line_id"):
            sale_line = self.env["sale.order.line"].browse(res["sale_line_id"])
            move_lines = sale_line.move_ids.move_line_ids.filtered(
                lambda ml: ml.state != "cancel" and ml.lot_id
            )
            res["line_ids"] = [
                Command.create({
                    "move_line_id": ml.id,
                    "current_lot_id": ml.lot_id.id,
                    "quantity": ml.quantity,
                    "new_lot_id": ml.lot_id.id,
                })
                for ml in move_lines
            ]
        return res

    def action_apply(self):
        self.ensure_one()
        changed = self.line_ids.filtered(lambda l: l.new_lot_id != l.current_lot_id)
        if not changed:
            raise UserError(_("No has cambiado ningún lote."))

        wrong_product = changed.filtered(
            lambda l: l.new_lot_id.product_id != self.product_id
        )
        if wrong_product:
            raise UserError(
                _("El lote de destino debe ser del mismo producto que la línea de venta.")
            )

        # Un anticipo (importe/kg facturado sin `invoiced=True`) no bloquea: la
        # liquidación final aún no está fijada. La facturación firme tampoco
        # bloquea aunque esté completa, porque es responsabilidad nuestra frente
        # al proveedor y no depende de a qué venta se atribuya el lote.
        lots_involved = changed.current_lot_id | changed.new_lot_id
        blocked = lots_involved.filtered(
            lambda lot: lot.invoiced and not lot.mercas_firm_negotiation
        )
        if blocked:
            raise UserError(
                _("No se puede corregir: los siguientes lotes ya tienen la "
                  "liquidación por venta facturada por completo al proveedor: %s")
                % ", ".join(blocked.mapped("name"))
            )

        draft_invoice_lines = self.sale_line_id.invoice_lines.filtered(
            lambda l: l.parent_state == "draft"
        )

        # Campo opcional de stock_restrict_lot (OCA stock-logistics-workflow):
        # si está instalado, la restricción de lote del movimiento debe seguir
        # a la corrección para no quedar apuntando al lote equivocado.
        has_restrict_lot_id = "restrict_lot_id" in self.env["stock.move"]._fields

        # El grupo "Corregir lotes" no implica por sí mismo poder escribir en
        # pedidos de venta o facturas ajenos; el control de acceso real ya lo
        # impone el ACL de este asistente, así que las escrituras concretas
        # (todas sobre un campo de trazabilidad, no financiero) se hacen con
        # sudo para no obligar a dar permisos de Ventas/Contabilidad aparte.
        for line in changed:
            old_lot = line.current_lot_id
            new_lot = line.new_lot_id
            # Escribir lot_id en una línea de albarán ya validada (`done`) ya
            # corrige las existencias físicas (stock.quant) en origen y
            # destino de esa línea: es comportamiento nativo de
            # stock.move.line.write() (deshace el efecto del lote antiguo y
            # aplica el del nuevo antes/después de super().write()), no hace
            # falta ningún ajuste manual aparte.
            line.move_line_id.sudo().lot_id = new_lot.id
            if has_restrict_lot_id:
                line.move_line_id.move_id.sudo().restrict_lot_id = new_lot.id
            draft_invoice_lines.filtered(lambda l: l.lot_id == old_lot).sudo().write(
                {"lot_id": new_lot.id}
            )
            note = _(
                "Corrección de lote: %(qty)s %(uom)s del pedido %(order)s "
                "(%(product)s) trasladados de %(old)s a %(new)s por %(user)s."
            ) % {
                "qty": line.quantity,
                "uom": line.move_line_id.product_uom_id.name,
                "order": self.order_id.name,
                "product": self.product_id.display_name,
                "old": old_lot.name,
                "new": new_lot.name,
                "user": self.env.user.name,
            }
            old_lot.message_post(body=note)
            new_lot.message_post(body=note)

        # El campo lote de la propia línea de venta es un único valor: si la
        # corrección reparte cantidad entre varios lotes de destino, se queda
        # con el de mayor cantidad corregida como referencia principal.
        self.sale_line_id.sudo().lot_id = max(changed, key=lambda l: l.quantity).new_lot_id

        return {"type": "ir.actions.act_window_close"}


class StockLotChangeWizardLine(models.TransientModel):
    _name = "stock.lot.change.wizard.line"
    _description = "Entrega a corregir"

    wizard_id = fields.Many2one(
        comodel_name="stock.lot.change.wizard",
        required=True,
        ondelete="cascade",
    )
    move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Línea de albarán",
        required=True,
        readonly=True,
    )
    current_lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lote actual",
        readonly=True,
    )
    quantity = fields.Float(string="Cantidad", readonly=True)
    new_lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lote correcto",
    )
