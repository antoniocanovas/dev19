# -*- coding: utf-8 -*-
"""
pos.order Extension
===================

Extends pos.order for baby list integration:
- paid_by_partner_id: Track who paid (for fiscal ticket)
- ewallet_beneficiary_id: Track wallet owner
- baby_list_item_ids: Link to baby list items being paid

Epic 5: Down payment (25%) triggers stock check and INT/PO creation.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    paid_by_partner_id = fields.Many2one('res.partner',
        string='Paid By',
        index=False,
        help="The customer who paid for this transaction. "
             "Used for fiscal ticket when different from eWallet beneficiary."
    )
    ewallet_beneficiary_id = fields.Many2one('res.partner',
        string='eWallet Beneficiary',
        index=False,
        help="The original eWallet holder who receives the balance. "
             "Stored for audit trail when fiscal customer differs."
    )
    baby_list_item_ids = fields.Many2many(
        'baby.list.item',
        string='Gift List Items',
        help='Baby list items paid in this POS order',
    )
    
    # Two-Order Flow: Link between top-up and settlement orders
    topup_order_id = fields.Many2one(
        'pos.order',
        string='Top-Up Order',
        index=True,
        help="The wallet top-up order that funded this settlement order. "
             "Set on the settlement order to link back to the top-up."
    )
    settlement_order_id = fields.Many2one(
        'pos.order',
        string='Settlement Order',
        index=True,
        help="The settlement order that was paid using this top-up. "
             "Set on the top-up order to link to the settlement."
    )
    is_gift_topup_order = fields.Boolean(
        string='Is Gift Top-Up',
        default=False,
        help="True if this order is a wallet top-up for a Gift List payment."
    )

    # NOTE: _load_pos_data_fields disabled - causes POS to hang during data sync
    # The receipt template uses frontend data via setTopupOrderInfo() instead
    # This avoids loading Many2one relations which triggers excessive data loading

    def _process_order(self, order, existing_order):
        """
        Override to handle paid_by_partner_id from POS frontend.

        When a different paying customer is specified:
        1. Extract paid_by_partner_id and ewallet_beneficiary_id from order data
        2. Use ewallet_beneficiary_id (sent by frontend) as the true beneficiary
        3. Temporarily set partner_id to beneficiary for wallet credit
        4. Restore partner_id to payer AFTER processing for fiscal ticket
        """
        try:
            # Extract paid_by_partner_id from order data
            data = order.get('data', {})
            paid_by_id = data.pop('paid_by_partner_id', False)

            # Also check if it's in the order dict directly
            if not paid_by_id:
                paid_by_id = order.pop('paid_by_partner_id', False)

            # CRITICAL: Use ewallet_beneficiary_id from frontend (explicitly sent)
            # This is the original partner (Tia) who should receive wallet credit
            beneficiary_id = data.pop('ewallet_beneficiary_id', False)
            
            # Fallback: if frontend didn't send it, use partner_id from order
            if not beneficiary_id:
                beneficiary_id = data.get('partner_id') or order.get('partner_id')

            # VALIDATION: Validate beneficiary exists (only if provided)
            if beneficiary_id:
                try:
                    beneficiary = self.env['res.partner'].browse(beneficiary_id)
                    if not beneficiary.exists():
                        _logger.warning("[MOOMBS] Invalid beneficiary partner ID: %s", beneficiary_id)
                        beneficiary_id = False
                except Exception as e:
                    _logger.warning("[MOOMBS] Error validating beneficiary: %s", str(e))
                    beneficiary_id = False
            
            # VALIDATION: Check if order contains eWallet top-up products
            # Only validate wallet if there are eWallet top-up products in the order
            order_lines = data.get('lines', []) or order.get('lines', [])
            has_ewallet_topup = False
            
            if order_lines and beneficiary_id:
                try:
                    # Get all eWallet programs (handle multiple programs)
                    ewallet_programs = self.env['loyalty.program'].search([
                        ('program_type', '=', 'ewallet'),
                        ('trigger', '=', 'auto'),
                    ])
                    
                    if ewallet_programs:
                        # Check if any line is an eWallet top-up product
                        for line in order_lines:
                            # Line format can be [0, 0, {...}] or {...}
                            line_data = line[2] if isinstance(line, list) and len(line) > 2 else line
                            product_id = line_data.get('product_id') if isinstance(line_data, dict) else False
                            
                            if product_id:
                                # Check if product is linked to any eWallet program through rewards
                                product = self.env['product.product'].browse(product_id)
                                if product.exists():
                                    # Check if product is in any eWallet program's reward products
                                    # eWallet top-up products are identified via reward_ids
                                    for program in ewallet_programs:
                                        if any(r.reward_type == 'product' and r.reward_product_id == product 
                                               for r in program.reward_ids):
                                            has_ewallet_topup = True
                                            break
                                    
                                    # Fallback: Check product name for eWallet indicators
                                    if not has_ewallet_topup:
                                        product_name = (product.name or '').lower()
                                        if any(keyword in product_name for keyword in ['wallet', 'ewallet', 'top-up', 'topup']):
                                            has_ewallet_topup = True
                                    
                                    if has_ewallet_topup:
                                        break
                        
                        # If eWallet top-up found, validate beneficiary has wallet for at least one program
                        if has_ewallet_topup:
                            beneficiary = self.env['res.partner'].browse(beneficiary_id)
                            if not beneficiary.exists():
                                _logger.warning("[MOOMBS] Beneficiary partner does not exist: %s", beneficiary_id)
                                has_ewallet_topup = False
                            else:
                                # Check if beneficiary has wallet for any eWallet program
                                wallet = self.env['loyalty.card'].search([
                                    ('partner_id', '=', beneficiary_id),
                                    ('program_id', 'in', ewallet_programs.ids),
                                ], limit=1)
                                
                                if not wallet:
                                    _logger.warning("[MOOMBS] Customer %s does not have an eWallet", beneficiary.name)
                                    has_ewallet_topup = False
                except Exception as e:
                    _logger.warning("[MOOMBS] Error validating eWallet products: %s", str(e))
                    has_ewallet_topup = False

            # If paid_by differs from beneficiary, we need to ensure wallet credit goes to beneficiary
            # Temporarily set partner_id to beneficiary in order data for wallet credit processing
            if paid_by_id and paid_by_id != beneficiary_id:
                # Temporarily set partner_id to beneficiary for wallet credit
                # This ensures Odoo's loyalty system credits the correct wallet
                if 'partner_id' in data:
                    data['partner_id'] = beneficiary_id
                if 'partner_id' in order:
                    order['partner_id'] = beneficiary_id

            # Create order with standard flow (partner_id = beneficiary for wallet credit)
            # Odoo's loyalty system will use partner_id to determine which wallet to credit
            order_id = super()._process_order(order, existing_order)

            # Fetch the created order object
            pos_order = self.browse(order_id)

            # Update order with correct fields
            if paid_by_id and paid_by_id != beneficiary_id:
                update_vals = {
                    'paid_by_partner_id': paid_by_id,
                    # KEEP partner_id as beneficiary (Tia) for bill display
                    # Payer info is shown separately via paid_by_partner_id field
                    'partner_id': beneficiary_id,
                }
                pos_order.write(update_vals)
                _logger.info("[MOOMBS] Order %s: Set paid_by_partner_id=%s, partner_id=%s", 
                            order_id, paid_by_id, beneficiary_id)

            return order_id
        except Exception as e:
            _logger.error("[MOOMBS] Error in _process_order: %s", str(e), exc_info=True)
            # If our custom logic fails, fall back to parent implementation
            return super()._process_order(order, existing_order)

    def _is_gift_list_order(self, order):
        """Check if POS order is from Gift List (has Sale Order linked).
        
        Args:
            order: pos.order record
            
        Returns:
            tuple: (is_gift_list, sale_orders) - Boolean and recordset of sale orders
        """
        sale_orders = self.env['sale.order']
        
        # Method 1: Check sale_order_ids (if pos_sale module links it)
        if hasattr(order, 'sale_order_ids') and order.sale_order_ids:
            sale_orders = order.sale_order_ids
            _logger.info("[MOOMBS] Gift List check: Found SOs via sale_order_ids: %s", 
                        ', '.join([so.name for so in sale_orders]))
        
        # Method 2: Check sale_order_origin_id from lines (for downpayments)
        if not sale_orders and order.lines:
            for pos_line in order.lines:
                if hasattr(pos_line, 'sale_order_origin_id') and pos_line.sale_order_origin_id:
                    so_id = pos_line.sale_order_origin_id
                    if isinstance(so_id, (int,)):
                        so = self.env['sale.order'].browse(so_id)
                    else:
                        so = so_id
                    if so.exists() and so not in sale_orders:
                        sale_orders |= so
                        _logger.info("[MOOMBS] Gift List check: Found SO via sale_order_origin_id: %s", so.name)
        
        # Method 3: Check sale_order_line_id from lines
        if not sale_orders and order.lines:
            for pos_line in order.lines:
                if hasattr(pos_line, 'sale_order_line_id') and pos_line.sale_order_line_id:
                    so = pos_line.sale_order_line_id.order_id
                    if so.exists() and so not in sale_orders:
                        sale_orders |= so
                        _logger.info("[MOOMBS] Gift List check: Found SO via sale_order_line_id: %s", so.name)
        
        # Check if any SO is from Gift List
        is_gift_list = False
        if sale_orders:
            # Check if any SO has baby_list_id (Gift List)
            for so in sale_orders:
                if hasattr(so, 'baby_list_id') and so.baby_list_id:
                    is_gift_list = True
                    _logger.info("[MOOMBS] Gift List check: SO %s is from Gift List %s", 
                                so.name, so.baby_list_id.name)
                    break
        
        return is_gift_list, sale_orders

    def _process_wallet_intermediary(self, order, sale_orders):
        """Process wallet intermediary flow for Gift List orders using TWO-ORDER approach.
        
        NEW FLOW (Two-Order Approach):
        1. Get original customer (beneficiary) from Sale Order
        2. Validate original customer has wallet
        3. Create Order 1: Top-Up Order (credits beneficiary's wallet)
        4. Modify Order 2 (current order): Settlement Order (pays with wallet)
        5. Link both orders together
        
        Benefits:
        - Clean audit trail with two distinct orders
        - Proper accounting entries for both transactions
        - Top-up and settlement are separate, traceable operations
        
        Args:
            order: pos.order record (becomes the settlement order)
            sale_orders: sale.order recordset
            
        Returns:
            dict: Contains topup_order_id for receipt display
        """
        _logger.info("[MOOMBS] Two-Order Flow: Processing for order %s", order.name)
        
        # Step 1: Get original customer (beneficiary) from Sale Order
        if not sale_orders:
            _logger.warning("[MOOMBS] Two-Order Flow: No sale orders found, skipping")
            return {}
        
        # Use first sale order's customer as original customer (beneficiary)
        original_customer = sale_orders[0].partner_id
        if not original_customer:
            _logger.warning("[MOOMBS] Two-Order Flow: No partner on SO, skipping")
            return {}
        
        _logger.info("[MOOMBS] Two-Order Flow: Original customer (beneficiary): %s (ID: %s)", 
                    original_customer.name, original_customer.id)
        
        # Step 2: Determine payer (paid_by)
        # If order.partner_id differs from original_customer, that's the payer
        # Otherwise, check paid_by_partner_id
        payer = None
        if order.paid_by_partner_id and order.paid_by_partner_id.id != original_customer.id:
            payer = order.paid_by_partner_id
        elif order.partner_id and order.partner_id.id != original_customer.id:
            payer = order.partner_id
        
        if not payer:
            _logger.info("[MOOMBS] Two-Order Flow: Same customer paying, no intermediary needed")
            return {}
        
        _logger.info("[MOOMBS] Two-Order Flow: Payer: %s (ID: %s)", payer.name, payer.id)
        
        # Step 3: Validate original customer has wallet
        ewallet_programs = self.env['loyalty.program'].search([
            ('program_type', '=', 'ewallet'),
            ('trigger', '=', 'auto'),
        ])
        
        if not ewallet_programs:
            raise UserError(_(
                "No eWallet program found. Please configure an eWallet program first."
            ))
        
        wallet = self.env['loyalty.card'].search([
            ('partner_id', '=', original_customer.id),
            ('program_id', 'in', ewallet_programs.ids),
        ], limit=1)
        
        if not wallet:
            raise UserError(_(
                "Customer '%s' must have a wallet to use this payment method. "
                "Please create a wallet for this customer first."
            ) % original_customer.name)
        
        _logger.info("[MOOMBS] Two-Order Flow: Found wallet %s for customer %s (balance: %s)", 
                    wallet.code, original_customer.name, wallet.points)
        
        # Step 4: Calculate total payment amount from existing payments
        existing_payments = order.payment_ids
        total_amount = sum(existing_payments.mapped('amount'))
        
        if total_amount <= 0:
            _logger.warning("[MOOMBS] Two-Order Flow: No payment amount, skipping")
            return {}
        
        _logger.info("[MOOMBS] Two-Order Flow: Total payment amount: %s", total_amount)
        
        # Step 4b: Calculate net amount excluding down payment lines
        # Down payment lines have negative amounts and should not be included in wallet credit/debit
        # We keep them in the order for history, but adjust the wallet transaction amount
        downpayment_lines = order.lines.filtered(lambda l: hasattr(l, 'is_downpayment') and l.is_downpayment)
        downpayment_total = 0.0
        
        if downpayment_lines:
            # Down payment lines are negative, so we subtract them (which adds to net amount)
            downpayment_total = sum(downpayment_lines.mapped('price_subtotal_incl'))
            _logger.info("[MOOMBS] Two-Order Flow: Found %d down payment line(s) with total: %s", 
                        len(downpayment_lines), downpayment_total)
        
        # Net amount = payment amount - down payment amount (down payment is negative, so this subtracts the negative)
        # Example: payment=$100, downpayment=-$25 → net=$100-(-$25)=$125? NO!
        # Actually: payment=$100 is what customer paid, downpayment=-$25 is already on order
        # So net wallet transaction should be: payment - abs(downpayment) = $100 - $25 = $75
        net_amount = total_amount
        if downpayment_total < 0:  # Down payment lines are negative
            net_amount = total_amount + downpayment_total  # Adding negative = subtracting
            _logger.info("[MOOMBS] Two-Order Flow: Adjusted net amount: %s (payment: %s, downpayment: %s)", 
                        net_amount, total_amount, downpayment_total)
        
        if net_amount <= 0:
            _logger.warning("[MOOMBS] Two-Order Flow: Net amount is zero or negative after down payment adjustment, skipping")
            return {}
        
        # Step 5: Create Order 1 - Top-Up Order (use net_amount)
        topup_order = self._create_gift_topup_order(
            beneficiary=original_customer,
            payer=payer,
            amount=net_amount,  # Use net amount excluding down payments
            wallet=wallet,
            ewallet_programs=ewallet_programs,
            original_payments=existing_payments,
            settlement_order=order,
            sale_orders=sale_orders,
        )
        
        _logger.info("[MOOMBS] Two-Order Flow: Created Top-Up Order %s (ID: %s) with amount %s", 
                    topup_order.name, topup_order.id, net_amount)
        
        # Step 6: Modify current order to be Settlement Order (paid with wallet, use net_amount)
        self._convert_to_wallet_settlement(
            order=order,
            wallet=wallet,
            total_amount=net_amount,  # Use net amount excluding down payments
            original_customer=original_customer,
            topup_order=topup_order,
        )
        
        _logger.info("[MOOMBS] Two-Order Flow: Converted order %s to wallet settlement", order.name)
        
        return {
            'topup_order_id': topup_order.id,
            'topup_order_name': topup_order.name,
        }

    def _create_gift_topup_order(self, beneficiary, payer, amount, wallet, ewallet_programs, 
                                  original_payments, settlement_order, sale_orders):
        """Create a wallet top-up order for Gift List payment.
        
        This order:
        - Has the beneficiary as partner_id (wallet owner)
        - Has the payer as paid_by_partner_id (for fiscal ticket)
        - Contains the eWallet top-up product
        - Uses the original payment methods (cash/card from payer)
        - Credits the beneficiary's wallet
        
        Args:
            beneficiary: res.partner - the wallet owner
            payer: res.partner - the person paying
            amount: float - the top-up amount
            wallet: loyalty.card - the beneficiary's wallet
            ewallet_programs: loyalty.program recordset
            original_payments: pos.payment recordset - payments from payer
            settlement_order: pos.order - the order being settled
            sale_orders: sale.order recordset - linked sale orders
            
        Returns:
            pos.order: The created top-up order
        """
        _logger.info("[MOOMBS] Creating Top-Up Order: Beneficiary=%s, Payer=%s, Amount=%s", 
                    beneficiary.name, payer.name, amount)
        
        # Get the eWallet program's trigger product (top-up product)
        program = ewallet_programs[0]
        topup_product = None
        
        # Method 1: Get trigger_product_ids from program
        if hasattr(program, 'trigger_product_ids') and program.trigger_product_ids:
            topup_product = program.trigger_product_ids[0]
            _logger.info("[MOOMBS] Top-Up Order: Using trigger product: %s", topup_product.name)
        
        # Method 2: Search for eWallet top-up product by name
        if not topup_product:
            topup_product = self.env['product.product'].search([
                '|', '|', '|',
                ('name', 'ilike', 'ewallet'),
                ('name', 'ilike', 'e-wallet'),
                ('name', 'ilike', 'wallet top'),
                ('name', 'ilike', 'monedero'),
            ], limit=1)
            if topup_product:
                _logger.info("[MOOMBS] Top-Up Order: Found top-up product by name: %s", topup_product.name)
        
        # Method 3: Create a generic top-up product if none exists
        if not topup_product:
            topup_product = self.env['product.product'].search([
                ('name', '=', 'Gift List Top-Up'),
                ('type', '=', 'service'),
            ], limit=1)
            
            if not topup_product:
                topup_product = self.env['product.product'].create({
                    'name': 'Gift List Top-Up',
                    'type': 'service',
                    'list_price': 0,
                    'available_in_pos': True,
                    'taxes_id': [(5, 0, 0)],  # No taxes on eWallet top-up
                })
                _logger.info("[MOOMBS] Top-Up Order: Created top-up product: %s (no taxes)", topup_product.id)
        
        # Get POS session and config from settlement order
        session = settlement_order.session_id
        config = session.config_id
        
        # Create the top-up order with required fields
        topup_order_vals = {
            'session_id': session.id,
            'config_id': config.id,
            'partner_id': beneficiary.id,  # Wallet owner
            'paid_by_partner_id': payer.id,  # Fiscal ticket shows payer
            'ewallet_beneficiary_id': beneficiary.id,
            'is_gift_topup_order': True,
            'settlement_order_id': settlement_order.id,  # Link to settlement
            'pricelist_id': settlement_order.pricelist_id.id,
            'fiscal_position_id': settlement_order.fiscal_position_id.id if settlement_order.fiscal_position_id else False,
            'company_id': settlement_order.company_id.id,
            'user_id': settlement_order.user_id.id,
            'to_invoice': False,  # Prevent invoice generation for top-up orders
            # Set amount fields to 0 initially (will be updated when line is created)
            'amount_total': 0,
            'amount_tax': 0,
            'amount_paid': 0,
            'amount_return': 0,
        }
        
        topup_order = self.create(topup_order_vals)
        _logger.info("[MOOMBS] Top-Up Order: Created order %s", topup_order.name)
        
        # Create the top-up line
        line_vals = {
            'order_id': topup_order.id,
            'product_id': topup_product.id,
            'qty': 1,
            'price_unit': amount,
            'price_subtotal': amount,
            'price_subtotal_incl': amount,
            'discount': 0,
            'full_product_name': _('Gift List Top-Up for %s') % beneficiary.name,
        }
        
        self.env['pos.order.line'].create(line_vals)
        
        # Update order totals after line creation
        topup_order.write({
            'amount_total': amount,
            'amount_tax': 0,  # No tax on top-up
            'amount_paid': amount,  # Will be paid immediately
        })
        _logger.info("[MOOMBS] Top-Up Order: Created line with amount %s", amount)
        
        # Copy payment methods from original order to top-up order
        for payment in original_payments:
            payment_vals = {
                'pos_order_id': topup_order.id,
                'payment_method_id': payment.payment_method_id.id,
                'amount': payment.amount,
                'payment_date': payment.payment_date,
                'card_type': payment.card_type if hasattr(payment, 'card_type') else False,
                'cardholder_name': payment.cardholder_name if hasattr(payment, 'cardholder_name') else False,
                'transaction_id': payment.transaction_id if hasattr(payment, 'transaction_id') else False,
            }
            self.env['pos.payment'].create(payment_vals)
        
        _logger.info("[MOOMBS] Top-Up Order: Copied %d payment(s) from original order", len(original_payments))
        
        # Credit the wallet
        old_balance = wallet.points
        wallet.points += amount
        
        # Create loyalty history entry for the top-up
        self.env['loyalty.history'].create({
            'card_id': wallet.id,
            'order_model': 'pos.order',
            'order_id': topup_order.id,
            'description': _('Gift List Top-Up from %s') % payer.name,
            'issued': amount,
            'used': 0,
        })
        
        _logger.info("[MOOMBS] Top-Up Order: Credited wallet %s. Old: %s, New: %s", 
                    wallet.code, old_balance, wallet.points)
        
        # NOTE: Do NOT call action_pos_order_paid() here!
        # The top-up order will be marked as paid when super().action_pos_order_paid() is called
        # in action_pos_order_paid() after the settlement order conversion is complete.
        # Calling it here would interfere with the settlement order processing.
        
        _logger.info("[MOOMBS] Top-Up Order: Order %s created (will be marked as paid later)", topup_order.name)
        
        return topup_order

    def _convert_to_wallet_settlement(self, order, wallet, total_amount, original_customer, topup_order):
        """Convert the current order to a wallet settlement order.
        
        This modifies the order to:
        - Remove original payment methods
        - Add wallet payment (debit from beneficiary's wallet)
        - Set partner_id to beneficiary
        - Link to top-up order
        
        Args:
            order: pos.order - the order to convert
            wallet: loyalty.card - the beneficiary's wallet
            total_amount: float - the amount to debit
            original_customer: res.partner - the beneficiary
            topup_order: pos.order - the linked top-up order
        """
        _logger.info("[MOOMBS] Settlement: Converting order %s to wallet payment", order.name)
        _logger.info("[MOOMBS] Settlement: Order ID=%s, Wallet=%s, Amount=%s", 
                    order.id, wallet.code, total_amount)
        
        # Delete original payment lines (they're now on the top-up order)
        _logger.info("[MOOMBS] Settlement: Deleting %d payment lines", len(order.payment_ids))
        order.payment_ids.unlink()
        _logger.info("[MOOMBS] Settlement: Deleted original payment lines")
        
        # Add a negative order line with eWallet discount product to represent the wallet debit
        # This is the standard Odoo approach for eWallet settlements
        _logger.info("[MOOMBS] Settlement: Adding negative eWallet line for amount %s", total_amount)
        
        # Get the eWallet program's discount product (payment_program_discount_product_id)
        ewallet_programs = self.env['loyalty.program'].search([
            ('program_type', '=', 'ewallet'),
            ('trigger', '=', 'auto'),
        ])
        
        ewallet_product = None
        if ewallet_programs and ewallet_programs[0].payment_program_discount_product_id:
            ewallet_product = ewallet_programs[0].payment_program_discount_product_id
            _logger.info("[MOOMBS] Settlement: Using eWallet discount product: %s", ewallet_product.name)
        
        if not ewallet_product:
            # Fallback: search for eWallet product by name
            _logger.info("[MOOMBS] Settlement: No discount product found, searching for eWallet product by name")
            ewallet_product = self.env['product.product'].search([
                '|', '|', '|',
                ('name', 'ilike', 'ewallet'),
                ('name', 'ilike', 'e-wallet'),
                ('name', 'ilike', 'wallet'),
                ('name', 'ilike', 'monedero'),
            ], limit=1)
        
        if ewallet_product:
            # Create eWallet debit line - taxes will be applied based on product configuration
            ewallet_line = self.env['pos.order.line'].create({
                'order_id': order.id,
                'product_id': ewallet_product.id,
                'qty': -1,  # Negative quantity
                'price_unit': total_amount,
                'price_subtotal': -total_amount,  # Negative amount
                'price_subtotal_incl': -total_amount,
                'discount': 0,
                'full_product_name': _('eWallet Settlement for %s') % original_customer.name,
            })
            _logger.info("[MOOMBS] Settlement: Added negative eWallet line with amount %s", total_amount)
            
            # Recalculate order totals after adding eWallet line
            all_lines = order.lines
            amount_total = sum(all_lines.mapped('price_subtotal_incl'))
            amount_tax = sum(all_lines.mapped(lambda l: l.price_subtotal_incl - l.price_subtotal))
            
            _logger.info("[MOOMBS] Settlement: Recalculated totals - amount_total=%s, amount_tax=%s", 
                        amount_total, amount_tax)
            
            order.write({
                'amount_total': amount_total,
                'amount_tax': amount_tax,
                'amount_paid': 0.0,  # Settlement order paid via wallet, no cash payment
                'amount_return': 0.0,
            })
        else:
            _logger.warning("[MOOMBS] Settlement: No eWallet product found for settlement line")
        
        # Debit the wallet
        _logger.info("[MOOMBS] Settlement: Debiting wallet - Old balance: %s", wallet.points)
        old_balance = wallet.points
        wallet.points -= total_amount
        _logger.info("[MOOMBS] Settlement: Wallet debited - New balance: %s", wallet.points)
        
        # Create loyalty history entry for the debit
        _logger.info("[MOOMBS] Settlement: Creating loyalty history entry")
        self.env['loyalty.history'].create({
            'card_id': wallet.id,
            'order_model': 'pos.order',
            'order_id': order.id,
            'description': _('Gift List Settlement'),
            'issued': 0,
            'used': total_amount,
        })
        
        _logger.info("[MOOMBS] Settlement: Debited wallet %s. Old: %s, New: %s", 
                    wallet.code, old_balance, wallet.points)
        
        # Update order fields
        # CRITICAL: Set to_invoice=False to prevent automatic invoice generation
        # Settlement orders are paid via wallet and should not generate invoices
        # This prevents "negative invoice amount" errors
        _logger.info("[MOOMBS] Settlement: Updating order fields - partner_id=%s, topup_order_id=%s", 
                    original_customer.id, topup_order.id)
        order.write({
            'partner_id': original_customer.id,
            'topup_order_id': topup_order.id,
            'ewallet_beneficiary_id': False,  # Force to False for settlement order
            'to_invoice': False,  # Prevent invoice generation for settlement orders
        })
        
        _logger.info("[MOOMBS] Settlement: Updated order %s with topup_order_id=%s", 
                    order.name, topup_order.id)

    def action_pos_order_paid(self):
        """Override to handle baby list down payments (Epic 5) and wallet intermediary.

        When POS payment is received:
        - Gift List orders: Route payment through wallet (credit → debit)
        - 25% payment (downpayment): Check stock and create INT or PO
        - 100% payment (final): Link pos_order_id for 'paid' state
        """
        # Separate orders into gift list and non-gift list
        gift_list_orders = self.env['pos.order']
        other_orders = self.env['pos.order']
        
        for order in self:
            # CRITICAL: Skip wallet intermediary for topup orders to prevent recursion
            # Topup orders are created by _create_gift_topup_order and should not trigger
            # another wallet intermediary flow
            if order.is_gift_topup_order:
                _logger.info("[MOOMBS] Skipping wallet intermediary for topup order: %s", order.name)
                other_orders |= order
                continue
            
            is_gift_list, sale_orders = self._is_gift_list_order(order)
            
            if is_gift_list:
                gift_list_orders |= order
            else:
                other_orders |= order
        
        # Process wallet intermediary for gift list orders BEFORE marking as paid
        topup_orders_to_mark_paid = self.env['pos.order']
        for order in gift_list_orders:
            _logger.info("[MOOMBS] Gift List order detected: %s, processing wallet intermediary", order.name)
            try:
                _logger.info("[MOOMBS] Calling _process_wallet_intermediary for order %s", order.id)
                result = self._process_wallet_intermediary(order, self._is_gift_list_order(order)[1])
                _logger.info("[MOOMBS] _process_wallet_intermediary completed successfully, result: %s", result)
                # Get the top-up order ID from the result and mark it as paid later
                if result and 'topup_order_id' in result:
                    topup_order = self.env['pos.order'].browse(result['topup_order_id'])
                    if topup_order.exists():
                        topup_orders_to_mark_paid |= topup_order
            except UserError:
                # Re-raise UserError (validation errors)
                raise
            except Exception as e:
                _logger.error("[MOOMBS] Wallet Intermediary error: %s", str(e), exc_info=True)
                raise UserError(_("Error processing wallet intermediary: %s") % str(e))
        
        # Mark top-up orders as paid
        if topup_orders_to_mark_paid:
            _logger.info("[MOOMBS] Marking %d top-up order(s) as paid", len(topup_orders_to_mark_paid))
            topup_orders_to_mark_paid.action_pos_order_paid()
        
        # Now mark all orders as paid (both gift list and others)
        # For gift list orders, the wallet payment has already been added
        res = super().action_pos_order_paid()

        for order in self:
            # DEBUG: Log that hook is running
            _logger.info("[MOOMBS] action_pos_order_paid called for POS Order: %s (Partner: %s, State: %s)", 
                        order.name, order.partner_id.name if order.partner_id else 'No Partner', order.state)
            # Handle directly linked baby list items (legacy)
            if order.baby_list_item_ids:
                order.baby_list_item_ids.write({
                    'pos_order_id': order.id,
                    'paid_by_id': order.paid_by_partner_id.id or order.partner_id.id,
                })

            # Collect sale orders from multiple sources
            # CRITICAL: Prioritize sale_order_origin_id from lines (most reliable for downpayments)
            sale_orders = self.env['sale.order']  # Empty recordset
            sos_from_origin_id = self.env['sale.order']  # Track SOs from origin_id
            
            # FIRST: Check POS order lines for sale_order_origin_id (for downpayments)
            # This is the MOST RELIABLE source for downpayment orders
            if order.lines:
                for pos_line in order.lines:
                    if hasattr(pos_line, 'sale_order_origin_id') and pos_line.sale_order_origin_id:
                        so_id = pos_line.sale_order_origin_id
                        if isinstance(so_id, (int,)):
                            so = self.env['sale.order'].browse(so_id)
                        else:
                            so = so_id
                        if so.exists() and so not in sos_from_origin_id:
                            sos_from_origin_id |= so
                            _logger.info("[MOOMBS] Found SO from sale_order_origin_id: %s (ID: %s)", so.name, so.id)
            
            # If we found SOs from origin_id, USE ONLY THOSE (ignore sale_order_ids which might be wrong)
            if sos_from_origin_id:
                sale_orders = sos_from_origin_id
                _logger.info("[MOOMBS] Using ONLY SOs from sale_order_origin_id: %s", ', '.join([so.name for so in sale_orders]))
            else:
                # SECOND: Check sale_order_ids on order (if pos_sale module links it)
                # Only use this if we didn't find origin_id
                if hasattr(order, 'sale_order_ids') and order.sale_order_ids:
                    sale_orders = order.sale_order_ids
                    _logger.info("[MOOMBS] Using SOs from sale_order_ids: %s", ', '.join([so.name for so in sale_orders]))
            
            # PRIORITY 1: Direct matching via sale_order_line_id or sale_order_origin_id (most precise)
            # For downpayments, Odoo uses sale_order_origin_id instead of sale_order_line_id
            matched_items = self.env['baby.list.item']
            if order.lines:
                for pos_line in order.lines:
                    item = None
                    
                    # Method 1: Check sale_order_line_id (for regular POS orders)
                    if hasattr(pos_line, 'sale_order_line_id') and pos_line.sale_order_line_id:
                        so_line = pos_line.sale_order_line_id
                        _logger.info("[MOOMBS] POS line has sale_order_line_id: %s (SO: %s)", 
                                    so_line.id, so_line.order_id.name if so_line.order_id else 'N/A')
                        
                        # Find baby list item by sale_order_line_id (most precise match)
                        item = self.env['baby.list.item'].search([
                            ('sale_order_line_id', '=', so_line.id),
                        ], limit=1)
                        
                        if item:
                            _logger.info("[MOOMBS] ✓ Direct match found via sale_order_line_id: Item ID=%s, Product=%s, SO=%s", 
                                        item.id, item.product_id.name, so_line.order_id.name)
                        else:
                            # Fallback: Check if SO line has baby_list_item_id field
                            if hasattr(so_line, 'baby_list_item_id') and so_line.baby_list_item_id:
                                item = so_line.baby_list_item_id
                                _logger.info("[MOOMBS] ✓ Direct match found via SO line baby_list_item_id: Item ID=%s, Product=%s", 
                                            item.id, item.product_id.name)
                    
                    # Method 2: Check sale_order_origin_id (for downpayment orders)
                    if not item and hasattr(pos_line, 'sale_order_origin_id') and pos_line.sale_order_origin_id:
                        so_id = pos_line.sale_order_origin_id
                        # Handle both ID and recordset
                        if isinstance(so_id, (int,)):
                            so = self.env['sale.order'].browse(so_id)
                        else:
                            so = so_id
                        
                        if not so.exists():
                            _logger.warning("[MOOMBS] sale_order_origin_id %s does not exist", so_id)
                            continue
                        
                        _logger.info("[MOOMBS] POS line has sale_order_origin_id: %s (SO: %s)", 
                                    so.id, so.name)
                        
                        # Find baby list item linked to this SO
                        # For downpayments, there should be only one item per SO
                        items = self.env['baby.list.item'].search([
                            ('sale_order_id', '=', so.id),
                        ])
                        
                        if len(items) == 1:
                            item = items[0]
                            _logger.info("[MOOMBS] ✓ Direct match found via sale_order_origin_id: Item ID=%s, Product=%s, SO=%s", 
                                        item.id, item.product_id.name, so.name)
                        elif len(items) > 1:
                            # Multiple items for same SO - match by product from downpayment details
                            # Check if pos_line has down_payment_details
                            if hasattr(pos_line, 'down_payment_details') and pos_line.down_payment_details:
                                for dp_detail in pos_line.down_payment_details:
                                    dp_price = dp_detail.get('price_unit') or dp_detail.get('total')
                                    dp_product_name = dp_detail.get('product_name', '')
                                    
                                    _logger.info("[MOOMBS] Downpayment details: product=%s, price=%s", dp_product_name, dp_price)
                                    
                                    # Match by product and price
                                    for candidate_item in items:
                                        if candidate_item.product_id.name == dp_product_name:
                                            # Check if price matches (within tolerance)
                                            item_price = candidate_item.price_unit
                                            if abs(item_price - dp_price) <= 0.01:
                                                item = candidate_item
                                                _logger.info("[MOOMBS] ✓ Matched by product+price: Item ID=%s, Product=%s, Price=%s", 
                                                            item.id, item.product_id.name, item_price)
                                                break
                                    
                                    if item:
                                        break
                            
                            if not item:
                                # Fallback: use first item if no price match
                                item = items[0]
                                _logger.warning("[MOOMBS] Multiple items for SO %s, using first: Item ID=%s", so.name, item.id)
                        
                        # Add SO to sale_orders for processing
                        if item and so and so not in sale_orders:
                            sale_orders |= so
                    
                    if item:
                        matched_items |= item
            
            # If we found items via direct matching, process them first
            if matched_items:
                _logger.info("[MOOMBS] Processing %d directly matched items via sale_order_line_id", len(matched_items))
                for item in matched_items:
                    if not item.sale_order_id:
                        continue
                    
                    sale_order = item.sale_order_id
                    total_paid = self._get_total_paid_for_so(sale_order, current_order=order)
                    is_downpayment = total_paid < sale_order.amount_total
                    is_full_payment = total_paid >= sale_order.amount_total
                    
                    _logger.info("[MOOMBS] Processing DIRECTLY MATCHED item: %s (SO: %s, Total paid: %s, SO total: %s)", 
                                item.product_id.name, sale_order.name, total_paid, sale_order.amount_total)
                    
                    if is_downpayment and not item.pos_downpayment_id:
                        _logger.info("[MOOMBS] Processing down payment for DIRECTLY MATCHED item ID=%s, Product=%s", 
                                    item.id, item.product_id.name)
                        try:
                            self._process_downpayment(item, order)
                            _logger.info("[MOOMBS] Successfully processed down payment for DIRECTLY MATCHED item ID=%s", item.id)
                        except Exception as e:
                            _logger.error("[MOOMBS] Error processing down payment for item %s: %s", item.product_id.name, str(e), exc_info=True)
                    elif is_full_payment and not item.pos_order_id:
                        _logger.info("[MOOMBS] Processing full payment for DIRECTLY MATCHED item: %s", item.product_id.name)
                        item.write({
                            'pos_order_id': order.id,
                            'paid_by_id': order.paid_by_partner_id.id or order.partner_id.id,
                        })
                        item._compute_state()
                        _logger.info("[MOOMBS] Successfully set pos_order_id=%s for DIRECTLY MATCHED item: %s, State: %s", 
                                    order.id, item.product_id.name, item.state)
                
                # Skip further processing if we found direct matches
                continue

            # FALLBACK 1: If sale_order_ids is empty, try to find SO from order lines
            if not sale_orders and order.lines:
                # Check if any line has a sale_order_id reference
                for line in order.lines:
                    if hasattr(line, 'sale_order_id') and line.sale_order_id:
                        if line.sale_order_id not in sale_orders:
                            sale_orders |= line.sale_order_id
                    # Also check if line has a sale_order_line_id (for SO collection)
                    if hasattr(line, 'sale_order_line_id') and line.sale_order_line_id:
                        so = line.sale_order_line_id.order_id
                        if so and so not in sale_orders:
                            sale_orders |= so

            # FALLBACK 2: If still no sale orders, find by partner and baby list items
            # This handles cases where pos_sale module doesn't link the orders
            if not sale_orders and order.partner_id:
                # Find baby list items for this partner that have sale orders
                # and are not yet fully paid (down payment scenario)
                items_with_so = self.env['baby.list.item'].search([
                    ('list_id.partner_id', '=', order.partner_id.id),
                    ('sale_order_id', '!=', False),
                    # Only items that could be in down payment state
                    # (either no pos_downpayment_id yet, or not fully paid)
                    '|',
                    ('pos_downpayment_id', '=', False),
                    ('pos_order_id', '=', False),
                ])
                if items_with_so:
                    # Get unique sale orders from these items
                    potential_sos = items_with_so.mapped('sale_order_id')
                    # Filter to only sale orders that match the payment scenario
                    # (i.e., the POS order amount matches a down payment or final payment)
                    for so in potential_sos:
                        if so and so.amount_total:
                            # Check if this POS order amount could be a payment for this SO
                            # For down payment: typically 25% of SO total
                            # For final payment: remaining amount
                            # We'll be lenient and accept if amount is reasonable
                            if so not in sale_orders:
                                sale_orders |= so

            # Handle items via Sale Orders
            # If no sale orders found via normal methods, try direct item search as last resort
            if not sale_orders and order.partner_id:
                # DIRECT FALLBACK: Find baby list items directly by partner
                # This handles cases where pos_sale doesn't link orders for down payments
                _logger.info("[MOOMBS] No sale orders found via normal methods, trying direct item search for partner: %s", 
                            order.partner_id.name)
                _logger.info("[MOOMBS] POS Order amount: %s", order.amount_total)
                
                direct_items = self.env['baby.list.item'].search([
                    ('list_id.partner_id', '=', order.partner_id.id),
                    ('sale_order_id', '!=', False),
                    # Only items that could be in down payment state
                    '|',
                    ('pos_downpayment_id', '=', False),
                    ('pos_order_id', '=', False),
                ])
                
                _logger.info("[MOOMBS] Found %d baby list items for direct processing", len(direct_items))
                
                if direct_items:
                    # CRITICAL: Match POS order amount to the correct SO
                    # Find the item whose SO amount matches the payment scenario
                    matched_item = None
                    pos_amount = order.amount_total
                    
                    for item in direct_items:
                        if not item.sale_order_id:
                            continue
                        
                        sale_order = item.sale_order_id
                        so_total = sale_order.amount_total
                        
                        # Calculate what's already paid (excluding current order)
                        total_paid_before = self._get_total_paid_for_so(sale_order, current_order=None)
                        remaining = so_total - total_paid_before
                        
                        # Calculate with current order included
                        total_paid_with_current = self._get_total_paid_for_so(sale_order, current_order=order)
                        
                        _logger.info("[MOOMBS] Checking item: %s (SO: %s, SO total: %s, Paid before: %s, Remaining: %s, POS amount: %s)", 
                                    item.product_id.name, sale_order.name, so_total, total_paid_before, remaining, pos_amount)
                        
                        # Match logic:
                        # 1. For downpayment: POS amount should be ~25% of SO total (allow 20-30% tolerance)
                        # 2. For final payment: POS amount should match remaining amount (allow small tolerance)
                        # 3. Exact match is preferred
                        
                        is_downpayment_match = False
                        is_final_payment_match = False
                        
                        if not item.pos_downpayment_id:
                            # Check if this could be a downpayment (25% of SO total)
                            expected_downpayment = so_total * 0.25
                            tolerance = so_total * 0.05  # 5% tolerance
                            if abs(pos_amount - expected_downpayment) <= tolerance:
                                is_downpayment_match = True
                                _logger.info("[MOOMBS]   → Matches downpayment scenario (expected: %s, actual: %s)", expected_downpayment, pos_amount)
                        
                        if not item.pos_order_id:
                            # Check if this could be final payment (matches remaining amount)
                            tolerance = max(0.01, so_total * 0.01)  # 1% tolerance or 0.01 minimum
                            if abs(pos_amount - remaining) <= tolerance:
                                is_final_payment_match = True
                                _logger.info("[MOOMBS]   → Matches final payment scenario (remaining: %s, actual: %s)", remaining, pos_amount)
                        
                        # Also check if POS amount exactly matches SO total (100% single payment)
                        if abs(pos_amount - so_total) <= 0.01:
                            is_final_payment_match = True
                            _logger.info("[MOOMBS]   → Matches 100% single payment (SO total: %s, actual: %s)", so_total, pos_amount)
                        
                        if is_downpayment_match or is_final_payment_match:
                            matched_item = item
                            _logger.info("[MOOMBS] ✓ MATCHED item ID=%s, Product=%s, SO=%s for POS Order %s", 
                                        item.id, item.product_id.name, sale_order.name, order.name)
                            break
                    
                    # Process only the matched item
                    if matched_item:
                        item = matched_item
                        sale_order = item.sale_order_id
                        
                        # Calculate payment progress
                        total_paid = self._get_total_paid_for_so(sale_order, current_order=order)
                        is_downpayment = total_paid < sale_order.amount_total
                        is_full_payment = total_paid >= sale_order.amount_total
                        
                        _logger.info("[MOOMBS] Processing MATCHED item: %s (SO: %s, Total paid: %s, SO total: %s, Current order: %s)", 
                                    item.product_id.name, sale_order.name, total_paid, sale_order.amount_total, order.amount_total)
                        
                        if is_downpayment and not item.pos_downpayment_id:
                            # First payment (25%) - trigger stock check
                            _logger.info("[MOOMBS] Processing down payment for item ID=%s, Product=%s (SO: %s, Total paid: %s, SO total: %s)", 
                                        item.id, item.product_id.name, sale_order.name, total_paid, sale_order.amount_total)
                            _logger.info("[MOOMBS]   - Current item state BEFORE down payment: %s", item.state)
                            _logger.info("[MOOMBS]   - Current pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
                            _logger.info("[MOOMBS]   - Current purchase_order_id: %s", item.purchase_order_id.id if item.purchase_order_id else False)
                            try:
                                self._process_downpayment(item, order)
                                _logger.info("[MOOMBS] Successfully processed down payment for item ID=%s", item.id)
                                _logger.info("[MOOMBS]   - pos_downpayment_id AFTER processing: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
                                _logger.info("[MOOMBS]   - purchase_order_id AFTER processing: %s", item.purchase_order_id.id if item.purchase_order_id else False)
                                _logger.info("[MOOMBS]   - picking_pending_id AFTER processing: %s", item.picking_pending_id.id if item.picking_pending_id else False)
                                _logger.info("[MOOMBS]   - Final state AFTER processing: %s", item.state)
                            except Exception as e:
                                _logger.error("[MOOMBS] Error processing down payment for item %s: %s", item.product_id.name, str(e), exc_info=True)
                        elif is_full_payment and not item.pos_order_id:
                            # Final payment (100%)
                            _logger.info("[MOOMBS] Processing full payment for item: %s (SO: %s, Total paid: %s, SO total: %s)", 
                                        item.product_id.name, sale_order.name, total_paid, sale_order.amount_total)
                            
                            # Set pos_order_id first
                            item.write({
                                'pos_order_id': order.id,
                                'paid_by_id': order.paid_by_partner_id.id or order.partner_id.id,
                            })
                            # CRITICAL: Force state recomputation after write
                            item._compute_state()
                            
                            # CRITICAL: Find and link delivery that Odoo creates automatically
                            # Odoo creates delivery when SO is confirmed, but it might not have partner_id set
                            # We need to find it and set partner_id + link picking_out_id
                            self._link_delivery_for_full_payment(item, sale_order)
                            
                            _logger.info("[MOOMBS] Successfully set pos_order_id=%s for item: %s, State: %s", 
                                        order.id, item.product_id.name, item.state)
                    else:
                        _logger.warning("[MOOMBS] No matching item found for POS Order %s (amount: %s). Checked %d items.", 
                                      order.name, pos_amount, len(direct_items))
                        # Log all items for debugging
                        for item in direct_items:
                            if item.sale_order_id:
                                so_total = item.sale_order_id.amount_total
                                expected_25pct = so_total * 0.25
                                _logger.info("[MOOMBS]   - Item: %s, SO: %s, SO total: %s, Expected 25%%: %s", 
                                            item.product_id.name, item.sale_order_id.name, so_total, expected_25pct)
                    
                    # Skip the normal sale order loop since we processed items directly
                    continue

            if not sale_orders:
                _logger.warning("[MOOMBS] No sale orders found for POS Order %s", order.name)
                continue

            _logger.info("[MOOMBS] Processing %d sale orders for POS Order %s: %s", 
                        len(sale_orders), order.name, ', '.join([so.name for so in sale_orders]))
            
            for sale_order in sale_orders:
                # Defensive check: ensure sale_order has an id
                if not sale_order or not sale_order.id:
                    continue
                
                # Find baby list items linked to this SO
                items = self.env['baby.list.item'].search([
                    ('sale_order_id', '=', sale_order.id),
                ])

                if not items:
                    continue

                # Defensive check: ensure sale_order has amount_total
                if not hasattr(sale_order, 'amount_total') or sale_order.amount_total is None:
                    continue

                # Calculate payment progress
                # CRITICAL: Include current order amount in calculation
                total_paid = self._get_total_paid_for_so(sale_order, current_order=order)
                is_downpayment = total_paid < sale_order.amount_total
                is_full_payment = total_paid >= sale_order.amount_total

                _logger.info("[MOOMBS] Payment calculation for SO: %s (Total paid: %s, SO total: %s, Current order: %s)", 
                            sale_order.name, total_paid, sale_order.amount_total, order.amount_total)
                _logger.info("[MOOMBS]   - is_downpayment: %s, is_full_payment: %s", is_downpayment, is_full_payment)

                for item in items:
                    _logger.info("[MOOMBS] Checking item ID=%s, Product=%s", item.id, item.product_id.name)
                    _logger.info("[MOOMBS]   - Current pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
                    _logger.info("[MOOMBS]   - Current pos_order_id: %s", item.pos_order_id.id if item.pos_order_id else False)
                    _logger.info("[MOOMBS]   - Current purchase_order_id: %s", item.purchase_order_id.id if item.purchase_order_id else False)
                    _logger.info("[MOOMBS]   - Current state: %s", item.state)
                    
                    if is_downpayment and not item.pos_downpayment_id:
                        # First payment (25%) - trigger stock check
                        _logger.info("[MOOMBS] Processing down payment for item ID=%s, Product=%s", item.id, item.product_id.name)
                        _logger.info("[MOOMBS]   - Current item state BEFORE down payment: %s", item.state)
                        self._process_downpayment(item, order)
                        _logger.info("[MOOMBS]   - pos_downpayment_id AFTER processing: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
                        _logger.info("[MOOMBS]   - purchase_order_id AFTER processing: %s", item.purchase_order_id.id if item.purchase_order_id else False)
                        _logger.info("[MOOMBS]   - picking_pending_id AFTER processing: %s", item.picking_pending_id.id if item.picking_pending_id else False)
                        _logger.info("[MOOMBS]   - Final state AFTER processing: %s", item.state)

                    elif is_full_payment and not item.pos_order_id:
                        # Final payment (100%)
                        _logger.info("[MOOMBS] Processing full payment for item: %s (SO: %s, Total paid: %s, SO total: %s)", 
                                    item.product_id.name, sale_order.name, total_paid, sale_order.amount_total)
                        _logger.info("[MOOMBS]   - Current item state BEFORE full payment: %s", item.state)
                        _logger.info("[MOOMBS]   - Current purchase_order_id: %s (PO state: %s)", 
                                    item.purchase_order_id.id if item.purchase_order_id else False,
                                    item.purchase_order_id.state if item.purchase_order_id else 'N/A')
                        
                        # CRITICAL: Check if PO needs to be created for 100% direct payment
                        # (when no 25% down payment was made first)
                        if not item.purchase_order_id and not item.pos_downpayment_id:
                            _logger.info("[MOOMBS] 100% direct payment with no prior down payment - checking stock for PO creation")
                            # Check stock and create PO if needed (same logic as down payment)
                            self._process_downpayment(item, order)
                            _logger.info("[MOOMBS] Stock check completed for 100% payment, purchase_order_id=%s", 
                                        item.purchase_order_id.id if item.purchase_order_id else False)
                        
                        item.write({
                            'pos_order_id': order.id,
                            'paid_by_id': order.paid_by_partner_id.id or order.partner_id.id,
                        })
                        # CRITICAL: Force state recomputation after write
                        item._compute_state()
                        _logger.info("[MOOMBS] Successfully set pos_order_id=%s for item: %s", order.id, item.product_id.name)
                        _logger.info("[MOOMBS]   - pos_order_id AFTER write: %s", item.pos_order_id.id if item.pos_order_id else False)
                        _logger.info("[MOOMBS]   - purchase_order_id AFTER write: %s", item.purchase_order_id.id if item.purchase_order_id else False)
                        _logger.info("[MOOMBS]   - Final state AFTER write and recompute: %s", item.state)
                    else:
                        if item.pos_order_id:
                            _logger.info("[MOOMBS] Item already has pos_order_id=%s, skipping", item.pos_order_id.id)
                        elif not is_full_payment:
                            _logger.info("[MOOMBS] Payment is not full (Total paid: %s < SO total: %s), skipping full payment processing", 
                                        total_paid, sale_order.amount_total)

        return res

    def _get_total_paid_for_so(self, sale_order, current_order=None):
        """Calculate total amount paid for a Sale Order via POS.
        
        Args:
            sale_order: The sale order to calculate payments for
            current_order: Optional current POS order being processed (to include in calculation)
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # CRITICAL: Check if sale_order_ids field exists (pos_sale module may not be installed)
        if hasattr(self, 'sale_order_ids'):
            # Search for existing paid orders linked to this SO
            pos_orders = self.search([
                ('sale_order_ids', 'in', sale_order.id),
                ('state', '=', 'paid'),
            ])
            # Exclude current_order if it's already in the results (to avoid double counting)
            if current_order and current_order.id:
                pos_orders = pos_orders.filtered(lambda o: o.id != current_order.id)
        else:
            # FALLBACK: Find POS orders by searching for baby list items linked to this SO
            # and then finding their pos_downpayment_id or pos_order_id
            items = self.env['baby.list.item'].search([
                ('sale_order_id', '=', sale_order.id),
            ])
            # Get all POS orders linked to these items (down payments and final payments)
            pos_order_ids = []
            for item in items:
                if item.pos_downpayment_id:
                    pos_order_ids.append(item.pos_downpayment_id.id)
                if item.pos_order_id:
                    pos_order_ids.append(item.pos_order_id.id)
            # Remove duplicates
            pos_order_ids = list(set(pos_order_ids))
            # Exclude current_order if it's in the list (to avoid double counting)
            if current_order and current_order.id and current_order.id in pos_order_ids:
                pos_order_ids.remove(current_order.id)
            
            if pos_order_ids:
                pos_orders = self.search([
                    ('id', 'in', pos_order_ids),
                    ('state', '=', 'paid'),
                ])
            else:
                pos_orders = self.env['pos.order']  # Empty recordset
        
        # Calculate total from existing paid orders
        total = sum(pos_orders.mapped('amount_total'))
        
        # CRITICAL: Include current order amount if provided
        # This ensures we count the payment being processed right now
        # IMPORTANT: Use line amounts instead of order.amount_total because wallet discounts
        # can make order.amount_total = 0, but the actual payment for the SO is in the lines
        if current_order:
            current_order_amount = 0
            
            # Method 1: Calculate from lines that reference this SO
            if current_order.lines:
                so_line_ids = sale_order.order_line.ids
                for pos_line in current_order.lines:
                    # Check if this line is related to the sale order
                    line_amount = 0
                    
                    # Check sale_order_line_id (direct link to SO line)
                    if hasattr(pos_line, 'sale_order_line_id') and pos_line.sale_order_line_id:
                        if pos_line.sale_order_line_id.id in so_line_ids:
                            # Use price_subtotal (actual payment amount, not affected by wallet discounts)
                            line_amount = pos_line.price_subtotal
                            _logger.info("[MOOMBS] _get_total_paid_for_so: Found SO line %s in POS order, amount: %s", 
                                        pos_line.sale_order_line_id.id, line_amount)
                    
                    # Check sale_order_origin_id (for downpayment lines)
                    elif hasattr(pos_line, 'sale_order_origin_id') and pos_line.sale_order_origin_id:
                        so_id = pos_line.sale_order_origin_id
                        if isinstance(so_id, (int,)):
                            so_id = so_id
                        else:
                            so_id = so_id.id if hasattr(so_id, 'id') else so_id
                        
                        if so_id == sale_order.id:
                            # For downpayments, use price_subtotal
                            line_amount = pos_line.price_subtotal
                            _logger.info("[MOOMBS] _get_total_paid_for_so: Found SO origin %s in POS order, amount: %s", 
                                        so_id, line_amount)
                    
                    if line_amount > 0:
                        current_order_amount += line_amount
            
            # Method 2: Fallback to order.amount_total if no lines matched (shouldn't happen, but defensive)
            if current_order_amount == 0 and current_order.amount_total:
                current_order_amount = current_order.amount_total
                _logger.warning("[MOOMBS] _get_total_paid_for_so: No matching lines found, using order.amount_total: %s", 
                              current_order_amount)
            
            if current_order_amount > 0:
                total += current_order_amount
                _logger.info("[MOOMBS] _get_total_paid_for_so: Including current order %s (amount: %s) in total. Total: %s", 
                            current_order.name, current_order_amount, total)
            else:
                _logger.info("[MOOMBS] _get_total_paid_for_so: Total from existing orders: %s (current_order has no amount for this SO)", 
                            total)
        else:
            _logger.info("[MOOMBS] _get_total_paid_for_so: Total from existing orders: %s (current_order not provided)", 
                        total)
        
        return total

    def _process_downpayment(self, item, pos_order):
        """Process 25% down payment: check stock, create INT or PO."""
        product = item.product_id

        # Get locations
        stock_location = self.env.ref('stock.stock_location_stock')
        pending_location = self.env.ref('moombs_list.stock_location_pending_delivery')

        # Check available stock
        available_qty = product.with_context(
            location=stock_location.id
        ).free_qty

        if available_qty >= 1:
            # Stock available: Create Internal Transfer
            self._create_internal_transfer(item, product, stock_location, pending_location, pos_order)
        else:
            # No stock: Create Purchase Order
            self._create_purchase_order(item, product, pos_order)

    def _create_internal_transfer(self, item, product, src_loc, dest_loc, pos_order):
        """Create internal transfer to Pending Delivery."""
        picking_type = self.env.ref('moombs_list.picking_type_internal_pending')

        # Set partner_id from baby list beneficiary
        partner_id = item.list_id.partner_id.id if item.list_id and item.list_id.partner_id else False

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'origin': _('MOOMBS: %s') % item.list_id.name,
            'baby_list_item_id': item.id,
            'partner_id': partner_id,  # Set contact from beneficiary
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom': product.uom_id.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'partner_id': partner_id,  # Set contact on move as well
            })],
        })
        
        if partner_id:
            _logger.info("[MOOMBS] _create_internal_transfer: Set partner_id=%s (beneficiary) on internal transfer %s", 
                        partner_id, picking.name)

        picking.action_confirm()
        picking.action_assign()

        _logger.info("[MOOMBS] _create_internal_transfer: Setting pos_downpayment_id=%s and picking_pending_id=%s for item ID=%s", 
                    pos_order.id, picking.id, item.id)
        _logger.info("[MOOMBS]   - Item state BEFORE write: %s", item.state)
        _logger.info("[MOOMBS]   - Current pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
        _logger.info("[MOOMBS]   - Current purchase_order_id: %s", item.purchase_order_id.id if item.purchase_order_id else False)

        item.write({
            'picking_pending_id': picking.id,
            'pos_downpayment_id': pos_order.id,
        })
        # CRITICAL: Force state recomputation after write
        item._compute_state()
        _logger.info("[MOOMBS]   - Item state AFTER write and recompute: %s", item.state)
        _logger.info("[MOOMBS]   - pos_downpayment_id after write: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
        _logger.info("[MOOMBS]   - purchase_order_id after write: %s", item.purchase_order_id.id if item.purchase_order_id else False)

    def _link_delivery_for_full_payment(self, item, sale_order):
        """Find and link delivery picking created by Odoo for 100% payment.
        
        When SO is confirmed, Odoo automatically creates delivery picking.
        We need to:
        1. Find the delivery picking (via SO or product+partner)
        2. Set partner_id from beneficiary (SAME AS internal transfer)
        3. Link picking_out_id to item
        4. Recompute state to show "out_created"
        
        This mirrors _create_internal_transfer logic but for deliveries.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info("[MOOMBS] _link_delivery_for_full_payment: ===== START =====")
        _logger.info("[MOOMBS] _link_delivery_for_full_payment: Looking for delivery for item ID=%s, Product=%s, SO=%s (ID=%s)", 
                    item.id, item.product_id.name if item.product_id else 'None', 
                    sale_order.name, sale_order.id)
        _logger.info("[MOOMBS] _link_delivery_for_full_payment: SO partner values - partner_id=%s (%s), partner_shipping_id=%s (%s), partner_invoice_id=%s (%s)", 
                    sale_order.partner_id.id if sale_order.partner_id else 'None',
                    sale_order.partner_id.name if sale_order.partner_id else 'None',
                    sale_order.partner_shipping_id.id if sale_order.partner_shipping_id else 'None',
                    sale_order.partner_shipping_id.name if sale_order.partner_shipping_id else 'None',
                    sale_order.partner_invoice_id.id if sale_order.partner_invoice_id else 'None',
                    sale_order.partner_invoice_id.name if sale_order.partner_invoice_id else 'None')
        _logger.info("[MOOMBS] _link_delivery_for_full_payment: Item beneficiary - list_id.partner_id=%s (%s)", 
                    item.list_id.partner_id.id if item.list_id and item.list_id.partner_id else 'None',
                    item.list_id.partner_id.name if item.list_id and item.list_id.partner_id else 'None')
        
        # CRITICAL: Delivery might be created from POS (WH/POS) or from SO (WH/OUT)
        # POS deliveries might not have sale_id set immediately, so we need multiple search methods
        
        delivery = None
        
        # Method 1: Find delivery via SO (most reliable for SO-created deliveries)
        # Odoo creates delivery when SO is confirmed, so it should have sale_id
        delivery = self.env['stock.picking'].search([
            ('sale_id', '=', sale_order.id),
            ('picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
        ], limit=1, order='create_date desc')
        
        if delivery:
            _logger.info("[MOOMBS] _link_delivery_for_full_payment: Found delivery %s via sale_id=%s", 
                        delivery.name, sale_order.id)
        else:
            # Method 2: Find via product + partner (CRITICAL for POS-created deliveries)
            # POS deliveries (WH/POS) might not have sale_id, so search by product+partner
            if item.product_id and item.list_id.partner_id:
                delivery = self.env['stock.picking'].search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('move_ids.product_id', '=', item.product_id.id),
                    ('partner_id', '=', item.list_id.partner_id.id),
                    ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
                    ('picking_out_id', '=', False),  # Not already linked to another item
                ], limit=1, order='create_date desc')
                
                if delivery:
                    _logger.info("[MOOMBS] _link_delivery_for_full_payment: Found delivery %s via product+partner (POS delivery)", 
                                delivery.name)
        
        # Method 3: If still not found, search by product only (last resort)
        # This handles cases where partner_id is not set yet on delivery
        if not delivery and item.product_id:
            delivery = self.env['stock.picking'].search([
                ('picking_type_code', '=', 'outgoing'),
                ('move_ids.product_id', '=', item.product_id.id),
                ('state', 'in', ['draft', 'waiting', 'assigned', 'done']),
                ('baby_list_item_id', '=', False),  # Not already linked
                ('picking_out_id', '=', False),  # Not already linked to another item
            ], limit=1, order='create_date desc')
            
            if delivery:
                _logger.info("[MOOMBS] _link_delivery_for_full_payment: Found delivery %s via product only (last resort)", 
                            delivery.name)
        
        if delivery:
            _logger.info("[MOOMBS] _link_delivery_for_full_payment: Found delivery %s (ID=%s, state=%s)", 
                        delivery.name, delivery.id, delivery.state)
            _logger.info("[MOOMBS] _link_delivery_for_full_payment: Delivery partner BEFORE fix - partner_id=%s (%s)", 
                        delivery.partner_id.id if delivery.partner_id else 'None',
                        delivery.partner_id.name if delivery.partner_id else 'None')
            
            # Set partner_id from beneficiary (CRITICAL - SAME AS internal transfer)
            if item.list_id and item.list_id.partner_id:
                partner_id = item.list_id.partner_id.id
                partner_name = item.list_id.partner_id.name
                
                if not delivery.partner_id or delivery.partner_id.id != partner_id:
                    delivery.write({'partner_id': partner_id})
                    _logger.info("[MOOMBS] _link_delivery_for_full_payment: ✓ Set partner_id=%s (%s) on delivery %s (was: %s)", 
                                partner_id, partner_name, delivery.name,
                                delivery.partner_id.id if delivery.partner_id else 'None')
                else:
                    _logger.info("[MOOMBS] _link_delivery_for_full_payment: ✓ partner_id=%s already correct on delivery %s", 
                                partner_id, delivery.name)
                
                # Set on all moves (SAME AS internal transfer)
                for move in delivery.move_ids:
                    if not move.partner_id or move.partner_id.id != partner_id:
                        move.write({'partner_id': partner_id})
                        _logger.info("[MOOMBS] _link_delivery_for_full_payment: ✓ Set partner_id=%s on move %s (product: %s)", 
                                    partner_id, move.id, move.product_id.name if move.product_id else 'None')
                    else:
                        _logger.info("[MOOMBS] _link_delivery_for_full_payment: ✓ partner_id=%s already correct on move %s", 
                                    partner_id, move.id)
            
            # Link baby_list_item_id
            if not delivery.baby_list_item_id:
                delivery.write({'baby_list_item_id': item.id})
                _logger.info("[MOOMBS] _link_delivery_for_full_payment: Linked baby_list_item_id=%s to delivery %s", 
                            item.id, delivery.name)
            
            # Link picking_out_id (CRITICAL for state computation)
            if not item.picking_out_id or item.picking_out_id.id != delivery.id:
                item.write({'picking_out_id': delivery.id})
                _logger.info("[MOOMBS] _link_delivery_for_full_payment: Linked picking_out_id=%s to item %s", 
                            delivery.id, item.id)
                
                # Recompute state to show "out_created" (Priority 3 > Priority 4 Paid)
                item.invalidate_recordset(['picking_out_id', 'pos_order_id', 'state'])
                item._compute_state()
                _logger.info("[MOOMBS] _link_delivery_for_full_payment: State recomputed, item state=%s (delivery state=%s)", 
                            item.state, delivery.state)
        else:
            _logger.warning("[MOOMBS] _link_delivery_for_full_payment: Could not find delivery for item ID=%s, SO=%s. "
                          "Delivery might be created later by Odoo. Will be linked via write() or action_confirm().", 
                          item.id, sale_order.name)

    def _create_purchase_order(self, item, product, pos_order):
        """Create PO when no stock available."""
        # Get vendor
        seller = product.seller_ids[:1]
        if not seller:
            _logger.info("[MOOMBS] _create_purchase_order: No vendor found, setting pos_downpayment_id=%s for item ID=%s", 
                        pos_order.id, item.id)
            _logger.info("[MOOMBS]   - Item state BEFORE write: %s", item.state)
            _logger.info("[MOOMBS]   - Current pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
            _logger.info("[MOOMBS]   - Current purchase_order_id: %s", item.purchase_order_id.id if item.purchase_order_id else False)
            
            item.write({'pos_downpayment_id': pos_order.id})
            # CRITICAL: Force state recomputation after write (state should be 'ordered')
            item._compute_state()
            _logger.info("[MOOMBS]   - Item state AFTER write and recompute: %s", item.state)
            _logger.info("[MOOMBS]   - pos_downpayment_id after write: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
            return

        po = self.env['purchase.order'].create({
            'partner_id': seller.partner_id.id,
            'origin': _('MOOMBS: %s') % item.list_id.name,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': 1,
                'product_uom_id': product.uom_id.id,
                'price_unit': seller.price or product.standard_price,
            })],
        })

        _logger.info("[MOOMBS] _create_purchase_order: Setting pos_downpayment_id=%s and purchase_order_id=%s for item ID=%s", 
                    pos_order.id, po.id, item.id)
        _logger.info("[MOOMBS]   - Item state BEFORE write: %s", item.state)
        _logger.info("[MOOMBS]   - Current pos_downpayment_id: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
        _logger.info("[MOOMBS]   - Current purchase_order_id: %s", item.purchase_order_id.id if item.purchase_order_id else False)

        item.write({
            'purchase_order_id': po.id,
            'pos_downpayment_id': pos_order.id,
        })
        # CRITICAL: Force state recomputation after write
        item._compute_state()
        _logger.info("[MOOMBS]   - Item state AFTER write and recompute: %s", item.state)
        _logger.info("[MOOMBS]   - pos_downpayment_id after write: %s", item.pos_downpayment_id.id if item.pos_downpayment_id else False)
        _logger.info("[MOOMBS]   - purchase_order_id after write: %s", item.purchase_order_id.id if item.purchase_order_id else False)
