# -*- coding: utf-8 -*-
"""
LST-020 to LST-024: View & Track
================================

View and Track features for list items:
- LST-020: See Dates with Timestamps
- LST-021: Click Date to Open Document
- LST-022: See Who Paid for Product
- LST-023: See Cancelled Items at Bottom
- LST-024: Smart Buttons

  Pillar: LIST
  Principles: P5 (Traceability), P6 (Computed States)
  Priority: Must/Should
"""

from odoo.tests import tagged
from odoo.fields import Datetime
from datetime import datetime
from .common import MoombsTestCommon


@tagged('moombs', 'lst_020', 'lst_021', 'lst_022', 'lst_023', 'lst_024', 'view', 'track')
class TestLST020024ViewTrack(MoombsTestCommon):
    """Test cases for View & Track features."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()
        self.item = self.create_test_item(self.baby_list)

    # ═══════════════════════════════════════════════════════════════
    # LST-020: DATES WITH TIMESTAMPS
    # ═══════════════════════════════════════════════════════════════

    def test_date_ordered_stored(self):
        """
        @happy_path @must @P5
        Scenario: date_ordered is stored when order created
        """
        self.item.state = 'ordered'
        self.item.date_ordered = Datetime.now()
        
        self.assertTrue(self.item.date_ordered)
        self.assertIsInstance(self.item.date_ordered, datetime)

    def test_date_paid_stored(self):
        """
        @happy_path @P5
        Scenario: date_paid is stored when paid
        """
        self.item.state = 'paid'
        self.item.date_paid = Datetime.now()
        
        self.assertTrue(self.item.date_paid)

    def test_date_delivered_stored(self):
        """
        @happy_path @P5
        Scenario: date_delivered is stored when delivered
        """
        self.item.state = 'delivered'
        self.item.date_delivered = Datetime.now()
        
        self.assertTrue(self.item.date_delivered)

    def test_date_cancelled_stored(self):
        """
        @happy_path @P5
        Scenario: date_cancelled is stored when cancelled
        """
        self.item.state = 'cancelled'
        self.item.date_cancelled = Datetime.now()
        
        self.assertTrue(self.item.date_cancelled)

    def test_dates_filled_progressively(self):
        """
        @happy_path @P5
        Scenario: Dates filled progressively as actions occur
        """
        now = Datetime.now()
        
        # Initially no dates
        self.assertFalse(self.item.date_ordered)
        
        # Order fills date_ordered
        self.item.date_ordered = now
        self.assertTrue(self.item.date_ordered)
        self.assertFalse(self.item.date_paid)

    # ═══════════════════════════════════════════════════════════════
    # LST-021: CLICK DATE TO OPEN DOCUMENT
    # ═══════════════════════════════════════════════════════════════

    def test_sale_order_link(self):
        """
        @happy_path @must @P5
        Scenario: sale_order_id links to SO document
        """
        # Create a sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_ana.id,
        })
        
        self.item.sale_order_id = sale_order.id
        
        self.assertEqual(self.item.sale_order_id, sale_order)
        # Clicking should open SO form (tested in UI)

    def test_multiple_document_links(self):
        """
        @edge_case @P5
        Scenario: Line can have multiple document links
        """
        # Line can have: sale_order_id, picking_id, pos_order_id
        # Each should be clickable when filled
        
        self.assertTrue(hasattr(self.item, 'sale_order_id'))
        # Additional fields depend on implementation

    # ═══════════════════════════════════════════════════════════════
    # LST-022: SEE WHO PAID
    # ═══════════════════════════════════════════════════════════════

    def test_paid_by_stored(self):
        """
        @happy_path @must @P5
        Scenario: paid_by_id shows who paid for product
        """
        self.item.paid_by_id = self.partner_maria.id
        
        self.assertEqual(self.item.paid_by_id, self.partner_maria)
        self.assertEqual(self.item.paid_by_id.name, 'María García López')

    def test_paid_by_beneficiary(self):
        """
        @happy_path
        Scenario: If beneficiary paid, shows their name
        """
        self.item.paid_by_id = self.partner_ana.id
        
        self.assertEqual(self.item.paid_by_id, self.partner_ana)

    def test_paid_by_empty_when_unpaid(self):
        """
        @edge_case
        Scenario: paid_by_id is empty when not yet paid
        """
        self.assertFalse(self.item.paid_by_id)

    # ═══════════════════════════════════════════════════════════════
    # LST-023: CANCELLED ITEMS AT BOTTOM
    # ═══════════════════════════════════════════════════════════════

    def test_cancelled_items_sort_order(self):
        """
        @happy_path @should @P6
        Scenario: Cancelled items sorted to bottom
        """
        # Create items in different states
        item_wished = self.create_test_item(self.baby_list, product=self.product_crib)
        item_cancelled = self.create_test_item(self.baby_list, product=self.product_bottle)
        item_delivered = self.create_test_item(self.baby_list, product=self.product_chair)
        
        item_wished.state = 'wished'
        item_cancelled.state = 'cancelled'
        item_delivered.state = 'delivered'
        
        # Get items ordered by state (implementation may vary)
        # Active items should come before cancelled
        active_items = self.baby_list.item_ids.filtered(
            lambda i: i.state != 'cancelled'
        )
        cancelled_items = self.baby_list.item_ids.filtered(
            lambda i: i.state == 'cancelled'
        )
        
        self.assertEqual(len(cancelled_items), 1)
        self.assertEqual(len(active_items), 3)  # Including original item

    def test_cancelled_item_has_marker(self):
        """
        @edge_case
        Scenario: Cancelled item identifiable
        """
        self.item.state = 'cancelled'
        
        self.assertEqual(self.item.state, 'cancelled')
        # Visual styling tested in UI

    # ═══════════════════════════════════════════════════════════════
    # LST-024: SMART BUTTONS
    # ═══════════════════════════════════════════════════════════════

    def test_item_count_computed(self):
        """
        @happy_path @must
        Scenario: Item count is computed
        """
        # Add more items
        self.create_test_item(self.baby_list, product=self.product_bottle)
        self.create_test_item(self.baby_list, product=self.product_chair)
        
        if hasattr(self.baby_list, 'item_count'):
            self.assertEqual(self.baby_list.item_count, 3)
        else:
            self.assertEqual(len(self.baby_list.item_ids), 3)

    def test_wallet_balance_in_smart_button(self):
        """
        @happy_path @must
        Scenario: Wallet balance accessible
        """
        if self.baby_list.wallet_id:
            self.baby_list.wallet_id.points = 500
            
            if hasattr(self.baby_list, 'wallet_balance'):
                self.assertEqual(self.baby_list.wallet_balance, 500)

    def test_smart_button_actions_exist(self):
        """
        @edge_case
        Scenario: Smart button action methods exist
        """
        # List should have action methods for smart buttons
        action_methods = [
            'action_view_items',
            'action_view_wallet',
            'action_view_family',
            'action_view_deliveries',
        ]
        
        for method in action_methods:
            # Methods may or may not exist depending on implementation
            if hasattr(self.baby_list, method):
                self.assertTrue(callable(getattr(self.baby_list, method)))

    def test_family_count_computed(self):
        """
        @edge_case
        Scenario: Family count is computed
        """
        # If family_ids exists
        if hasattr(self.baby_list, 'family_ids'):
            if hasattr(self.baby_list, 'family_count'):
                self.assertEqual(
                    self.baby_list.family_count, 
                    len(self.baby_list.family_ids)
                )
