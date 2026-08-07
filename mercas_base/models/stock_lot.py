from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date


class StockLot(models.Model):
    _inherit = "stock.lot"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor",
        index=True,
    )
    origin_country_id = fields.Many2one(
        comodel_name="res.country",
        string="País origen",
    )
    origin_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Provincia origen",
        domain="[('country_id', '=', origin_country_id)]",
    )
    purchase_line_ids = fields.One2many(
        comodel_name="purchase.order.line",
        inverse_name="lot_id",
        string="Líneas de compra",
    )
    sale_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="lot_id",
        string="Líneas de venta",
    )
    supplier_invoice_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="lot_id",
        string="Líneas factura proveedor",
        domain=[("move_id.move_type", "in", ["in_invoice", "in_refund"])],
    )
    customer_invoice_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="lot_id",
        string="Líneas factura cliente",
        domain=[("move_id.move_type", "in", ["out_invoice", "out_refund"])],
    )
    scrap_line_ids = fields.One2many(
        comodel_name="stock.scrap",
        inverse_name="lot_id",
        string="Desechos",
    )
    stock_move_line_ids = fields.One2many(
        comodel_name="stock.move.line",
        inverse_name="lot_id",
        string="Movimientos de stock",
    )

    # ── Liquidación ────────────────────────────────────────────────────────────

    purchase_kg = fields.Float(
        string="Kg comprados",
        compute="_compute_purchase_kg",
        digits=(16, 3),
    )
    sale_kg = fields.Float(
        string="Kg vendidos",
        compute="_compute_sale_fields",
        digits=(16, 3),
    )
    sale_amount = fields.Float(
        string="Importe vendido",
        compute="_compute_sale_fields",
        digits=(16, 2),
    )
    scrap_kg = fields.Float(
        string="Kg desechados",
        compute="_compute_scrap_kg",
        digits=(16, 3),
    )
    completed = fields.Boolean(
        string="Completado",
        compute="_compute_completed",
        store=True,
    )
    mercas_firm_negotiation = fields.Boolean(
        string="Facturación firme",
        copy=False,
        tracking=True,
        help=(
            "Se paga al proveedor la totalidad de lo recibido de este lote, "
            "con independencia de lo vendido, en vez de liquidar por venta. "
            "Toma su valor inicial de la línea de compra de origen. Solo lo "
            "puede cambiar un Gestor de contabilidad, y solo mientras el "
            "lote no tenga facturación en firme registrada."
        ),
    )
    can_edit_firm_negotiation = fields.Boolean(
        compute="_compute_can_edit_firm_negotiation",
    )
    received_kg = fields.Float(
        string="Kg recibidos",
        compute="_compute_received_kg",
        store=True,
        digits=(16, 3),
        help="Kg recibidos físicamente del proveedor (albaranes de entrada validados).",
    )
    net_invoiced_kg = fields.Float(
        string="Kg facturados (neto)",
        compute="_compute_net_invoiced_kg",
        store=True,
        digits=(16, 3),
        help="Kg de facturas de proveedor validadas menos kg de abonos validados.",
    )
    net_invoiced_amount = fields.Float(
        string="Importe facturado (neto)",
        compute="_compute_net_invoiced_amount",
        store=True,
        digits=(16, 2),
        help="Importe de facturas de proveedor posteadas menos abonos posteados de este lote.",
    )
    invoiced = fields.Boolean(
        string="Facturado",
        copy=False,
        help=(
            "Indica si el lote se considera completamente facturado al "
            "proveedor. Se actualiza automáticamente, pero puede forzarse "
            "manualmente; una vez editado a mano deja de recalcularse solo."
        ),
    )
    invoiced_locked = fields.Boolean(
        string="Facturado fijado manualmente",
        copy=False,
    )
    invoiceable = fields.Boolean(
        string="Facturable",
        compute="_compute_invoiceable",
        store=True,
        help=(
            "Candidato a facturar al proveedor: en régimen de pago total, "
            "tiene kg recibidos pendientes de facturar; en régimen de "
            "liquidación por venta, hay importe pendiente sobre lo vendido "
            "(y desechado) hasta ahora, ya esté completado (liquidación "
            "final) o con stock todavía disponible (anticipo)."
        ),
    )

    mercas_margin = fields.Float(
        string="Margen (%)",
        digits=(10, 2),
    )
    can_edit_margin = fields.Boolean(
        compute="_compute_can_edit_margin",
    )
    supplier_amount = fields.Float(
        string="Importe proveedor",
        compute="_compute_supplier_fields",
        digits=(16, 2),
    )
    supplier_price_kg = fields.Float(
        string="Precio/kg proveedor",
        compute="_compute_supplier_fields",
        inverse="_inverse_supplier_price_kg",
        digits=(16, 4),
    )
    margin = fields.Float(
        string="Margen importe",
        compute="_compute_supplier_fields",
        digits=(16, 2),
    )

    @api.depends_context("uid")
    def _compute_can_edit_firm_negotiation(self):
        is_manager = self.env.user.has_group("account.group_account_manager")
        for lot in self:
            lot.can_edit_firm_negotiation = is_manager

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.location_id.usage",
        "stock_move_line_ids.location_dest_id.usage",
    )
    def _compute_received_kg(self):
        for lot in self:
            received_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done"
                and ml.location_id.usage == "supplier"
                and ml.location_dest_id.usage == "internal"
            )
            lot.received_kg = sum(received_mls.mapped("quantity"))

    @api.depends(
        "supplier_invoice_line_ids.quantity",
        "supplier_invoice_line_ids.move_id.state",
        "supplier_invoice_line_ids.move_id.move_type",
        "supplier_invoice_line_ids.mercas_is_firm_line",
    )
    def _compute_net_invoiced_kg(self):
        """Kg facturados en régimen de negociación en firme (líneas marcadas
        `mercas_is_firm_line`). Los anticipos/liquidaciones por venta no
        cuentan aquí: no representan kg de recibido al precio de compra."""
        for lot in self:
            posted = lot.supplier_invoice_line_ids.filtered(
                lambda l: l.move_id.state == "posted" and l.mercas_is_firm_line
            )
            net = 0.0
            for line in posted:
                if line.move_id.move_type == "in_invoice":
                    net += line.quantity
                elif line.move_id.move_type == "in_refund":
                    net -= line.quantity
            lot.net_invoiced_kg = net

    @api.depends(
        "supplier_invoice_line_ids.price_subtotal",
        "supplier_invoice_line_ids.move_id.state",
        "supplier_invoice_line_ids.move_id.move_type",
    )
    def _compute_net_invoiced_amount(self):
        for lot in self:
            posted = lot.supplier_invoice_line_ids.filtered(
                lambda l: l.move_id.state == "posted"
            )
            net = 0.0
            for line in posted:
                if line.move_id.move_type == "in_invoice":
                    net += line.price_subtotal
                elif line.move_id.move_type == "in_refund":
                    net -= line.price_subtotal
            lot.net_invoiced_amount = net

    def _mercas_company(self):
        """`company_id` (compute='_compute_company_id', from product_id.company_id)
        is empty for any lot whose product has no company set (a product
        shared across companies) unless something wrote it explicitly (e.g.
        `_mercas_autocreate_lots` does, from the purchase order's own
        company) -- reading Mercas company settings via `self.company_id.x`
        directly would then silently see nothing instead of the intended
        configuration. Fall back to the current company in that case."""
        self.ensure_one()
        return self.company_id or self.env.company

    def _mercas_liquidation_gross(self):
        """Valor bruto de liquidación por venta de este lote: el definitivo
        (sale_amount neto de margen) si está completado (sin stock), o una
        estimación de anticipo si todavía queda stock -- en ambos casos es
        siempre el importe de lo realmente vendido neto de margen (el
        desecho no se paga nunca). La cantidad/precio que se reparte ese
        importe depende de `company.liquidation_mode`:
        - "average_price": vendido + desechado (el desecho diluye el
          precio/kg de la única línea, sin aparecer aparte).
        - "average_price_scrap_split": solo lo vendido (el desecho se
          factura aparte a precio 0, ver `_mercas_prepare_invoice_lines`).
        Devuelve (cantidad, precio, importe)."""
        self.ensure_one()
        if self.completed:
            amount = self.supplier_amount
        elif not self.sale_kg:
            return 0.0, 0.0, 0.0
        else:
            amount = self.sale_amount * (1.0 - self.mercas_margin / 100.0)

        if self._mercas_company().liquidation_mode == "average_price_scrap_split":
            qty = self.sale_kg
        elif self.completed:
            qty = self.purchase_kg
        else:
            qty = self.sale_kg + self.scrap_kg
        price_kg = amount / qty if qty > 0 else 0.0
        return qty, price_kg, amount

    @api.depends(
        "invoiced", "mercas_firm_negotiation", "received_kg", "net_invoiced_kg",
        "completed", "net_invoiced_amount", "sale_kg", "scrap_kg", "sale_amount",
        "mercas_margin", "purchase_kg", "supplier_price_kg", "supplier_amount",
    )
    def _compute_invoiceable(self):
        for lot in self:
            if lot.invoiced:
                lot.invoiceable = False
            elif lot.mercas_firm_negotiation:
                lot.invoiceable = lot.received_kg > lot.net_invoiced_kg
            else:
                _, _, gross = lot._mercas_liquidation_gross()
                lot.invoiceable = gross - lot.net_invoiced_amount > 0.01

    def _mercas_recompute_invoiced_status(self):
        """Reevalúa `invoiced` tras postear una factura o abono de proveedor
        con líneas de lote. No toca lotes bloqueados a mano (invoiced_locked)."""
        for lot in self:
            if lot.invoiced_locked:
                continue
            if lot.mercas_firm_negotiation:
                if lot.received_kg <= 0:
                    continue
                new_value = lot.net_invoiced_kg >= lot.received_kg
            else:
                if not lot.completed:
                    # Los anticipos con stock pendiente nunca cierran el lote.
                    continue
                _, _, gross = lot._mercas_liquidation_gross()
                if gross <= 0:
                    continue
                new_value = lot.net_invoiced_amount >= gross - 0.01
            if lot.invoiced != new_value:
                lot.with_context(mercas_auto_invoiced=True).write({"invoiced": new_value})

    def action_open_scrap(self):
        """Open the standard scrap wizard (same one stock.picking's own
        "Scrap" button opens), pre-filled with this lot's product and lot
        and quantity left at 0 for the user to fill in.

        `company_id` falls back to the current company when the lot's own
        (computed from product_id.company_id) is empty -- a product shared
        across companies (no company set) leaves the lot without one too.
        Passing that empty value through as `default_company_id` used to
        leave stock.scrap's own `company_id` blank, which in turn skips its
        `location_id`/`scrap_location_id` computes entirely (both guard on
        `if scrap.company_id`) and, combined with `check_company=True`,
        left the location dropdowns with nothing to offer either.

        `location_id` is set explicitly from this lot's own stock instead
        of leaving it to stock.scrap's generic default (the "first"
        warehouse for the company, oblivious to the lot) -- with more than
        one warehouse that default can easily point at a location where
        this lot has no stock at all."""
        self.ensure_one()
        view = self.env.ref("stock.stock_scrap_form_view2")
        quant = self.quant_ids.filtered(
            lambda q: q.quantity > 0 and q.location_id.usage == "internal"
        )[:1]
        context = {
            "default_product_id": self.product_id.id,
            "default_lot_id": self.id,
            "default_scrap_qty": 0,
            "default_company_id": self._mercas_company().id,
        }
        if quant:
            context["default_location_id"] = quant.location_id.id
        return {
            "name": _("Desechar"),
            "type": "ir.actions.act_window",
            "res_model": "stock.scrap",
            "view_mode": "form",
            "view_id": view.id,
            "views": [(view.id, "form")],
            "target": "new",
            "context": context,
        }

    def _mercas_has_firm_invoicing(self):
        self.ensure_one()
        return bool(self.supplier_invoice_line_ids.filtered(
            lambda l: l.move_id.state == "posted" and l.mercas_is_firm_line
        ))

    def _mercas_unreconciled_settlement_amount(self):
        """Importe neto ya facturado por liquidación por venta (anticipos u
        otras liquidaciones), pendiente de descontar en la primera factura en
        firme de este lote. Una vez descontado, la propia línea de descuento
        (no marcada como firme) lo cancela a cero para siempre."""
        self.ensure_one()
        non_firm = self.supplier_invoice_line_ids.filtered(
            lambda l: l.move_id.state == "posted" and not l.mercas_is_firm_line
        )
        amount = 0.0
        for line in non_firm:
            if line.move_id.move_type == "in_invoice":
                amount += line.price_subtotal
            elif line.move_id.move_type == "in_refund":
                amount -= line.price_subtotal
        return amount

    def write(self, vals):
        if "invoiced" in vals and not self.env.context.get("mercas_auto_invoiced"):
            vals = dict(vals, invoiced_locked=True)
        if "mercas_firm_negotiation" in vals:
            propagating = self.env.context.get("mercas_propagate_firm_negotiation")
            for lot in self:
                if lot.mercas_firm_negotiation == vals["mercas_firm_negotiation"]:
                    continue
                if lot._mercas_has_firm_invoicing():
                    raise UserError(
                        _("No se puede cambiar la negociación en firme del lote "
                          "'%s': ya tiene facturación en firme registrada.")
                        % lot.name
                    )
                if not propagating and not self.env.user.has_group(
                    "account.group_account_manager"
                ):
                    raise UserError(
                        _("Solo un Gestor de contabilidad puede cambiar la "
                          "negociación en firme de un lote.")
                    )
        return super().write(vals)

    @api.constrains("purchase_line_ids")
    def _check_single_purchase_partner(self):
        for lot in self:
            partners = lot.purchase_line_ids.order_id.partner_id
            if len(partners) > 1:
                raise ValidationError(
                    _(
                        "El lote '%(lot)s' tiene líneas de compra de distintos "
                        "proveedores (%(partners)s). Por trazabilidad, un lote "
                        "solo puede estar asociado a un único proveedor."
                    )
                    % {
                        "lot": lot.name,
                        "partners": ", ".join(partners.mapped("name")),
                    }
                )

    @api.depends("name", "product_qty", "quant_ids.reserved_quantity", "partner_id", "create_date")
    @api.depends_context("lot_display_with_qty")
    def _compute_display_name(self):
        if not self.env.context.get("lot_display_with_qty"):
            return super()._compute_display_name()
        for lot in self:
            on_hand = lot.product_qty
            available = on_hand - sum(lot.quant_ids.mapped("reserved_quantity"))
            parts = ["%s (%s/%s)" % (
                lot.name,
                self._format_qty(on_hand),
                self._format_qty(available),
            )]
            if lot.partner_id:
                parts.append(lot.partner_id.name)
            if lot.create_date:
                parts.append(format_date(self.env, lot.create_date))
            lot.display_name = " - ".join(parts)

    @api.model
    def _format_qty(self, qty):
        if qty == int(qty):
            return str(int(qty))
        return "%.2f" % qty

    @api.depends("product_qty")
    def _compute_completed(self):
        for lot in self:
            lot.completed = lot.product_qty <= 0

    @api.depends("purchase_line_ids.product_qty", "purchase_line_ids.order_id.state")
    def _compute_purchase_kg(self):
        for lot in self:
            lines = lot.purchase_line_ids.filtered(
                lambda l: l.order_id.state in ("purchase", "done")
            )
            lot.purchase_kg = sum(lines.mapped("product_qty"))

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.move_id.sale_line_id",
        "stock_move_line_ids.move_id.sale_line_id.price_unit",
        "stock_move_line_ids.move_id.sale_line_id.discount",
    )
    def _compute_sale_fields(self):
        for lot in self:
            sale_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done" and ml.move_id.sale_line_id
            )
            lot.sale_kg = sum(sale_mls.mapped("quantity"))
            amount = 0.0
            for ml in sale_mls:
                sl = ml.move_id.sale_line_id
                amount += ml.quantity * sl.price_unit * (1.0 - sl.discount / 100.0)
            lot.sale_amount = amount

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.location_id.usage",
        "stock_move_line_ids.location_dest_id.usage",
    )
    def _compute_scrap_kg(self):
        for lot in self:
            loss_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done"
                and ml.location_id.usage == "internal"
                and ml.location_dest_id.usage in ("production", "inventory")
            )
            gain_mls = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done"
                and ml.location_id.usage == "inventory"
                and ml.location_dest_id.usage == "internal"
            )
            lot.scrap_kg = (
                sum(loss_mls.mapped("quantity")) - sum(gain_mls.mapped("quantity"))
            )

    @api.depends_context("uid")
    def _compute_can_edit_margin(self):
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")
        for lot in self:
            lot.can_edit_margin = is_manager

    @api.depends(
        "stock_move_line_ids.quantity",
        "stock_move_line_ids.state",
        "stock_move_line_ids.move_id.sale_line_id",
        "stock_move_line_ids.move_id.sale_line_id.price_unit",
        "stock_move_line_ids.move_id.sale_line_id.discount",
        "purchase_line_ids.product_qty",
        "purchase_line_ids.order_id.state",
        "mercas_margin",
    )
    def _compute_supplier_fields(self):
        for lot in self:
            supplier_amount = lot.sale_amount * (1.0 - lot.mercas_margin / 100.0)
            lot.supplier_amount = supplier_amount
            lot.supplier_price_kg = (
                supplier_amount / lot.purchase_kg if lot.purchase_kg else 0.0
            )
            lot.margin = lot.sale_amount - supplier_amount

    def _inverse_supplier_price_kg(self):
        """Editar el precio/kg a mano recalcula el margen equivalente --
        `mercas_margin` sigue siendo el único campo realmente persistido, el
        resto se deriva siempre de él (ver `_compute_supplier_fields`), así
        que escribir aquí simplemente resuelve qué margen produciría el
        precio introducido y lo guarda en su lugar.

        Sin importe vendido (`sale_amount = 0`, típico antes de la primera
        venta) no hay base sobre la que calcular un margen -- se ignora el
        cambio en silencio y el campo vuelve a su valor calculado (0) al
        recomputarse."""
        for lot in self:
            if not lot.sale_amount or not lot.purchase_kg:
                continue
            target_amount = lot.supplier_price_kg * lot.purchase_kg
            lot.mercas_margin = (1.0 - target_amount / lot.sale_amount) * 100.0

    @api.onchange("supplier_price_kg")
    def _onchange_supplier_price_kg(self):
        """El `inverse` de un campo compute solo se ejecuta al guardar --
        aquí se repite la misma lógica para que el margen se recalcule en
        pantalla mientras se edita el precio, sin esperar a guardar."""
        self._inverse_supplier_price_kg()

    def _mercas_invoice_origin_suffix(self):
        """Texto '<fecha> | <pedido> | <ref.proveedor> | <lote>' para anexar al
        nombre de la línea principal de un lote."""
        self.ensure_one()
        purchase_line = self.purchase_line_ids.filtered(
            lambda l: l.order_id.state in ("purchase", "done")
        )[:1]
        parts = []
        if purchase_line and purchase_line.order_id.date_order:
            parts.append(purchase_line.order_id.date_order.strftime("%d/%m/%Y"))
        if purchase_line and purchase_line.order_id.name:
            parts.append(purchase_line.order_id.name)
        if purchase_line and purchase_line.order_id.partner_ref:
            parts.append(purchase_line.order_id.partner_ref)
        parts.append(self.name)
        return " | ".join(parts), purchase_line

    def _mercas_sale_breakdown_text(self):
        """Desglose acumulado, una línea de texto por movimiento de venta
        validado de este lote: 'DD/MM/YYYY => Pedido => Cantidad uom =>
        Precio unitario símbolo_moneda'. Siempre acumulado (todas las
        ventas hasta ahora, no solo las nuevas desde la última factura) --
        igual que ya son acumulados Kg vendidos/Importe vendido, así que no
        hace falta ningún tracking nuevo de qué venta ya apareció en una
        factura anterior. Es solo texto informativo, no afecta a ningún
        importe."""
        self.ensure_one()
        sale_mls = self.stock_move_line_ids.filtered(
            lambda ml: ml.state == "done" and ml.move_id.sale_line_id
        ).sorted(lambda ml: ml.move_id.date or ml.create_date)
        lines = []
        for ml in sale_mls:
            sale_line = ml.move_id.sale_line_id
            price = sale_line.price_unit * (1.0 - sale_line.discount / 100.0)
            date_str = format_date(self.env, ml.move_id.date) if ml.move_id.date else ""
            uom = ml.product_uom_id.name or ""
            currency_symbol = sale_line.currency_id.symbol or ""
            lines.append(
                "%s => %s => %.2f %s => %.2f %s"
                % (
                    date_str, sale_line.order_id.name, ml.quantity, uom,
                    price, currency_symbol,
                )
            )
        return "\n".join(lines)

    def _mercas_scrap_breakdown_text(self):
        """Desglose acumulado de las regularizaciones de desecho de este
        lote, una línea de texto por movimiento: 'DD/MM/YYYY => Cantidad
        UdM'. Mismo criterio de movimientos que `_compute_scrap_kg`
        (desechos formales y ajustes de inventario negativos en positivo,
        ajustes positivos en negativo -- para que la suma cuadre con el
        neto de la propia línea de desecho). Acumulado, mismo motivo que
        `_mercas_sale_breakdown_text`: no hace falta ningún tracking de qué
        regularización ya apareció en una factura anterior."""
        self.ensure_one()
        loss_mls = self.stock_move_line_ids.filtered(
            lambda ml: ml.state == "done"
            and ml.location_id.usage == "internal"
            and ml.location_dest_id.usage in ("production", "inventory")
        )
        gain_mls = self.stock_move_line_ids.filtered(
            lambda ml: ml.state == "done"
            and ml.location_id.usage == "inventory"
            and ml.location_dest_id.usage == "internal"
        )
        entries = [(ml, ml.quantity) for ml in loss_mls]
        entries += [(ml, -ml.quantity) for ml in gain_mls]
        entries.sort(key=lambda entry: entry[0].move_id.date or entry[0].create_date)
        lines = []
        for ml, qty in entries:
            date_str = format_date(self.env, ml.move_id.date) if ml.move_id.date else ""
            uom = ml.product_uom_id.name or ""
            lines.append("%s => %.2f %s" % (date_str, qty, uom))
        return "\n".join(lines)

    def _mercas_prepare_invoice_lines(self):
        """Líneas de factura de proveedor para este lote, según régimen.
        Para el régimen de liquidación por venta, si ya hay anticipos previos
        posteados, añade una línea de descuento por cada uno (igual que el
        estándar de Odoo con los anticipos de venta)."""
        self.ensure_one()
        origin_suffix, purchase_line = self._mercas_invoice_origin_suffix()

        if self.mercas_firm_negotiation:
            pending_qty = self.received_kg - self.net_invoiced_kg
            unreconciled = self._mercas_unreconciled_settlement_amount()
            if pending_qty <= 0 and unreconciled <= 0.01:
                return []
            price_unit = purchase_line.price_unit if purchase_line else 0.0
            lines = []
            if pending_qty > 0:
                lines.append(Command.create({
                    "product_id": self.product_id.id,
                    "quantity": pending_qty,
                    "price_unit": price_unit,
                    "lot_id": self.id,
                    "mercas_is_firm_line": True,
                    "name": "%s\n%s" % (self.product_id.display_name or "", origin_suffix),
                }))
            if unreconciled > 0.01:
                # Solo puede haber importe pendiente de anticipos/liquidación
                # por venta en la primera factura en firme del lote: a partir
                # de ahí la negociación queda fijada en firme y ese camino se
                # bloquea, así que nunca vuelve a hacer falta esta línea.
                lines.append(Command.create({
                    "product_id": self.product_id.id,
                    "quantity": 1,
                    "price_unit": -unreconciled,
                    "lot_id": self.id,
                    "name": _("(-) Anticipos pendientes de descontar"),
                }))
            return lines

        gross_qty, gross_price, gross_amount = self._mercas_liquidation_gross()
        if gross_amount - self.net_invoiced_amount <= 0.01:
            return []

        company = self._mercas_company()
        label = _("Liquidación") if self.completed else _("Anticipo liquidación (estimado)")
        name = "%s - %s\n%s" % (self.product_id.display_name or "", label, origin_suffix)
        if company.liquidation_show_sale_breakdown:
            breakdown = self._mercas_sale_breakdown_text()
            if breakdown:
                name = "%s\n%s" % (name, breakdown)
        lines = [Command.create({
            "product_id": self.product_id.id,
            "quantity": gross_qty,
            "price_unit": gross_price,
            "lot_id": self.id,
            "name": name,
        })]

        # Modo "desecho aparte": línea informativa a precio 0 con el total
        # desechado hasta ahora -- dejar explícito en la factura que no se
        # paga, en vez de diluirlo en el precio/kg de la línea de arriba.
        if (
            company.liquidation_mode == "average_price_scrap_split"
            and self.scrap_kg > 0
        ):
            scrap_name = "%s - %s\n%s" % (
                self.product_id.display_name or "", _("Desecho"), origin_suffix,
            )
            if company.liquidation_show_sale_breakdown:
                scrap_breakdown = self._mercas_scrap_breakdown_text()
                if scrap_breakdown:
                    scrap_name = "%s\n%s" % (scrap_name, scrap_breakdown)
            lines.append(Command.create({
                "product_id": self.product_id.id,
                "quantity": self.scrap_kg,
                "price_unit": 0.0,
                "lot_id": self.id,
                "name": scrap_name,
            }))

        prior_moves = self.supplier_invoice_line_ids.filtered(
            lambda l: l.move_id.state == "posted"
        ).mapped("move_id").sorted("invoice_date")
        for move in prior_moves:
            move_lines = self.supplier_invoice_line_ids.filtered(lambda l: l.move_id == move)
            contribution = sum(move_lines.mapped("price_subtotal"))
            if move.move_type == "in_refund":
                contribution = -contribution
            if not contribution:
                continue
            lines.append(Command.create({
                "product_id": self.product_id.id,
                "quantity": 1,
                "price_unit": -contribution,
                "lot_id": self.id,
                "name": _("(-) Anticipo ya facturado: %(invoice)s del %(date)s") % {
                    "invoice": move.name,
                    "date": format_date(self.env, move.invoice_date) if move.invoice_date else "",
                },
            }))
        return lines

    def action_create_supplier_invoices(self):
        lots = self.filtered(lambda l: l.invoiceable and l.partner_id)
        if not lots:
            raise UserError(
                _("No hay lotes facturables (completados, con anticipo de "
                  "venta pendiente, o con recibido pendiente en régimen de "
                  "pago total) sin facturar y con proveedor asignado.")
            )

        # `invoiceable` solo mira facturas posteadas (net_invoiced_kg/amount),
        # así que un lote con una factura en borrador sigue saliendo como
        # facturable y volvería a generar líneas duplicadas si se le deja pasar.
        with_draft = lots.filtered(
            lambda l: l.supplier_invoice_line_ids.move_id.filtered(
                lambda m: m.state == "draft"
            )
        )
        if with_draft:
            raise UserError(
                _("Los siguientes lotes ya tienen facturas en borrador: %s. "
                  "Confirma o elimina esas facturas antes de generar otras nuevas.")
                % ", ".join(with_draft.mapped("name"))
            )

        by_partner = {}
        for lot in lots:
            by_partner.setdefault(lot.partner_id.id, self.env["stock.lot"])
            by_partner[lot.partner_id.id] |= lot

        invoices = self.env["account.move"]
        for partner_id, partner_lots in by_partner.items():
            lines = []
            for lot in partner_lots:
                lines += lot._mercas_prepare_invoice_lines()
            if not lines:
                continue

            invoice = self.env["account.move"].create({
                "move_type": "in_invoice",
                "partner_id": partner_id,
                "invoice_date": fields.Date.context_today(self),
                "invoice_line_ids": lines,
            })

            # `invoiced` se recalcula al postear (ver account_move.py): en régimen
            # de pago total, cuando lo facturado cubre lo recibido; en régimen de
            # liquidación por venta, solo cuando además el lote está completado
            # (un anticipo con stock pendiente nunca cierra el lote por sí solo).
            # El coste de las líneas de venta solo se sincroniza en la
            # liquidación final: en un anticipo el precio es una estimación.
            for lot in partner_lots.filtered(
                lambda l: not l.mercas_firm_negotiation and l.completed
            ):
                lot._sync_sale_lines_cost()

            if self.env.company.auto_confirm_supplier_invoice:
                invoice.action_post()

            invoices |= invoice

        if not invoices:
            return

        if len(invoices) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": invoices.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "domain": [("id", "in", invoices.ids)],
            "view_mode": "list,form",
            "target": "current",
        }

    def _sync_sale_lines_cost(self):
        """Actualiza purchase_price en las líneas de venta si sale_margin está instalado."""
        if "purchase_price" not in self.env["sale.order.line"]._fields:
            return
        for lot in self:
            sale_lines = lot.stock_move_line_ids.filtered(
                lambda ml: ml.state == "done" and ml.move_id.sale_line_id
            ).mapped("move_id.sale_line_id")
            if sale_lines:
                sale_lines.write({"purchase_price": lot.supplier_price_kg})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "mercas_margin" not in vals:
                partner_id = vals.get("partner_id")
                company_id = vals.get("company_id", self.env.company.id)
                partner = (
                    self.env["res.partner"].browse(partner_id)
                    if partner_id
                    else self.env["res.partner"]
                )
                company = self.env["res.company"].browse(company_id)
                vals["mercas_margin"] = (
                    partner.mercas_margin
                    if partner and partner.mercas_margin
                    else company.mercas_margin
                )
        return super().create(vals_list)
