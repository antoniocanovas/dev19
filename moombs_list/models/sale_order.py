# -*- coding: utf-8 -*-
"""
Sale Order Extensions
=====================

Extends sale.order to link with baby lists.

Stories: LST-010
"""

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    moombs_product_summary = fields.Text(
        string='Product Summary',
        compute='_compute_moombs_product_fields',
    )
    moombs_product_image = fields.Binary(
        string='Product Image',
        compute='_compute_moombs_product_fields',
    )
    amount_discount = fields.Monetary(
        string='Discounts',
        compute='_compute_amount_discount',
        help='Total discount amount across all order lines',
    )
    baby_list_id = fields.Many2one(
        'baby.list',
        string='Gift List',
        index=True,
        help='Linked baby/gift list',
    )

    is_gift_list_order = fields.Boolean(
        string='Is Gift List Order',
        compute='_compute_is_gift_list_order',
        store=True,
    )

    @api.depends(
        'order_line.product_id',
        'order_line.product_id.default_code',
        'order_line.product_id.name',
        'order_line.product_id.image_128',
        'order_line.is_downpayment',
        'order_line.display_type',
    )
    def _compute_moombs_product_fields(self):
        for order in self:
            products_desc = []
            first_image = False
            for line in order.order_line:
                if line.product_id and not line.is_downpayment and not line.display_type:
                    name = line.product_id.name or ''
                    default_code = line.product_id.default_code
                    if default_code:
                        desc = f"[{default_code}] {name}"
                    else:
                        desc = name
                    products_desc.append(desc)

                    if not first_image and line.product_id.image_128:
                        first_image = line.product_id.image_128

            order.moombs_product_summary = ', '.join(products_desc)
            order.moombs_product_image = first_image

    @api.depends('order_line.price_unit', 'order_line.discount', 'order_line.product_uom_qty', 'order_line.price_subtotal')
    def _compute_amount_discount(self):
        for order in self:
            total_discount = 0.0
            for line in order.order_line:
                if line.discount and line.price_unit and line.product_uom_qty:
                    # Calculate discount amount: price_unit * qty * discount / 100
                    discount_amount = (line.price_unit * line.product_uom_qty * line.discount) / 100
                    total_discount += discount_amount
            order.amount_discount = total_discount

    @api.depends('baby_list_id')
    def _compute_is_gift_list_order(self):
        for record in self:
            record.is_gift_list_order = bool(record.baby_list_id)

    def _prepare_picking(self):
        """Override to ensure delivery gets correct partner_id from SO.
        
        CRITICAL: Odoo's default _prepare_picking might use partner_shipping_id
        or partner_invoice_id, but for gift lists, we want partner_id (beneficiary).
        This ensures the delivery contact is set correctly at creation time.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info("[MOOMBS] _prepare_picking: Called for SO %s (ID=%s)", self.name, self.id)
        _logger.info("[MOOMBS] _prepare_picking: SO partner values - partner_id=%s (%s), partner_shipping_id=%s (%s), partner_invoice_id=%s (%s), baby_list_id=%s", 
                    self.partner_id.id if self.partner_id else 'None',
                    self.partner_id.name if self.partner_id else 'None',
                    self.partner_shipping_id.id if self.partner_shipping_id else 'None',
                    self.partner_shipping_id.name if self.partner_shipping_id else 'None',
                    self.partner_invoice_id.id if self.partner_invoice_id else 'None',
                    self.partner_invoice_id.name if self.partner_invoice_id else 'None',
                    self.baby_list_id.id if self.baby_list_id else 'None')
        
        res = super()._prepare_picking()
        
        _logger.info("[MOOMBS] _prepare_picking: Base result from super() - partner_id=%s, origin=%s", 
                    res.get('partner_id', 'None'), res.get('origin', 'None'))
        
        # For gift list orders, ensure partner_id is set from SO's partner_id (beneficiary)
        # AND make origin unique per item to prevent Odoo from grouping deliveries
        if self.baby_list_id and self.partner_id:
            old_partner_id = res.get('partner_id')
            res['partner_id'] = self.partner_id.id
            _logger.info("[MOOMBS] _prepare_picking: OVERRIDE - Set partner_id=%s (beneficiary) on delivery for SO %s (was: %s)", 
                        self.partner_id.id, self.name, old_partner_id)
            
            # CRITICAL: Make origin unique per gift list item to prevent grouping
            # Find the baby list item linked to this SO line
            if self.order_line:
                for line in self.order_line:
                    item = self.env['baby.list.item'].search([
                        ('sale_order_line_id', '=', line.id)
                    ], limit=1)
                    if item:
                        # Make origin unique by including item ID - prevents Odoo from grouping
                        unique_origin = f"{res.get('origin', self.name)} [Item-{item.id}]"
                        res['origin'] = unique_origin
                        _logger.info("[MOOMBS] _prepare_picking: Set unique origin=%s to prevent grouping for item %s", 
                                    unique_origin, item.id)
                        break
        else:
            _logger.warning("[MOOMBS] _prepare_picking: NOT overriding - baby_list_id=%s, partner_id=%s", 
                          self.baby_list_id.id if self.baby_list_id else 'None',
                          self.partner_id.id if self.partner_id else 'None')
        
        _logger.info("[MOOMBS] _prepare_picking: Final result - partner_id=%s, origin=%s", 
                    res.get('partner_id', 'None'), res.get('origin', 'None'))
        
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_procurement_values(self, group_id=None, **kwargs):
        """Override to:
        1. Handle group_id parameter from stock_delivery module
        2. Set partner_id on stock moves for gift list orders (CRITICAL FIX)
        
        CRITICAL: This is where stock moves get their values from SO lines.
        We MUST set partner_id here to ensure delivery contact is set correctly.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # Get MRO to find sale_stock class (skip stock_delivery)
        mro = self.__class__.__mro__
        sale_stock_cls = None
        
        # Find sale_stock in MRO (comes after stock_delivery)
        for cls in mro:
            if 'sale_stock' in cls.__module__ and hasattr(cls, '_prepare_procurement_values'):
                sale_stock_cls = cls
                break
        
        # Call parent method to get base values
        if sale_stock_cls:
            # Call sale_stock's method directly, bypassing stock_delivery
            res = super(sale_stock_cls, self)._prepare_procurement_values()
        else:
            # Fallback: try normal super() - might fail but we have no other option
            try:
                res = super()._prepare_procurement_values()
            except TypeError:
                # If it fails, get base method from registry
                base_model = self.env.registry['sale.order.line']
                for cls in base_model.__class__.__mro__:
                    if cls.__module__ == 'odoo.addons.sale.models.sale_order' and hasattr(cls, '_prepare_procurement_values'):
                        res = super(cls, self)._prepare_procurement_values()
                        break
                else:
                    raise
        
        # CRITICAL FIX: Set partner_id from SO's partner_id (beneficiary) for gift list orders
        # This ensures stock moves get the correct contact, which Odoo then copies to delivery picking
        if self.order_id and self.order_id.baby_list_id and self.order_id.partner_id:
            old_partner_id = res.get('partner_id')
            res['partner_id'] = self.order_id.partner_id.id
            _logger.info("[MOOMBS] _prepare_procurement_values: Set partner_id=%s (beneficiary) on stock move for SO line %s (SO=%s, was: %s)", 
                        self.order_id.partner_id.id, self.id, self.order_id.name, old_partner_id)
        elif self.order_id and self.order_id.baby_list_id:
            _logger.warning("[MOOMBS] _prepare_procurement_values: Gift list order but no partner_id on SO %s", 
                          self.order_id.name)
        
        return res

