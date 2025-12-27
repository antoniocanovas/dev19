# -*- coding: utf-8 -*-
"""
baby.list_item Model
======================

Gift list item (line) model for MOOMBS Lists.

Stories: LST-010, LST-011, LST-012, LST-020-024
Business Rules: BR-004 (One Line = One Unit), BR-008 (No Edit)
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class BabyListItem(models.Model):
    _name = 'baby.list.item'
    _description = 'Gift List Item'
    _order = 'is_cancelled, sequence, id'  # Cancelled items at bottom (LST-023)
    _rec_name = 'display_name'

    # ═══════════════════════════════════════════════════════════════
    # BASIC FIELDS
    # ═══════════════════════════════════════════════════════════════

    list_id = fields.Many2one(
        'baby.list',
        string='List',
        required=True,
        ondelete='cascade',
        index=True,
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        index=True,
    )

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # PRICE FIELDS (LST-012)
    # ═══════════════════════════════════════════════════════════════

    price_unit = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id',
        help='Price captured at add time',
    )

    discount = fields.Float(
        string='Discount (%)',
        default=0.0,
        digits='Discount',
    )

    price_final = fields.Monetary(
        string='Final Price',
        compute='_compute_price_final',
        store=True,
        currency_field='currency_id',
        help='Unit Price after discount',
    )

    # ═══════════════════════════════════════════════════════════════
    # STATE FIELD
    # ═══════════════════════════════════════════════════════════════

    state = fields.Selection(
        selection=[
            ('wished', 'Deseado'),
            ('ordered', 'Pedido'),
            ('po_draft', 'PC Borrador'),
            ('po_sent', 'PC Enviado'),
            ('received', 'Recibido'),
            ('reserved', 'Reservado'),
            ('pending', 'Pendiente'),
            ('paid', 'Pagado'),
            ('out_created', 'Entrega Creada'),
            ('delivered', 'Entregado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Status',
        compute='_compute_state',
        store=True,
        index=True,
    )

    is_active = fields.Boolean(
        string='Is Active',
        compute='_compute_is_active',
        store=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # LINKED DOCUMENTS
    # ═══════════════════════════════════════════════════════════════

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='SO Line',
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
    )

    picking_in_id = fields.Many2one(
        'stock.picking',
        string='Receipt',
    )

    picking_out_id = fields.Many2one(
        'stock.picking',
        string='Delivery Note',
    )

    picking_pending_id = fields.Many2one(
        'stock.picking',
        string='Internal Transfer',
        help='Transfer from Stock to Pending Delivery location',
    )

    pos_downpayment_id = fields.Many2one(
        'pos.order',
        string='Down Payment Order',
        help='POS order for 25% down payment',
    )

    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        help='Payment reference',
    )

    paid_by_id = fields.Many2one(
        'res.partner',
        string='Paid By',
        help='Who paid for this item',
    )

    # ═══════════════════════════════════════════════════════════════
    # CANCELLATION FIELDS
    # ═══════════════════════════════════════════════════════════════

    # Keep only date_cancelled for audit trail (Epic 5)
    date_cancelled = fields.Datetime(
        string='CAN-C',
        help='Cancelled date (audit)',
    )

    is_cancelled = fields.Boolean(
        string='Cancelled',
        default=False,
        help='Flag for cancellation',
    )

    cancel_reason = fields.Selection(
        selection=[
            ('opinion', 'Change of mind'),
            ('duplicate', 'Duplicate line'),
            ('unavailable', 'Product unavailable'),
            ('price', 'Incorrect price'),
            ('replaced', 'Replaced by another'),
            ('error', 'Error when adding'),
            ('other', 'Other'),
        ],
        string='Cancel Reason',
    )

    cancel_reason_detail = fields.Char(
        string='Reason Detail',
        help='Free text when reason is other',
    )

    # ═══════════════════════════════════════════════════════════════
    # RELATED FIELDS
    # ═══════════════════════════════════════════════════════════════

    partner_id = fields.Many2one(
        related='list_id.partner_id',
        store=True,
        string='Beneficiary',
    )

    company_id = fields.Many2one(
        related='list_id.company_id',
        store=True,
        string='Company',
    )

    currency_id = fields.Many2one(
        related='list_id.currency_id',
        store=True,
        string='Currency',
    )

    list_state = fields.Selection(
        related='list_id.state',
        string='List Status',
    )

    # Product related fields (LST-011)
    product_image = fields.Binary(
        related='product_id.image_128',
        string='Image',
    )

    product_code = fields.Char(
        related='product_id.default_code',
        string='Code',
    )

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.depends('product_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.product_id.name if record.product_id else ''

    @api.depends('price_unit', 'discount')
    def _compute_price_final(self):
        """Compute final price after discount (LST-012)."""
        for record in self:
            discount_factor = 1 - (record.discount or 0) / 100
            record.price_final = record.price_unit * discount_factor

    @api.depends(
        'is_cancelled',
        'picking_out_id',  # Note: 'picking_out_id.state' removed - manual hooks handle picking state changes
        'pos_order_id',
        'picking_pending_id',  # Note: 'picking_pending_id.state' removed - manual hooks handle picking state changes
        'picking_in_id',  # Note: 'picking_in_id.state' removed - manual hooks handle picking state changes
        'purchase_order_id',  # Note: 'purchase_order_id.state' removed - manual hooks handle PO state changes
        'pos_downpayment_id',
        'sale_order_id',
    )
    def _compute_state(self):
        """Compute state from linked documents.

        Priority order (highest to lowest):
        1. Cancelled (is_cancelled flag)
        2. Received (picking_in done) - only if PO exists (takes precedence over delivery in purchase flow)
        3. Delivered (picking_out done)
        4. Out Created (picking_out exists)
        5. Paid (pos_order_id exists = 100% paid)
        6. Pending (picking_pending done) - only if PO exists
        7. Reserved (picking_pending assigned) - only if PO exists
        7.5. Receipt Pending (picking_in exists but not validated) - only if PO exists
        8. PO Sent (purchase_order sent)
        9. PO Draft (purchase_order exists)
        10. Ordered (pos_downpayment_id exists = 25% paid, NO PO)
        11. Wished (sale_order_id exists or default)
        
        NOTE: After 25% down payment, state is "Ordered" unless a PO is created.
        "Reserved" and "Pending" only apply when a PO exists.
        """
        for item in self:
            # DEBUG: Log all field values for state computation
            _logger.info("[MOOMBS] _compute_state for item ID=%s, Product=%s", 
                       item.id, item.product_id.name if item.product_id else 'No Product')
            _logger.info("[MOOMBS]   - is_cancelled: %s", item.is_cancelled)
            _logger.info("[MOOMBS]   - picking_out_id: %s (state: %s)", 
                       item.picking_out_id.id if item.picking_out_id else False,
                       item.picking_out_id.state if item.picking_out_id else 'N/A')
            _logger.info("[MOOMBS]   - pos_order_id: %s", item.pos_order_id.id if item.pos_order_id else False)
            _logger.info("[MOOMBS]   - purchase_order_id: %s (state: %s)", 
                       item.purchase_order_id.id if item.purchase_order_id else False,
                       item.purchase_order_id.state if item.purchase_order_id else 'N/A')
            _logger.info("[MOOMBS]   - picking_in_id: %s (state: %s)", 
                       item.picking_in_id.id if item.picking_in_id else False,
                       item.picking_in_id.state if item.picking_in_id else 'N/A')
            _logger.info("[MOOMBS]   - picking_pending_id: %s (state: %s)", 
                       item.picking_pending_id.id if item.picking_pending_id else False,
                       item.picking_pending_id.state if item.picking_pending_id else 'N/A')
            _logger.info("[MOOMBS]   - pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
            _logger.info("[MOOMBS]   - sale_order_id: %s", item.sale_order_id.id if item.sale_order_id else False)
            _logger.info("[MOOMBS]   - Current state: %s", item.state)

            # Priority 1: Cancelled
            if item.is_cancelled:
                item.state = 'cancelled'
                _logger.info("[MOOMBS]   → State set to 'cancelled' (Priority 1)")
                continue

            # Priority 2: Received from vendor (only if PO exists)
            # CRITICAL: Check receipt validation BEFORE delivery validation
            # When going through purchase/receipt flow after 100% payment, receipt validation
            # should show "Received" even if delivery exists (created from 100% payment)
            # Document: Priority 7 - Received (picking_in done)
            # Only show 'received' when picking_in is validated (state='done')
            if item.purchase_order_id and item.picking_in_id and item.picking_in_id.state == 'done':
                item.state = 'received'
                _logger.info("[MOOMBS]   → State set to 'received' (Priority 2 - PO exists, picking_in validated, takes precedence over delivery)")
                continue

            # Priority 3: Delivered (customer delivery validated)
            # Only show 'delivered' if delivery is validated AND receipt is not validated (or no PO)
            # This ensures "Received" takes precedence over "Delivered" in purchase flow
            if item.picking_out_id and item.picking_out_id.state == 'done':
                item.state = 'delivered'
                _logger.info("[MOOMBS]   → State set to 'delivered' (Priority 3 - picking_out validated)")
                continue

            # Priority 4: Delivery Created
            if item.picking_out_id:
                item.state = 'out_created'
                _logger.info("[MOOMBS]   → State set to 'out_created' (Priority 4)")
                continue

            # Priority 5: Paid (100%)
            if item.pos_order_id:
                item.state = 'paid'
                _logger.info("[MOOMBS]   → State set to 'paid' (Priority 5)")
                continue

            # Priority 6: In Pending Delivery location (only if PO exists)
            # Document: Priority 5 - Pending (picking_pending done)
            if item.purchase_order_id and item.picking_pending_id and item.picking_pending_id.state == 'done':
                item.state = 'pending'
                _logger.info("[MOOMBS]   → State set to 'pending' (Priority 6 - PO exists, picking_pending validated)")
                continue

            # Priority 7: Reserved (INT assigned, only if PO exists)
            # Document: Priority 6 - Reserved (picking_pending assigned)
            if item.purchase_order_id and item.picking_pending_id and item.picking_pending_id.state == 'assigned':
                item.state = 'reserved'
                _logger.info("[MOOMBS]   → State set to 'reserved' (Priority 7 - PO exists, picking_pending assigned)")
                continue

            # Priority 7.5: Receipt Created but Not Validated (only if PO exists)
            # When receipt is created (picking_in_id exists) but not validated (state != 'done'),
            # show 'pending' status to indicate receipt is pending validation
            # This is AFTER Priority 2 (Received) but BEFORE Priority 8 (PO Sent) so it takes precedence over PO Sent
            if item.purchase_order_id and item.picking_in_id and item.picking_in_id.state != 'done':
                item.state = 'pending'
                _logger.info("[MOOMBS]   → State set to 'pending' (Priority 7.5 - Receipt created but not validated, PO exists)")
                _logger.info("[MOOMBS]   → picking_in_id=%s, picking_in_id.state=%s (not 'done')", 
                            item.picking_in_id.id, item.picking_in_id.state)
                continue

            # Priority 8: PO Sent
            # CRITICAL: Check PO state AFTER checking receipt status
            # This ensures PO Sent is shown when PO is sent but receipt is not yet created
            # SAFE ACCESS: Read state directly without triggering dependency tracking
            if item.purchase_order_id:
                try:
                    po_state = item.purchase_order_id.state  # Read state safely
                    if po_state == 'sent':
                        item.state = 'po_sent'
                        _logger.info("[MOOMBS]   → State set to 'po_sent' (Priority 8 - PO state='sent')")
                        _logger.info("[MOOMBS]   → purchase_order_id=%s, purchase_order_id.state=%s", 
                                    item.purchase_order_id.id, po_state)
                        continue
                except (KeyError, AttributeError) as e:
                    # If state access fails (e.g., during write operations), skip this priority
                    _logger.warning("[MOOMBS]   → Could not read PO state for item ID=%s (non-critical): %s", item.id, e)
                    # Fall through to Priority 9

            # Priority 9: PO Draft (PO exists)
            if item.purchase_order_id:
                item.state = 'po_draft'
                _logger.info("[MOOMBS]   → State set to 'po_draft' (Priority 9 - PO exists, blocking 'ordered')")
                continue

            # Priority 10: Ordered (25% paid, NO PO)
            if item.pos_downpayment_id:
                item.state = 'ordered'
                _logger.info("[MOOMBS]   → State set to 'ordered' (Priority 10 - pos_downpayment_id exists, NO PO)")
                continue

            # Priority 11: Wished (SO exists or default)
            item.state = 'wished'
            _logger.info("[MOOMBS]   → State set to 'wished' (Priority 11 - default)")
            
            _logger.info("[MOOMBS] Final state for item ID=%s: %s", item.id, item.state)
        
        # Send bus notification to trigger UI refresh (works even if websockets fail)
        self._notify_state_change()

    def _notify_state_change(self):
        """Send bus notification to trigger UI refresh when state changes.
        
        This works even if websockets fail - Odoo will use longpolling as fallback.
        Uses Odoo's standard bus notification mechanism.
        """
        if not self:
            return
        
        try:
            # Invalidate cache to force UI refresh
            self.invalidate_recordset(['state'])
            
            # Send bus notifications using Odoo's standard mechanism
            # This triggers UI refresh via longpolling if websockets fail
            bus_obj = self.env['bus.bus']
            
            for item in self:
                # Notify about item state change - use standard Odoo notification format
                # Channel format: (dbname, model, id)
                channel = (self.env.cr.dbname, 'baby.list.item', item.id)
                message = {
                    'type': 'baby_list_item_state_changed',
                    'item_id': item.id,
                    'state': item.state,
                    'list_id': item.list_id.id,
                }
                
                # Use _sendone if available (Odoo 19 standard)
                # _sendone signature: (dbname, model, id, message)
                if hasattr(bus_obj, '_sendone'):
                    try:
                        bus_obj._sendone(channel[0], channel[1], channel[2], message)
                    except TypeError:
                        # Fallback if signature is different
                        bus_obj._sendone(*channel, message)
                elif hasattr(bus_obj, 'sendone'):
                    bus_obj.sendone(channel[0], channel[1], channel[2], message)
                
                # Also notify the list to refresh
                list_channel = (self.env.cr.dbname, 'baby.list', item.list_id.id)
                list_message = {
                    'type': 'baby_list_item_state_changed',
                    'message': 'Item state updated',
                }
                
                if hasattr(bus_obj, '_sendone'):
                    try:
                        bus_obj._sendone(list_channel[0], list_channel[1], list_channel[2], list_message)
                    except TypeError:
                        # Fallback if signature is different
                        bus_obj._sendone(*list_channel, list_message)
                elif hasattr(bus_obj, 'sendone'):
                    bus_obj.sendone(list_channel[0], list_channel[1], list_channel[2], list_message)
            
            _logger.info("[MOOMBS] Sent bus notifications for %s items to trigger UI refresh", len(self))
        except Exception as e:
            # Don't fail if bus notification fails - state change is more important
            # The invalidate_recordset above will still help with cache refresh
            _logger.warning("[MOOMBS] Failed to send bus notification (non-critical): %s", str(e))

    @api.depends('state')
    def _compute_is_active(self):
        for record in self:
            record.is_active = record.state not in ('delivered', 'cancelled')

    # ═══════════════════════════════════════════════════════════════
    # ONCHANGE METHODS
    # ═══════════════════════════════════════════════════════════════

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill price when product selected (LST-010)."""
        if self.product_id:
            self.price_unit = self.product_id.list_price

    # ═══════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════

    @api.constrains('list_id')
    def _check_list_active(self):
        """Cannot add items to inactive/completed list."""
        for record in self:
            if record.list_id.state not in ('draft', 'active'):
                raise ValidationError(
                    _("Cannot add items to %s list.") % record.list_id.state
                )

    # ═══════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        """Create item, capture price, and auto-create confirmed SO (LST-010)."""
        for vals in vals_list:
            # Capture price at add time if not provided
            if 'price_unit' not in vals and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['price_unit'] = product.list_price

        records = super().create(vals_list)

        # Auto-create confirmed SO for each item
        for record in records:
            record._create_sale_order()

        return records

    def _create_sale_order(self):
        """Create confirmed Sale Order for this item (LST-010).

        Creates SO with:
        - partner_id = baby list's Beneficiary 1
        - user_id = baby list's advisor
        - baby_list_id = link to baby list
        - state = 'sale' (confirmed)
        - SO line with qty=1 (BR-004)
        """
        self.ensure_one()

        # Create Sale Order
        # CRITICAL: Set partner_id, partner_shipping_id, and partner_invoice_id to beneficiary
        # This ensures Odoo copies the correct contact to delivery picking
        beneficiary_id = self.list_id.partner_id.id
        beneficiary_name = self.list_id.partner_id.name if self.list_id.partner_id else 'None'
        
        _logger.info("[MOOMBS] _create_sale_order: Creating SO for item ID=%s, Product=%s", 
                    self.id, self.product_id.name if self.product_id else 'None')
        _logger.info("[MOOMBS] _create_sale_order: Beneficiary ID=%s, Name=%s (from list_id.partner_id)", 
                    beneficiary_id, beneficiary_name)
        
        so_vals = {
            'partner_id': beneficiary_id,
            'partner_shipping_id': beneficiary_id,  # CRITICAL: Ensure delivery gets beneficiary contact
            'partner_invoice_id': beneficiary_id,   # CRITICAL: Ensure invoice gets beneficiary contact
            'user_id': self.list_id.advisor_id.id,
            'baby_list_id': self.list_id.id,
        }
        
        _logger.info("[MOOMBS] _create_sale_order: SO vals - partner_id=%s, partner_shipping_id=%s, partner_invoice_id=%s, baby_list_id=%s", 
                    so_vals['partner_id'], so_vals['partner_shipping_id'], 
                    so_vals['partner_invoice_id'], so_vals['baby_list_id'])
        
        so = self.env['sale.order'].create(so_vals)
        
        _logger.info("[MOOMBS] _create_sale_order: SO created - Name=%s, ID=%s", so.name, so.id)
        _logger.info("[MOOMBS] _create_sale_order: SO partner values - partner_id=%s (%s), partner_shipping_id=%s (%s), partner_invoice_id=%s (%s)", 
                    so.partner_id.id if so.partner_id else 'None',
                    so.partner_id.name if so.partner_id else 'None',
                    so.partner_shipping_id.id if so.partner_shipping_id else 'None',
                    so.partner_shipping_id.name if so.partner_shipping_id else 'None',
                    so.partner_invoice_id.id if so.partner_invoice_id else 'None',
                    so.partner_invoice_id.name if so.partner_invoice_id else 'None')

        # Create Sale Order Line (qty=1 per BR-004)
        so_line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.product_id.id,
            'price_unit': self.price_unit,
            'product_uom_qty': 1,  # BR-004: One Line = One Unit
        })

        # Confirm the SO
        _logger.info("[MOOMBS] _create_sale_order: Confirming SO %s (will trigger delivery creation)", so.name)
        try:
            so.action_confirm()
            _logger.info("[MOOMBS] _create_sale_order: SO %s confirmed successfully", so.name)
        except Exception as e:
            # Handle route configuration errors gracefully
            error_msg = str(e)
            if 'No rule has been found to replenish' in error_msg or 'route' in error_msg.lower():
                _logger.warning("[MOOMBS] Cannot confirm SO %s for item %s: %s. SO created but not confirmed.", 
                              so.name, self.id, error_msg)
                # Still link the SO even if confirmation failed
                self.write({
                    'sale_order_id': so.id,
                    'sale_order_line_id': so_line.id,
                })
                # Raise user-friendly error
                raise UserError(_(
                    "Cannot confirm Sale Order for product '%s'. "
                    "No delivery route configured.\n\n"
                    "To fix this:\n"
                    "1. Go to Inventory → Configuration → Warehouses\n"
                    "2. Select your warehouse\n"
                    "3. Check the 'Routes' section and ensure 'Deliver' route is enabled\n"
                    "4. Or go to Inventory → Configuration → Routes and verify delivery routes are configured\n\n"
                    "Sale Order %s has been created but not confirmed. "
                    "You can manually confirm it after fixing the route configuration."
                ) % (self.product_id.name, so.name))
            else:
                # Re-raise other errors
                raise

        # Link back to item (state will be computed automatically)
        self.write({
            'sale_order_id': so.id,
            'sale_order_line_id': so_line.id,  # Also link SO line ID
        })

    def write(self, vals):
        """Enforce BR-008: No Edit (only document links and dates allowed)."""
        # Fields that CAN be modified (BR-008)
        # Epic 5: Only document links and cancellation fields
        allowed_fields = {
            'sequence',
            'sale_order_id',
            'sale_order_line_id',
            'purchase_order_id',
            'picking_in_id',
            'picking_out_id',
            'picking_pending_id',
            'pos_order_id',
            'pos_downpayment_id',
            'paid_by_id',
            'is_cancelled',
            'cancel_reason',
            'cancel_reason_detail',
            'date_cancelled',  # Only date kept for audit
        }
        
        # Exclude computed fields from validation (they shouldn't be written directly)
        # Computed fields (even with store=True) are managed by Odoo automatically
        # Known computed fields that should be excluded from validation
        known_computed_fields = {
            'state',  # Computed from linked documents
            'price_final',  # Computed from price_unit and discount
            'display_name',  # Computed name
            'is_active',  # Computed from state
        }
        
        # Remove computed fields from vals before validation
        for computed_field in known_computed_fields:
            if computed_field in vals:
                vals.pop(computed_field, None)
        
        # Also check dynamically for any other computed fields
        for field_name in list(vals.keys()):  # Use list() to avoid modification during iteration
            field = self._fields.get(field_name)
            # Check if field is computed (field.compute is the method name/string, truthy if exists)
            if field and getattr(field, 'compute', None):
                # This is a computed field, remove it from vals
                vals.pop(field_name, None)

        # Check for forbidden modifications (excluding computed fields)
        forbidden = set(vals.keys()) - allowed_fields
        if forbidden:
            # Allow during creation (no ID yet) - this check is for existing records
            if self.ids:
                raise UserError(
                    _("Cannot edit item fields: %s. Cancel and create new.") % ', '.join(forbidden)
                )

        return super().write(vals)

    def unlink(self):
        """Prevent deletion of ordered items."""
        for record in self:
            if record.state not in ('wished', 'cancelled'):
                raise UserError(
                    _("Cannot delete %s item. Cancel it first.") % record.state
                )
        return super().unlink()

    # ═══════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════

    def action_cancel(self):
        """Open cancel wizard (LST-080)."""
        self.ensure_one()
        if self.state in ('paid', 'delivered'):
            raise UserError(_("Cannot cancel %s item.") % self.state)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Item'),
            'res_model': 'baby.list.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_item_id': self.id},
        }

    def action_view_product(self):
        """Open product form (LST-011)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_order(self):
        """Open linked sale order (LST-021)."""
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def action_view_picking(self):
        """Open linked picking (LST-021)."""
        self.ensure_one()
        picking = self.picking_out_id or self.picking_in_id
        if not picking:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Picking'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        }

    def action_view_pos_order(self):
        """Open linked POS order (payment)."""
        self.ensure_one()
        if not self.pos_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Order'),
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.pos_order_id.id,
        }

    def action_view_purchase_order(self):
        """Open linked Purchase Order (Epic 5)."""
        self.ensure_one()
        if not self.purchase_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
        }

    def action_create_delivery(self):
        """Create outgoing delivery for paid items (Epic 5)."""
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(_("Item must be paid before delivery."))

        pending_location = self.env.ref('moombs_list.stock_location_pending_delivery')
        customer_location = self.env.ref('stock.stock_location_customers')
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.company_id.id),
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': pending_location.id,
            'location_dest_id': customer_location.id,
            'partner_id': self.partner_id.id,
            'origin': _('MOOMBS: %s') % self.list_id.name,
            'baby_list_item_id': self.id,
            'move_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_qty': 1,
                'product_uom': self.product_id.uom_id.id,
                'location_id': pending_location.id,
                'location_dest_id': customer_location.id,
            })],
        })

        picking.action_confirm()
        picking.action_assign()

        self.write({'picking_out_id': picking.id})
        # CRITICAL: Force state recomputation after write
        self._compute_state()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }
