# -*- coding: utf-8 -*-
"""
stock.picking Extension
=======================

Hooks into stock.picking to update baby.list.item traceability.

Epic 5:
- Incoming (vendor receipt): Create INT to Pending Delivery
- Internal (to Pending): Just link, state computed
- Outgoing (customer delivery): Link picking_out_id
"""

from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    baby_list_item_id = fields.Many2one(
        'baby.list.item',
        string='Gift List Item',
        help='Link to baby list item for traceability',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to link baby list items and set partner_id for deliveries."""
        import logging
        _logger = logging.getLogger(__name__)
        
        # CRITICAL: Find item and set partner_id BEFORE super().create()
        # This ensures partner_id is set at creation time, not later
        for vals in vals_list:
            if vals.get('picking_type_code') == 'outgoing' or vals.get('picking_type_id'):
                # Check if we can determine it's an outgoing picking
                picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id', [0])[0] if isinstance(vals.get('picking_type_id'), list) else vals.get('picking_type_id'))
                if picking_type and picking_type.code == 'outgoing':
                    item = None
                    
                    _logger.info("[MOOMBS] create: Processing outgoing picking in vals (origin=%s, sale_id=%s, move_ids count=%s)", 
                                vals.get('origin', 'None'),
                                vals.get('sale_id', 'None'),
                                len(vals.get('move_ids', [])) if vals.get('move_ids') else 0)
                    
                    # CRITICAL: Invalidate cache before searching
                    self.env['baby.list.item'].invalidate_model(['sale_order_line_id', 'sale_order_id'])
                    _logger.info("[MOOMBS] create: Cache invalidated for sale_order_line_id and sale_order_id (BEFORE create)")
                    
                    # Method 1: Try via move_ids in vals (if sale_line_id is in move creation)
                    # Extract sale_line_id from move_ids before they're created
                    if vals.get('move_ids'):
                        for move_cmd in vals.get('move_ids', []):
                            if isinstance(move_cmd, (list, tuple)) and len(move_cmd) >= 3:
                                if move_cmd[0] == 0:  # CREATE command
                                    move_vals = move_cmd[2] if len(move_cmd) > 2 else {}
                                    if move_vals.get('sale_line_id'):
                                        sale_line_id = move_vals['sale_line_id']
                                        item = self.env['baby.list.item'].search([
                                            ('sale_order_line_id', '=', sale_line_id),
                                        ], limit=1)
                                        if item:
                                            _logger.info("[MOOMBS] create: Found item ID=%s via sale_line_id=%s in move_ids (BEFORE create)", 
                                                        item.id, sale_line_id)
                                            break
                    
                    # Method 2: Try via sale_id in vals
                    if not item and vals.get('sale_id'):
                        item = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', vals['sale_id']),
                        ], limit=1)
                        if item:
                            _logger.info("[MOOMBS] create: Found item ID=%s via sale_id=%s in vals (BEFORE create)", 
                                        item.id, vals['sale_id'])
                        else:
                            # Fallback: Try via SO lines
                            so = self.env['sale.order'].browse(vals['sale_id'])
                            if so.exists() and so.order_line:
                                for so_line in so.order_line:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', so_line.id),
                                    ], limit=1)
                                    if item:
                                        _logger.info("[MOOMBS] create: Found item ID=%s via SO line ID=%s (fallback from sale_id in vals)", 
                                                    item.id, so_line.id)
                                        break
                    
                    # Method 3: Try via origin (SO name) - CRITICAL for deliveries created from SO
                    if not item and vals.get('origin'):
                        import re
                        # Try multiple patterns: S00126, S0126, SO00126, etc.
                        so_match = re.search(r'S[O0]*(\d+)', vals.get('origin', ''), re.IGNORECASE)
                        if so_match:
                            so_num = so_match.group(1)
                            so_name = 'S' + so_num.zfill(5)
                            _logger.info("[MOOMBS] create: Trying to find SO=%s from origin=%s (BEFORE create)", 
                                        so_name, vals.get('origin'))
                            so = self.env['sale.order'].search([('name', '=', so_name)], limit=1)
                            if so:
                                _logger.info("[MOOMBS] create: Found SO=%s (ID=%s) from origin (BEFORE create)", 
                                            so_name, so.id)
                                
                                # CRITICAL: Invalidate cache before searching
                                self.env['baby.list.item'].invalidate_model(['sale_order_id', 'sale_order_line_id'])
                                
                                # Try via SO lines FIRST (MORE RELIABLE - direct relationship)
                                if so.order_line:
                                    _logger.info("[MOOMBS] create: SO has %s order lines, searching for items via sale_order_line_id (BEFORE create)", 
                                                len(so.order_line))
                                    for idx, so_line in enumerate(so.order_line):
                                        _logger.info("[MOOMBS] create: Checking SO line %s/%s (ID=%s, product=%s)", 
                                                    idx+1, len(so.order_line), so_line.id,
                                                    so_line.product_id.name if so_line.product_id else 'None')
                                        item = self.env['baby.list.item'].search([
                                            ('sale_order_line_id', '=', so_line.id),
                                        ], limit=1)
                                        if item:
                                            _logger.info("[MOOMBS] create: Found item ID=%s via SO line ID=%s from origin SO=%s (BEFORE create, MOST RELIABLE)", 
                                                        item.id, so_line.id, so_name)
                                            break
                                        else:
                                            _logger.info("[MOOMBS] create: No item found for SO line ID=%s (BEFORE create)", so_line.id)
                                else:
                                    _logger.warning("[MOOMBS] create: SO=%s has NO order lines (BEFORE create)", so_name)
                                
                                # Fallback: Try via sale_order_id
                                if not item:
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_id', '=', so.id),
                                    ], limit=1)
                                    if item:
                                        _logger.info("[MOOMBS] create: Found item ID=%s via origin SO=%s (sale_order_id) in vals (BEFORE create)", 
                                                    item.id, so_name)
                                    else:
                                        _logger.warning("[MOOMBS] create: Could not find item for SO=%s (ID=%s) - sale_order_id search returned None (BEFORE create)", 
                                                      so_name, so.id)
                                        # Debug: Check if SO has lines
                                        _logger.info("[MOOMBS] create: SO has %s order lines", len(so.order_line))
                            else:
                                _logger.warning("[MOOMBS] create: Could not find SO=%s from origin=%s (BEFORE create)", 
                                              so_name, vals.get('origin'))
                    
                    # Set partner_id in vals if item found
                    if item and item.list_id and item.list_id.partner_id:
                        if not vals.get('partner_id'):
                            vals['partner_id'] = item.list_id.partner_id.id
                            _logger.info("[MOOMBS] create: Pre-set partner_id=%s (beneficiary) in vals BEFORE create", 
                                        item.list_id.partner_id.id)
                            
                            # Also set partner_id on moves in vals
                            if vals.get('move_ids'):
                                for move_cmd in vals.get('move_ids', []):
                                    if isinstance(move_cmd, (list, tuple)) and len(move_cmd) >= 3:
                                        if move_cmd[0] == 0:  # CREATE command
                                            move_vals = move_cmd[2] if len(move_cmd) > 2 else {}
                                            if not move_vals.get('partner_id'):
                                                move_vals['partner_id'] = item.list_id.partner_id.id
                                                _logger.info("[MOOMBS] create: Pre-set partner_id=%s on move in vals", 
                                                            item.list_id.partner_id.id)
        
        pickings = super().create(vals_list)
        
        _logger.info("[MOOMBS] create: Created %s picking(s) via super().create()", len(pickings))
        
        # Process incoming receipts AFTER creation - link picking_in_id when receipt is created
        for picking in pickings:
            if picking.picking_type_code == 'incoming':
                _logger.info("[MOOMBS] create: Processing incoming receipt picking %s (ID=%s) AFTER creation", 
                            picking.name, picking.id)
                _logger.info("[MOOMBS] create: Receipt picking - purchase_id=%s, origin=%s, partner_id=%s, move_ids count=%s", 
                            picking.purchase_id.id if hasattr(picking, 'purchase_id') and picking.purchase_id else 'None',
                            picking.origin or 'None',
                            picking.partner_id.id if picking.partner_id else 'None',
                            len(picking.move_ids))
                
                # NOTE: Removed invalidate_model() to avoid KeyError issues with related field paths
                
                # Find baby list items linked to this PO
                # Odoo 19 Data Model: stock.picking.purchase_id -> purchase.order (DIRECT RELATIONSHIP)
                items = []
                purchase_order = None
                
                # Method 1: Via purchase_id field (MOST RELIABLE - direct relationship)
                if hasattr(picking, 'purchase_id') and picking.purchase_id:
                    purchase_order = picking.purchase_id
                    _logger.info("[MOOMBS] create: Found PO %s (ID=%s) via picking.purchase_id (MOST RELIABLE)", 
                                purchase_order.name, purchase_order.id)
                    items = self.env['baby.list.item'].search([
                        ('purchase_order_id', '=', purchase_order.id),
                    ])
                    if items:
                        _logger.info("[MOOMBS] create: Found %s items via purchase_id (Method 1)", len(items))
                
                # Method 2: Via picking_ids relationship (fallback if purchase_id not set yet)
                if not items:
                    items = self.env['baby.list.item'].search([
                        ('purchase_order_id.picking_ids', 'in', picking.id),
                    ])
                    if items:
                        _logger.info("[MOOMBS] create: Found %s items via purchase_order_id.picking_ids (Method 2)", len(items))
                        purchase_order = items[0].purchase_order_id if items else None
                
                # Method 3: Via origin field (last resort - parse PO name from origin)
                if not items and picking.origin:
                    import re
                    # Try to find PO name in origin (e.g., "PO00001" or "Purchase Order PO00001")
                    po_match = re.search(r'PO[0]*(\d+)', picking.origin, re.IGNORECASE)
                    if po_match:
                        po_name = 'PO' + po_match.group(1).zfill(5)
                        _logger.info("[MOOMBS] create: Trying to find PO=%s from origin=%s (Method 3)", 
                                    po_name, picking.origin)
                        purchase_order = self.env['purchase.order'].search([('name', '=', po_name)], limit=1)
                        if purchase_order:
                            items = self.env['baby.list.item'].search([
                                ('purchase_order_id', '=', purchase_order.id),
                            ])
                            if items:
                                _logger.info("[MOOMBS] create: Found %s items via origin parsing (Method 3)", len(items))
                
                if items:
                    _logger.info("[MOOMBS] create: Found %s items linked to receipt picking %s via PO %s", 
                                len(items), picking.name, purchase_order.name if purchase_order else 'Unknown')
                    for item in items:
                        # Check if product matches
                        if picking.move_ids and any(move.product_id.id == item.product_id.id for move in picking.move_ids):
                            if not item.picking_in_id or item.picking_in_id.id != picking.id:
                                item.write({'picking_in_id': picking.id})
                                _logger.info("[MOOMBS] create: Linked picking_in_id=%s to item ID=%s (receipt created, not validated)", 
                                            picking.id, item.id)
                                
                                # CRITICAL: Force state recomputation to show 'pending' status (Priority 7.5)
                                # This is similar to how delivery validation works - recompute after linking
                                item._compute_state()
                                _logger.info("[MOOMBS] create: State recomputed for item ID=%s, new state=%s (receipt created, not validated)", 
                                            item.id, item.state)
                        else:
                            _logger.warning("[MOOMBS] create: Item ID=%s product_id=%s does not match receipt moves", 
                                          item.id, item.product_id.id if item.product_id else 'None')
                else:
                    _logger.info("[MOOMBS] create: No items found for receipt picking %s (may not be linked to gift list)", 
                                picking.name)
        
        # Process outgoing deliveries AFTER creation - link item and set partner_id
        # Store item found in vals_list processing for each picking
        items_by_picking = {}
        for idx, picking in enumerate(pickings):
            if picking.picking_type_code == 'outgoing':
                _logger.info("[MOOMBS] create: Processing outgoing picking %s (ID=%s) AFTER creation", 
                            picking.name, picking.id)
                _logger.info("[MOOMBS] create: Picking partner values - partner_id=%s (%s), origin=%s, sale_id=%s", 
                            picking.partner_id.id if picking.partner_id else 'None',
                            picking.partner_id.name if picking.partner_id else 'None',
                            picking.origin or 'None',
                            picking.sale_id.id if picking.sale_id else 'None')
                # Try to find item from the vals we processed earlier
                # We stored the item reference, but need to re-find it after creation
                item = None
                
                # CRITICAL: Invalidate cache before searching to ensure fresh data
                self.env['baby.list.item'].invalidate_model(['sale_order_line_id', 'sale_order_id'])
                
                # Method 1: Try via moves sale_line_id (MOST RELIABLE - direct relationship)
                # stock.move.sale_line_id -> baby.list.item.sale_order_line_id
                if picking.move_ids:
                    for move in picking.move_ids:
                        if move.sale_line_id:
                            item = self.env['baby.list.item'].search([
                                ('sale_order_line_id', '=', move.sale_line_id.id),
                            ], limit=1)
                            if item:
                                _logger.info("[MOOMBS] create: Found item ID=%s via sale_line_id=%s (AFTER create, MOST RELIABLE)", 
                                            item.id, move.sale_line_id.id)
                                break
                
                # Method 2: If picking has sale_id, find item directly
                if not item and picking.sale_id:
                    item = self.env['baby.list.item'].search([
                        ('sale_order_id', '=', picking.sale_id.id),
                    ], limit=1)
                    if item:
                        _logger.info("[MOOMBS] create: Found item ID=%s via sale_id=%s (AFTER create)", 
                                    item.id, picking.sale_id.id)
                    else:
                        # Fallback: Try via SO lines
                        so = picking.sale_id
                        if so.order_line:
                            for so_line in so.order_line:
                                item = self.env['baby.list.item'].search([
                                    ('sale_order_line_id', '=', so_line.id),
                                ], limit=1)
                                if item:
                                    _logger.info("[MOOMBS] create: Found item ID=%s via SO line ID=%s (AFTER create, fallback)", 
                                                item.id, so_line.id)
                                    break
                
                # Method 3: Try via origin (SO name) - CRITICAL for deliveries created from SO
                # This is often the ONLY way to find the item when sale_id is None (computed field)
                if not item and picking.origin:
                    import re
                    # Try multiple patterns: S00126, S0126, SO00126, etc.
                    so_match = re.search(r'S[O0]*(\d+)', picking.origin, re.IGNORECASE)
                    if so_match:
                        so_num = so_match.group(1)
                        so_name = 'S' + so_num.zfill(5)
                        _logger.info("[MOOMBS] create: Trying to find SO=%s from origin=%s (AFTER create)", 
                                    so_name, picking.origin)
                        so = self.env['sale.order'].search([('name', '=', so_name)], limit=1)
                        if so:
                            _logger.info("[MOOMBS] create: Found SO=%s (ID=%s) from origin (AFTER create)", 
                                        so_name, so.id)
                            
                            # CRITICAL: Invalidate cache before searching
                            self.env['baby.list.item'].invalidate_model(['sale_order_id', 'sale_order_line_id'])
                            
                            # Try via SO lines FIRST (MORE RELIABLE - direct relationship)
                            if so.order_line:
                                _logger.info("[MOOMBS] create: SO has %s order lines, searching for items via sale_order_line_id (AFTER create)", 
                                            len(so.order_line))
                                for idx, so_line in enumerate(so.order_line):
                                    _logger.info("[MOOMBS] create: Checking SO line %s/%s (ID=%s, product=%s)", 
                                                idx+1, len(so.order_line), so_line.id,
                                                so_line.product_id.name if so_line.product_id else 'None')
                                    item = self.env['baby.list.item'].search([
                                        ('sale_order_line_id', '=', so_line.id),
                                    ], limit=1)
                                    if item:
                                        _logger.info("[MOOMBS] create: Found item ID=%s via SO line ID=%s from origin SO=%s (AFTER create, MOST RELIABLE)", 
                                                    item.id, so_line.id, so_name)
                                        break
                                    else:
                                        _logger.info("[MOOMBS] create: No item found for SO line ID=%s (AFTER create)", so_line.id)
                                        
                                        # DEBUG: Check if any items exist with this sale_order_id
                                        items_by_so = self.env['baby.list.item'].search([
                                            ('sale_order_id', '=', so.id),
                                        ])
                                        _logger.info("[MOOMBS] create: Found %s items with sale_order_id=%s (for debugging)", 
                                                    len(items_by_so), so.id)
                                        if items_by_so:
                                            for itm in items_by_so:
                                                _logger.info("[MOOMBS] create:   - Item ID=%s, sale_order_line_id=%s, product=%s", 
                                                            itm.id, 
                                                            itm.sale_order_line_id.id if itm.sale_order_line_id else 'None',
                                                            itm.product_id.name if itm.product_id else 'None')
                            else:
                                _logger.warning("[MOOMBS] create: SO=%s has NO order lines (AFTER create)", so_name)
                            
                            # Fallback: Try via sale_order_id
                            if not item:
                                item = self.env['baby.list.item'].search([
                                    ('sale_order_id', '=', so.id),
                                ], limit=1)
                                if item:
                                    _logger.info("[MOOMBS] create: Found item ID=%s via origin SO=%s (sale_order_id) (AFTER create)", 
                                                item.id, so_name)
                                else:
                                    _logger.warning("[MOOMBS] create: Could not find item for SO=%s (ID=%s) - sale_order_id search returned None (AFTER create)", 
                                                  so_name, so.id)
                                    # Debug: Check if SO has lines
                                    _logger.info("[MOOMBS] create: SO has %s order lines", len(so.order_line))
                        else:
                            _logger.warning("[MOOMBS] create: Could not find SO=%s from origin=%s (AFTER create)", 
                                          so_name, picking.origin)
                
                if item:
                    items_by_picking[picking.id] = item
                    
                    # Link baby_list_item_id to picking
                    picking.write({'baby_list_item_id': item.id})
                    _logger.info("[MOOMBS] create: Linked baby_list_item_id=%s to picking %s", 
                                item.id, picking.name)
                    
                    # CRITICAL: Set partner_id from beneficiary (gift list partner) if not already set
                    if item.list_id and item.list_id.partner_id:
                        if not picking.partner_id or picking.partner_id.id != item.list_id.partner_id.id:
                            picking.write({'partner_id': item.list_id.partner_id.id})
                            _logger.info("[MOOMBS] create: Set partner_id=%s (beneficiary) on picking %s (was: %s)", 
                                        item.list_id.partner_id.id, picking.name,
                                        picking.partner_id.id if picking.partner_id else 'None')
                        
                        # Set on all moves
                        for move in picking.move_ids:
                            if not move.partner_id or move.partner_id.id != item.list_id.partner_id.id:
                                move.write({'partner_id': item.list_id.partner_id.id})
                                _logger.info("[MOOMBS] create: Set partner_id=%s on move %s", 
                                            item.list_id.partner_id.id, move.id)
                    
                    # CRITICAL: Link picking_out_id IMMEDIATELY so state shows "out_created"
                    if not item.picking_out_id or item.picking_out_id.id != picking.id:
                        item.write({'picking_out_id': picking.id})
                        _logger.info("[MOOMBS] create: Linked picking_out_id=%s to item %s", 
                                    picking.id, item.id)
                        
                        # Recompute state to show "out_created" (Priority 3 > Priority 4 Paid)
                        item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
                        item._compute_state()
                        _logger.info("[MOOMBS] create: State recomputed, item state=%s (picking state=%s, picking_out_id=%s, pos_order_id=%s)", 
                                    item.state, picking.state,
                                    item.picking_out_id.id if item.picking_out_id else 'None',
                                    item.pos_order_id.id if item.pos_order_id else 'None')
                else:
                    _logger.warning("[MOOMBS] create: Could not find item for outgoing picking %s (ID=%s, origin=%s, sale_id=%s)", 
                                  picking.name, picking.id, picking.origin or 'None', 
                                  picking.sale_id.id if picking.sale_id else 'None')
                    
                    # Last resort: Try via product_id + partner_id if partner is set
                    if picking.partner_id and picking.move_ids:
                        for move in picking.move_ids:
                            if move.product_id:
                                item = self.env['baby.list.item'].search([
                                    ('product_id', '=', move.product_id.id),
                                    ('list_id.partner_id', '=', picking.partner_id.id),
                                    ('picking_out_id', '=', False),  # Not already linked
                                ], limit=1)
                                if item:
                                    _logger.info("[MOOMBS] create: Found item ID=%s via product_id=%s + partner_id=%s (last resort)", 
                                                item.id, move.product_id.id, picking.partner_id.id)
                                    
                                    # Link item
                                    picking.write({'baby_list_item_id': item.id})
                                    if item.list_id.partner_id:
                                        picking.write({'partner_id': item.list_id.partner_id.id})
                                        for m in picking.move_ids:
                                            m.write({'partner_id': item.list_id.partner_id.id})
                                    item.write({'picking_out_id': picking.id})
                                    item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
                                    item._compute_state()
                                    _logger.info("[MOOMBS] create: Linked item %s via last resort method, state=%s", 
                                                item.id, item.state)
                                    break
                        if not item:
                            _logger.warning("[MOOMBS] create: Last resort search also failed for picking %s", picking.name)
        
        return pickings

    def _link_baby_list_item(self):
        """Link baby list item to picking and set partner_id for outgoing deliveries.
        
        Uses multiple fallback methods:
        1. sale_id on picking
        2. sale_line_id on moves
        3. origin field (SO name)
        4. product_id + sale_order_id from moves
        5. product_id + list_id matching
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # Only process outgoing deliveries
        if self.picking_type_code != 'outgoing':
            return
        
        # Skip if already linked
        if self.baby_list_item_id:
            return
        
        _logger.info("[MOOMBS] _link_baby_list_item: Processing picking %s (ID=%s)", 
                    self.name, self.id)
        _logger.info("[MOOMBS] _link_baby_list_item: sale_id=%s, origin=%s, partner_id=%s, move_count=%s", 
                    self.sale_id.id if self.sale_id else 'None',
                    self.origin or 'None',
                    self.partner_id.id if self.partner_id else 'None',
                    len(self.move_ids))
        
        # CRITICAL: Invalidate cache before searching to ensure fresh data
        self.env['baby.list.item'].invalidate_model(['sale_order_line_id', 'sale_order_id'])
        
        # PRIORITIZE MOST RELIABLE RELATIONSHIPS FIRST
        # Odoo 19 Data Model: stock.move.sale_line_id -> baby.list.item.sale_order_line_id (DIRECT, MOST RELIABLE)
        
        # Method 1: Try via move_ids sale_line_id (MOST RELIABLE - direct relationship)
        # stock.move.sale_line_id -> baby.list.item.sale_order_line_id
        if self.move_ids:
            for move in self.move_ids:
                if move.sale_line_id:
                    _logger.info("[MOOMBS] _link_baby_list_item: Method 1 - Found sale_line_id=%s in move (SO line ID=%s, SO ID=%s)", 
                                move.sale_line_id.id,
                                move.sale_line_id.id,
                                move.sale_line_id.order_id.id if move.sale_line_id.order_id else 'None')
                    # One SO Line = One Item
                    item = self.env['baby.list.item'].search([
                        ('sale_order_line_id', '=', move.sale_line_id.id),
                    ], limit=1)
                    
                    if item:
                        _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for sale_order_line_id=%s (MOST RELIABLE)", 
                                    item.id, move.sale_line_id.id)
                        self._link_to_item(item, _logger)
                        return
        
        # Method 2: Try via sale_id (if picking has sale order reference)
        # Note: sale_id might be a computed field, so we need to read it properly
        sale_id = False
        if hasattr(self, 'sale_id') and self.sale_id:
            sale_id = self.sale_id.id
        elif hasattr(self, 'sale_ids') and self.sale_ids:
            # Some Odoo versions use sale_ids (many2many)
            sale_id = self.sale_ids[0].id if self.sale_ids else False
        
        if sale_id:
            _logger.info("[MOOMBS] _link_baby_list_item: Method 2 - Found sale_id=%s", sale_id)
            # One SO = One Item (business rule: each item has separate SO)
            item = self.env['baby.list.item'].search([
                ('sale_order_id', '=', sale_id),
            ], limit=1)
            
            if item:
                _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for sale_id=%s", 
                            item.id, sale_id)
                self._link_to_item(item, _logger)
                return
            else:
                _logger.warning("[MOOMBS] _link_baby_list_item: No item found for sale_id=%s. "
                               "Trying via SO lines as fallback.", sale_id)
                # Fallback: Try via SO lines (more reliable than sale_order_id)
                so = self.env['sale.order'].browse(sale_id)
                if so.exists() and so.order_line:
                    for so_line in so.order_line:
                        item = self.env['baby.list.item'].search([
                            ('sale_order_line_id', '=', so_line.id),
                        ], limit=1)
                        if item:
                            _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s via SO line ID=%s (fallback from sale_id)", 
                                        item.id, so_line.id)
                            self._link_to_item(item, _logger)
                            return
        
        # Method 3: Try via origin field (might contain SO name like "S00116")
        if self.origin:
            _logger.info("[MOOMBS] _link_baby_list_item: Method 3 - Checking origin=%s", self.origin)
            # Try to find SO by name in origin
            so_name = None
            # Origin might be like "S00116" or "MOOMBS: BBP-202512-0007" or "S00116 - BBP-202512-0007"
            import re
            so_match = re.search(r'S0*(\d+)', self.origin)
            if so_match:
                so_name = 'S' + so_match.group(1).zfill(5)  # Format like S00116
                _logger.info("[MOOMBS] _link_baby_list_item: Extracted SO name=%s from origin", so_name)
                so = self.env['sale.order'].search([('name', '=', so_name)], limit=1)
                if so:
                    _logger.info("[MOOMBS] _link_baby_list_item: Found SO %s (ID=%s) from origin", so.name, so.id)
                    # One SO = One Item
                    item = self.env['baby.list.item'].search([
                        ('sale_order_id', '=', so.id),
                    ], limit=1)
                    
                    if item:
                        _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for SO ID=%s from origin", 
                                    item.id, so.id)
                        self._link_to_item(item, _logger)
                        return
                    else:
                        _logger.warning("[MOOMBS] _link_baby_list_item: No item found for SO ID=%s (name=%s). "
                                       "Item may not have sale_order_id set yet, or SO mismatch.", so.id, so.name)
                        # Force cache refresh and try again
                        self.env['baby.list.item'].invalidate_model(['sale_order_id'])
                        item = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', so.id),
                        ], limit=1)
                        if item:
                            _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s after cache refresh", item.id)
                            self._link_to_item(item, _logger)
                            return
                        # Try to find by SO name in item's sale_order_id.name as fallback
                        items_by_name = self.env['baby.list.item'].search([
                            ('sale_order_id.name', '=', so_name),
                        ], limit=1)
                        if items_by_name:
                            _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s by SO name fallback", 
                                        items_by_name.id)
                            self._link_to_item(items_by_name, _logger)
                            return
        
        # Method 4: Try via move's order_id (sale.order from stock.move)
        if self.move_ids:
            for move in self.move_ids:
                # Check if move has order_id (sale.order reference)
                if hasattr(move, 'order_id') and move.order_id:
                    _logger.info("[MOOMBS] _link_baby_list_item: Method 4 - Found order_id=%s in move", 
                                move.order_id.id)
                    # One SO = One Item, but match product for safety
                    item = self.env['baby.list.item'].search([
                        ('sale_order_id', '=', move.order_id.id),
                        ('product_id', '=', move.product_id.id),
                    ], limit=1)
                    
                    if item:
                        _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for order_id=%s, product_id=%s", 
                                    item.id, move.order_id.id, move.product_id.id)
                        self._link_to_item(item, _logger)
                        return
        
        # Method 5: Try via product_id + partner_id matching (last resort)
        if self.move_ids and self.partner_id:
            _logger.info("[MOOMBS] _link_baby_list_item: Method 5 - Fallback: product + partner matching")
            for move in self.move_ids:
                if move.product_id:
                    # One Item per product+partner combination (fallback)
                    item = self.env['baby.list.item'].search([
                        ('product_id', '=', move.product_id.id),
                        ('list_id.partner_id', '=', self.partner_id.id),
                        ('picking_out_id', '=', False),  # Not already linked
                    ], limit=1)
                    
                    if item:
                        _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for product_id=%s, partner_id=%s", 
                                    item.id, move.product_id.id, self.partner_id.id)
                        self._link_to_item(item, _logger)
                        return
        
        # Method 6: Try via product_id only (if no partner match)
        if self.move_ids:
            _logger.info("[MOOMBS] _link_baby_list_item: Method 6 - Last resort: product only")
            for move in self.move_ids:
                if move.product_id:
                    # Last resort: find by product only (one item per product+SO)
                    item = self.env['baby.list.item'].search([
                        ('product_id', '=', move.product_id.id),
                        ('picking_out_id', '=', False),  # Not already linked
                        ('sale_order_id', '!=', False),  # Has SO (means it's ordered)
                    ], limit=1)
                    
                    if item:
                        _logger.info("[MOOMBS] _link_baby_list_item: Found item ID=%s for product_id=%s (last resort)", 
                                    item.id, move.product_id.id)
                        self._link_to_item(item, _logger)
                        return
        
        _logger.warning("[MOOMBS] _link_baby_list_item: Could not link picking %s to any baby list item", 
                       self.name)

    def _link_to_item(self, item, _logger):
        """Link picking to baby list item and set partner_id."""
        # Link baby_list_item_id to picking
        self.write({'baby_list_item_id': item.id})
        _logger.info("[MOOMBS] _link_to_item: Linked baby_list_item_id=%s to picking %s", 
                    item.id, self.name)
        
        # ALWAYS set partner_id from baby list (even if already set, ensure it's correct)
        if item.list_id and item.list_id.partner_id:
            # Check current partner_id value (might be False, None, or a different ID)
            current_partner = self.partner_id.id if self.partner_id else False
            if current_partner != item.list_id.partner_id.id:
                # Set partner_id on picking
                self.write({'partner_id': item.list_id.partner_id.id})
                _logger.info("[MOOMBS] _link_to_item: Set partner_id=%s from baby list (was: %s)", 
                            item.list_id.partner_id.id, current_partner)
            else:
                _logger.info("[MOOMBS] _link_to_item: partner_id=%s already set correctly on picking", 
                            item.list_id.partner_id.id)
            
            # ALWAYS set partner_id on all moves (important for delivery/transfer documents)
            # This ensures customer name appears in all stock moves
            if self.move_ids:
                for move in self.move_ids:
                    if not move.partner_id or move.partner_id.id != item.list_id.partner_id.id:
                        move.write({'partner_id': item.list_id.partner_id.id})
                        _logger.info("[MOOMBS] _link_to_item: Set partner_id=%s on move %s (product: %s)", 
                                    item.list_id.partner_id.id, move.id, 
                                    move.product_id.name if move.product_id else 'N/A')
                    else:
                        _logger.info("[MOOMBS] _link_to_item: partner_id=%s already set on move %s", 
                                    item.list_id.partner_id.id, move.id)
        else:
            _logger.warning("[MOOMBS] _link_to_item: No partner_id on baby list (list_id=%s)", 
                           item.list_id.id if item.list_id else 'None')
        
        # Link picking_out_id to item (CRITICAL for state computation)
        # This must happen AFTER partner_id is set to ensure proper linking
        old_picking_out_id = item.picking_out_id.id if item.picking_out_id else 'None'
        old_state = item.state
        
        if not item.picking_out_id or item.picking_out_id.id != self.id:
            # CRITICAL: Invalidate cache BEFORE writing to ensure fresh read
            item.invalidate_recordset(['picking_out_id', 'pos_order_id'])
            
            _logger.info("[MOOMBS] _link_to_item: Setting picking_out_id=%s on item %s (was: %s, current state: %s)", 
                        self.id, item.id, old_picking_out_id, old_state)
            
            item.write({'picking_out_id': self.id})
            _logger.info("[MOOMBS] _link_to_item: ✓ Linked picking_out_id=%s to item %s (picking state: %s)", 
                        self.id, item.id, self.state)
            
            # CRITICAL: Invalidate cache and force state recomputation
            # Priority order: Delivered (done) > Out Created (exists) > Paid (pos_order_id)
            # This ensures "out_created" state is shown when delivery is created, even if item is paid
            item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
            
            # Force fresh read of picking state
            fresh_picking = self.env['stock.picking'].browse(self.id)
            _logger.info("[MOOMBS] _link_to_item: Fresh picking state=%s", fresh_picking.state)
            
            # Recompute state - should show "out_created" if picking exists and not done
            item._compute_state()
            _logger.info("[MOOMBS] _link_to_item: State recomputed, item state=%s (picking_out_id=%s, picking state=%s, pos_order_id=%s)", 
                        item.state, 
                        item.picking_out_id.id if item.picking_out_id else 'None',
                        fresh_picking.state,
                        item.pos_order_id.id if item.pos_order_id else 'None')
        else:
            _logger.info("[MOOMBS] _link_to_item: picking_out_id=%s already linked to item", self.id)
            # Still recompute state to ensure it's correct
            item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
            item._compute_state()
            _logger.info("[MOOMBS] _link_to_item: State recomputed, item state=%s", item.state)

    def write(self, vals):
        """Override write to link baby list items when moves are added or partner is set."""
        import logging
        _logger = logging.getLogger(__name__)
        
        res = super().write(vals)
        
        # CRITICAL: Iterate over recordset - write() can be called on multiple records
        for picking in self:
            # Try to link if:
            # 1. Moves were added
            # 2. Partner was set (might help with matching) - CRITICAL: user manually set partner
            # 3. Picking is outgoing and not yet linked
            # 4. Empty write() call (from _handle_internal_transfer) - force linking attempt
            should_link = (
                'move_ids' in vals or 
                'partner_id' in vals or
                (not picking.baby_list_item_id and picking.picking_type_code == 'outgoing') or
                (not vals and picking.picking_type_code == 'outgoing')  # Empty write from _handle_internal_transfer
            )
            
            if should_link and picking.picking_type_code == 'outgoing':
                _logger.info("[MOOMBS] write: Attempting to link item for picking %s (partner_id in vals: %s, move_ids in vals: %s, already_linked: %s)", 
                            picking.name, 'partner_id' in vals, 'move_ids' in vals, bool(picking.baby_list_item_id))
                _logger.info("[MOOMBS] write: should_link condition met, calling _link_baby_list_item()...")
                
                # Use sudo to avoid access rights issues during creation
                picking.sudo()._link_baby_list_item()
                
                _logger.info("[MOOMBS] write: _link_baby_list_item() completed, baby_list_item_id=%s", 
                            picking.baby_list_item_id.id if picking.baby_list_item_id else 'None')
                
                # If item was linked, ensure partner_id is set correctly
                if picking.baby_list_item_id:
                    item = picking.baby_list_item_id
                    if item.list_id.partner_id:
                        # Ensure partner_id is set on picking (even if user set it manually, ensure it's correct)
                        if not picking.partner_id or picking.partner_id.id != item.list_id.partner_id.id:
                            picking.write({'partner_id': item.list_id.partner_id.id})
                            _logger.info("[MOOMBS] write: Set partner_id=%s (beneficiary) on picking %s after linking", 
                                        item.list_id.partner_id.id, picking.name)
                        
                        # Ensure partner_id is set on all moves
                        for move in picking.move_ids:
                            if not move.partner_id or move.partner_id.id != item.list_id.partner_id.id:
                                move.write({'partner_id': item.list_id.partner_id.id})
                                _logger.info("[MOOMBS] write: Set partner_id=%s on move %s after linking", 
                                            item.list_id.partner_id.id, move.id)
        
        return res

    def action_confirm(self):
        """Override action_confirm to ensure linking happens after moves are confirmed.
        
        CRITICAL: After confirmation, moves are fully created with sale_line_id populated.
        This is often when we can finally find the item via sale_line_id.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        res = super().action_confirm()
        
        # After confirmation, moves are fully created, so try to link
        for picking in self:
            if picking.picking_type_code == 'outgoing':
                _logger.info("[MOOMBS] action_confirm: Processing outgoing picking %s (ID=%s, origin=%s, sale_id=%s, baby_list_item_id=%s)", 
                            picking.name, picking.id, 
                            picking.origin or 'None',
                            picking.sale_id.id if picking.sale_id else 'None',
                            picking.baby_list_item_id.id if picking.baby_list_item_id else 'None')
                
                if not picking.baby_list_item_id:
                    _logger.info("[MOOMBS] action_confirm: No item linked yet, attempting to link...")
                    picking._link_baby_list_item()
                
                # Ensure partner_id is set on picking and moves after confirmation
                if picking.baby_list_item_id:
                    item = picking.baby_list_item_id
                    _logger.info("[MOOMBS] action_confirm: Item %s linked, ensuring partner_id and picking_out_id are set", item.id)
                    
                    if item.list_id.partner_id:
                        # Set on picking
                        if not picking.partner_id or picking.partner_id.id != item.list_id.partner_id.id:
                            picking.write({'partner_id': item.list_id.partner_id.id})
                            _logger.info("[MOOMBS] action_confirm: Set partner_id=%s (beneficiary) on picking %s", 
                                        item.list_id.partner_id.id, picking.name)
                        
                        # Set on all moves
                        for move in picking.move_ids:
                            if not move.partner_id or move.partner_id.id != item.list_id.partner_id.id:
                                move.write({'partner_id': item.list_id.partner_id.id})
                                _logger.info("[MOOMBS] action_confirm: Set partner_id=%s on move %s", 
                                            item.list_id.partner_id.id, move.id)
                    
                    # CRITICAL: Ensure picking_out_id is linked (for state computation)
                    if not item.picking_out_id or item.picking_out_id.id != picking.id:
                        item.write({'picking_out_id': picking.id})
                        item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
                        item._compute_state()
                        _logger.info("[MOOMBS] action_confirm: Linked picking_out_id=%s to item %s, state=%s", 
                                    picking.id, item.id, item.state)
                else:
                    _logger.warning("[MOOMBS] action_confirm: Could not link item for picking %s after confirmation", picking.name)
        
        return res

    def button_validate(self):
        """Override to handle baby list stock operations (Epic 5)."""
        import logging
        _logger = logging.getLogger(__name__)
        
        res = super().button_validate()

        for picking in self:
            _logger.info("[MOOMBS] button_validate: Picking %s (ID=%s) type_code=%s", 
                        picking.name, picking.id, picking.picking_type_code)
            
            # Handle incoming (vendor receipt)
            if picking.picking_type_code == 'incoming':
                _logger.info("[MOOMBS] button_validate: Calling _handle_vendor_receipt for picking %s", picking.name)
                self._handle_vendor_receipt(picking)

            # Handle internal (to Pending Delivery)
            elif picking.picking_type_code == 'internal':
                _logger.info("[MOOMBS] button_validate: Calling _handle_internal_transfer for picking %s", picking.name)
                self._handle_internal_transfer(picking)

            # Handle outgoing (customer delivery)
            elif picking.picking_type_code == 'outgoing':
                _logger.info("[MOOMBS] button_validate: Calling _handle_customer_delivery for picking %s", picking.name)
                self._handle_customer_delivery(picking)
            else:
                _logger.warning("[MOOMBS] button_validate: Picking %s has unknown type_code=%s", 
                               picking.name, picking.picking_type_code)

        return res

    def _handle_vendor_receipt(self, picking):
        """When PO receipt is validated, create INT to Pending Delivery.
        
        CRITICAL: This is called when receipt is VALIDATED (state='done').
        The picking_in_id should already be linked when receipt is created (in create() method).
        This method ensures state is 'received' and creates internal transfer.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info("[MOOMBS] _handle_vendor_receipt: Receipt %s validated (state=%s)", 
                    picking.name, picking.state)
        
        # Find baby list items waiting for this PO
        for move in picking.move_ids:
            # Find items with this PO that don't have INT yet
            # NOTE: Removed invalidate_model() to avoid KeyError issues with related field paths
            
            # Odoo 19 Data Model: stock.picking.purchase_id -> purchase.order (DIRECT RELATIONSHIP)
            # Use purchase_id if available (MOST RELIABLE), fallback to picking_ids
            purchase_order = None
            if hasattr(picking, 'purchase_id') and picking.purchase_id:
                purchase_order = picking.purchase_id
                _logger.info("[MOOMBS] _handle_vendor_receipt: Found PO %s (ID=%s) via picking.purchase_id", 
                            purchase_order.name, purchase_order.id)
                items = self.env['baby.list.item'].search([
                    ('purchase_order_id', '=', purchase_order.id),
                    ('product_id', '=', move.product_id.id),
                    ('picking_pending_id', '=', False),
                ])
            else:
                # Fallback: via picking_ids relationship
                _logger.info("[MOOMBS] _handle_vendor_receipt: purchase_id not set, using picking_ids fallback")
                items = self.env['baby.list.item'].search([
                    ('purchase_order_id.picking_ids', 'in', picking.id),
                    ('product_id', '=', move.product_id.id),
                    ('picking_pending_id', '=', False),
                ])

            _logger.info("[MOOMBS] _handle_vendor_receipt: Found %s items for product %s", 
                        len(items), move.product_id.name if move.product_id else 'None')

            for item in items:
                _logger.info("[MOOMBS] _handle_vendor_receipt: Processing item ID=%s, current picking_in_id=%s, current state=%s", 
                            item.id, 
                            item.picking_in_id.id if item.picking_in_id else 'None',
                            item.state)
                
                # CRITICAL: Ensure picking_in_id is linked (should already be linked in create(), but double-check)
                if not item.picking_in_id or item.picking_in_id.id != picking.id:
                    item.write({'picking_in_id': picking.id})
                    _logger.info("[MOOMBS] _handle_vendor_receipt: Linked picking_in_id=%s to item ID=%s (receipt validated)", 
                                picking.id, item.id)
                
                # CRITICAL: Force state recomputation after write
                # This should now show 'received' status (Priority 5: picking_in_id.state == 'done')
                item._compute_state()
                _logger.info("[MOOMBS] _handle_vendor_receipt: State recomputed for item ID=%s, new state=%s (receipt validated)", 
                            item.id, item.state)
                
                # Verify state is 'received' (not 'delivered')
                if item.state == 'delivered':
                    _logger.error("[MOOMBS] _handle_vendor_receipt: ERROR - Item ID=%s state is 'delivered' but should be 'received'! "
                                "picking_out_id=%s, picking_in_id=%s, picking_in_id.state=%s", 
                                item.id,
                                item.picking_out_id.id if item.picking_out_id else 'None',
                                item.picking_in_id.id if item.picking_in_id else 'None',
                                item.picking_in_id.state if item.picking_in_id else 'N/A')
                elif item.state == 'received':
                    _logger.info("[MOOMBS] _handle_vendor_receipt: ✓ Item ID=%s state is correctly 'received'", item.id)
                else:
                    _logger.warning("[MOOMBS] _handle_vendor_receipt: Item ID=%s state is '%s' (expected 'received')", 
                                  item.id, item.state)

                # Create Internal Transfer to Pending
                self._create_pending_transfer(item, move.product_id, picking)

    def _create_pending_transfer(self, item, product, source_picking):
        """Create internal transfer to Pending Delivery location."""
        stock_location = self.env.ref('stock.stock_location_stock')
        pending_location = self.env.ref('moombs_list.stock_location_pending_delivery')
        picking_type = self.env.ref('moombs_list.picking_type_internal_pending')

        # Set partner_id from baby list beneficiary
        partner_id = item.list_id.partner_id.id if item.list_id and item.list_id.partner_id else False

        int_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': stock_location.id,
            'location_dest_id': pending_location.id,
            'origin': _('MOOMBS: %s') % item.list_id.name,
            'baby_list_item_id': item.id,
            'partner_id': partner_id,  # Set contact from beneficiary
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom': product.uom_id.id,
                'location_id': stock_location.id,
                'location_dest_id': pending_location.id,
                'partner_id': partner_id,  # Set contact on move as well
            })],
        })
        
        if partner_id:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info("[MOOMBS] _create_pending_transfer: Set partner_id=%s (beneficiary) on internal transfer %s", 
                        partner_id, int_picking.name)

        int_picking.action_confirm()
        int_picking.action_assign()

        item.write({'picking_pending_id': int_picking.id})
        # CRITICAL: Force state recomputation after write
        item._compute_state()

    def _handle_internal_transfer(self, picking):
        """Handle internal transfer validation (to Pending Delivery).

        State is computed from picking_pending_id.state:
        - assigned → 'reserved'
        - done → 'pending'
        
        CRITICAL: After validating internal transfer, if SO exists and stock is in Pending Delivery,
        check if delivery exists and link it, or create it if needed.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        if not picking.baby_list_item_id:
            return

        # Just ensure the link exists (state computed automatically)
        item = picking.baby_list_item_id
        if not item.picking_pending_id:
            item.write({'picking_pending_id': picking.id})
            # CRITICAL: Force state recomputation after write
            item._compute_state()

        # When transfer is complete
        if picking.state == 'done':
            # CRITICAL: Force state recomputation when picking state changes to done
            item._compute_state()
            
            # CRITICAL: After internal transfer is validated, check if delivery exists and link it
            # This ensures "delivery created" status shows when stock is ready for delivery
            # KEY INSIGHT: When user saves delivery (e.g., updates notes), write() method triggers
            # _link_baby_list_item() which links delivery and sets picking_out_id, updating state.
            # We need to trigger the same flow here.
            if item.sale_order_id and not item.picking_out_id:
                _logger.info("[MOOMBS] _handle_internal_transfer: Stock in Pending Delivery, checking for delivery for item ID=%s, SO=%s", 
                            item.id, item.sale_order_id.name)
                
                # CRITICAL: Use multiple search methods (same as _link_baby_list_item) because delivery
                # might have sale_id=None but origin=S00144. We need fallback methods!
                # Invalidate cache to ensure fresh data
                self.env['stock.picking'].invalidate_model(['sale_id', 'picking_type_code', 'origin'])
                delivery = None
                
                # Method 1: Search by sale_id (most reliable if set)
                delivery = self.env['stock.picking'].search([
                    ('sale_id', '=', item.sale_order_id.id),
                    ('picking_type_code', '=', 'outgoing'),
                    ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
                ], limit=1, order='create_date desc')
                
                if delivery:
                    _logger.info("[MOOMBS] _handle_internal_transfer: Found delivery %s via sale_id=%s", 
                                delivery.name, item.sale_order_id.id)
                else:
                    # Method 2: Search by origin (SO name) - CRITICAL FALLBACK
                    # Delivery might have origin=S00144 but sale_id=None
                    so_name = item.sale_order_id.name
                    delivery = self.env['stock.picking'].search([
                        ('origin', '=', so_name),
                        ('picking_type_code', '=', 'outgoing'),
                        ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
                    ], limit=1, order='create_date desc')
                    
                    if delivery:
                        _logger.info("[MOOMBS] _handle_internal_transfer: Found delivery %s via origin=%s (sale_id was None)", 
                                    delivery.name, so_name)
                    else:
                        # Method 3: Search by product + partner (last resort)
                        if item.product_id and item.list_id.partner_id:
                            delivery = self.env['stock.picking'].search([
                                ('picking_type_code', '=', 'outgoing'),
                                ('move_ids.product_id', '=', item.product_id.id),
                                ('partner_id', '=', item.list_id.partner_id.id),
                                ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
                            ], limit=1, order='create_date desc')
                            
                            if delivery:
                                _logger.info("[MOOMBS] _handle_internal_transfer: Found delivery %s via product+partner (last resort)", 
                                            delivery.name)
                
                if delivery:
                    _logger.info("[MOOMBS] _handle_internal_transfer: Found existing delivery %s (ID=%s) for SO %s", 
                                delivery.name, delivery.id, item.sale_order_id.name)
                    _logger.info("[MOOMBS] _handle_internal_transfer: Delivery state BEFORE write: %s, baby_list_item_id=%s, partner_id=%s", 
                                delivery.state, 
                                delivery.baby_list_item_id.id if delivery.baby_list_item_id else 'None',
                                delivery.partner_id.id if delivery.partner_id else 'None')
                    _logger.info("[MOOMBS] _handle_internal_transfer: Item state BEFORE write: picking_out_id=%s, state=%s", 
                                item.picking_out_id.id if item.picking_out_id else 'None',
                                item.state)
                    
                    # CRITICAL: Trigger write() on delivery (even with empty vals) to trigger the same
                    # linking logic that happens when user saves delivery. This ensures:
                    # 1. _link_baby_list_item() is called
                    # 2. _link_to_item() is called
                    # 3. picking_out_id is set on item
                    # 4. State is recomputed
                    # This is the SAME flow that happens when user updates notes and saves!
                    _logger.info("[MOOMBS] _handle_internal_transfer: Triggering delivery.write({}) to activate linking flow...")
                    delivery.write({})  # Empty write triggers the linking logic in write() method
                    
                    # Refresh delivery and item to get updated values
                    delivery.invalidate_recordset(['baby_list_item_id', 'partner_id'])
                    item.invalidate_recordset(['picking_out_id', 'state'])
                    
                    _logger.info("[MOOMBS] _handle_internal_transfer: Delivery state AFTER write: %s, baby_list_item_id=%s, partner_id=%s", 
                                delivery.state, 
                                delivery.baby_list_item_id.id if delivery.baby_list_item_id else 'None',
                                delivery.partner_id.id if delivery.partner_id else 'None')
                    _logger.info("[MOOMBS] _handle_internal_transfer: Item state AFTER write: picking_out_id=%s, state=%s", 
                                item.picking_out_id.id if item.picking_out_id else 'None',
                                item.state)
                    
                    if item.picking_out_id and item.picking_out_id.id == delivery.id:
                        _logger.info("[MOOMBS] _handle_internal_transfer: ✓ SUCCESS - Delivery %s linked to item %s, state=%s", 
                                    delivery.name, item.id, item.state)
                    else:
                        _logger.warning("[MOOMBS] _handle_internal_transfer: ✗ FAILED - Delivery %s NOT linked to item %s (picking_out_id=%s)", 
                                      delivery.name, item.id, 
                                      item.picking_out_id.id if item.picking_out_id else 'None')
                else:
                    _logger.info("[MOOMBS] _handle_internal_transfer: No delivery found for SO %s. Delivery will be created when SO is confirmed or stock is available.", 
                                item.sale_order_id.name)

    def _handle_customer_delivery(self, picking):
        """Handle outgoing delivery validation.
        
        SIMPLE APPROACH:
        1. Find item where picking_out_id = this picking (already linked)
        2. Set partner_id from item.list_id.partner_id (beneficiary)
        3. Recompute state (out_created if not done, delivered if done)
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("[MOOMBS] _handle_customer_delivery: Starting for picking %s (ID=%s, state=%s)", 
                    picking.name, picking.id, picking.state)
        
        # SIMPLE: Find item where picking_out_id = this picking
        # This is the most reliable way since the transfer is already linked
        item = self.env['baby.list.item'].search([
            ('picking_out_id', '=', picking.id),
        ], limit=1)
        
        if not item:
            # Fallback: Try via baby_list_item_id on picking
            if picking.baby_list_item_id:
                item = picking.baby_list_item_id
                _logger.info("[MOOMBS] _handle_customer_delivery: Found item via baby_list_item_id=%s", item.id)
            else:
                # Last resort: Try to link using _link_baby_list_item
                _logger.info("[MOOMBS] _handle_customer_delivery: No item found via picking_out_id, trying to link")
                picking._link_baby_list_item()
                if picking.baby_list_item_id:
                    item = picking.baby_list_item_id
                    # Ensure picking_out_id is linked
                    if not item.picking_out_id or item.picking_out_id.id != picking.id:
                        item.write({'picking_out_id': picking.id})
                        _logger.info("[MOOMBS] _handle_customer_delivery: Linked picking_out_id=%s to item %s", 
                                    picking.id, item.id)
        
        if item:
            _logger.info("[MOOMBS] _handle_customer_delivery: Processing item ID=%s (list_id=%s, partner_id=%s)", 
                        item.id, item.list_id.id if item.list_id else 'None',
                        item.list_id.partner_id.id if item.list_id and item.list_id.partner_id else 'None')
            
            # CRITICAL: Set partner_id from beneficiary (gift list partner)
            if item.list_id and item.list_id.partner_id:
                # Set on picking
                if not picking.partner_id or picking.partner_id.id != item.list_id.partner_id.id:
                    picking.write({'partner_id': item.list_id.partner_id.id})
                    _logger.info("[MOOMBS] _handle_customer_delivery: Set partner_id=%s (beneficiary) on picking", 
                                item.list_id.partner_id.id)
                
                # Set on all moves (important for delivery documents)
                for move in picking.move_ids:
                    if not move.partner_id or move.partner_id.id != item.list_id.partner_id.id:
                        move.write({'partner_id': item.list_id.partner_id.id})
                        _logger.info("[MOOMBS] _handle_customer_delivery: Set partner_id=%s on move %s", 
                                    item.list_id.partner_id.id, move.id)
            else:
                _logger.warning("[MOOMBS] _handle_customer_delivery: No partner_id on baby list (list_id=%s)", 
                               item.list_id.id if item.list_id else 'None')
            
            # Ensure picking_out_id is linked
            if not item.picking_out_id or item.picking_out_id.id != picking.id:
                item.write({'picking_out_id': picking.id})
                _logger.info("[MOOMBS] _handle_customer_delivery: Linked picking_out_id=%s to item %s", 
                            picking.id, item.id)
            
            # Link baby_list_item_id to picking for future reference
            if not picking.baby_list_item_id or picking.baby_list_item_id.id != item.id:
                picking.write({'baby_list_item_id': item.id})
                _logger.info("[MOOMBS] _handle_customer_delivery: Linked baby_list_item_id=%s to picking", item.id)
            
            # CRITICAL: Get fresh picking state
            fresh_picking = self.env['stock.picking'].browse(picking.id)
            _logger.info("[MOOMBS] _handle_customer_delivery: Fresh picking state=%s", fresh_picking.state)
            
            # CRITICAL: For stored computed fields, we need to write to a dependency to trigger storage
            # Following the same pattern as purchase_order.py - write to dependency field to trigger recomputation and storage
            # The picking_out_id is already linked, but we need to ensure state is recomputed and stored
            # Invalidate cache first to ensure fresh read of picking state
            item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
            if item.picking_out_id:
                item.picking_out_id.invalidate_recordset(['state'])
            
            # CRITICAL: Write to dependency field to trigger automatic recomputation and storage
            # This ensures the computed state is actually stored in the database
            item.write({'picking_out_id': item.picking_out_id.id})
            
            expected_state = 'delivered' if fresh_picking.state == 'done' else 'out_created'
            _logger.info("[MOOMBS] _handle_customer_delivery: State updated, item state=%s (expected: %s)", 
                        item.state, expected_state)
        else:
            _logger.warning("[MOOMBS] _handle_customer_delivery: Could not find item for picking %s", picking.name)
