# -*- coding: utf-8 -*-
"""
LST-010: Add Product to List (Creates Confirmed SO)
LST-011: See Product Details
LST-012: See Discount and Final Price
BR-004: One Line = One Unit
BR-008: No Edit
======================================

Feature: Add Products to List
  As an Advisor
  I want to add products to the list
  So that a confirmed SO is created for the beneficiary

  Pillar: LIST
  Principles: P7 (Referential Integrity), P8 (One Line = One Unit)
  Business Rules: BR-004, BR-008
  Priority: Must
"""

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .common import MoombsTestCommon


@tagged('moombs', 'lst_010', 'lst_011', 'lst_012', 'products', 'must')
class TestLST010012AddProducts(MoombsTestCommon):
    """Test cases for LST-010, LST-011, LST-012: Add Products."""

    def setUp(self):
        super().setUp()
        self.baby_list = self.create_test_list()

    # ═══════════════════════════════════════════════════════════════
    # LST-010: ADD PRODUCT - CREATES CONFIRMED SO
    # ═══════════════════════════════════════════════════════════════

    def test_add_product_creates_so(self):
        """
        @happy_path @must @LST-010
        Scenario: Adding product creates confirmed Sale Order
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # SO should be created and confirmed
        self.assertTrue(item.sale_order_id, "Sale Order should be created")
        self.assertEqual(item.sale_order_id.state, 'sale', "SO should be confirmed")

    def test_so_linked_to_beneficiary(self):
        """
        @happy_path @must @LST-010
        Scenario: SO partner is Beneficiary 1
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        self.assertEqual(
            item.sale_order_id.partner_id,
            self.baby_list.partner_id,
            "SO partner should be the baby list beneficiary"
        )

    def test_so_created_by_advisor(self):
        """
        @happy_path @must @LST-010
        Scenario: SO user is baby list advisor
        """
        # Set advisor on baby list
        self.baby_list.advisor_id = self.user_advisor

        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        self.assertEqual(
            item.sale_order_id.user_id,
            self.baby_list.advisor_id,
            "SO user should be the baby list advisor"
        )

    def test_item_state_ordered_after_add(self):
        """
        @happy_path @must @LST-010
        Scenario: Item state is 'ordered' after add (SO created)
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        self.assertEqual(item.state, 'ordered', "Item should be in 'ordered' state")
        self.assertTrue(item.date_ordered, "date_ordered should be set")

    def test_so_has_baby_list_link(self):
        """
        @happy_path @LST-010
        Scenario: SO has link back to baby list
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        self.assertEqual(
            item.sale_order_id.baby_list_id,
            self.baby_list,
            "SO should have baby_list_id link"
        )

    # ═══════════════════════════════════════════════════════════════
    # BR-004: ONE LINE = ONE UNIT
    # ═══════════════════════════════════════════════════════════════

    def test_so_line_qty_always_one(self):
        """
        @happy_path @must @BR-004
        Scenario: SO line qty is always 1
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # Get SO line via SO (1 item = 1 SO = 1 SO line)
        so_line = item.sale_order_id.order_line[0]
        self.assertEqual(
            so_line.product_uom_qty,
            1,
            "SO line qty must be 1 (BR-004)"
        )

    def test_multiple_units_create_multiple_sos(self):
        """
        @happy_path @BR-004
        Scenario: Each unit creates separate SO (One Line = One Unit)
        """
        # Add 3 bottles - should create 3 separate SOs
        items = []
        for _ in range(3):
            item = self.env['baby.list.item'].create({
                'list_id': self.baby_list.id,
                'product_id': self.product_bottle.id,
                'price_unit': self.product_bottle.list_price,
            })
            items.append(item)

        self.assertEqual(len(items), 3)

        # All items have separate SOs with qty=1
        so_ids = set()
        for item in items:
            self.assertTrue(item.sale_order_id)
            so_ids.add(item.sale_order_id.id)
            self.assertEqual(item.sale_order_id.order_line[0].product_uom_qty, 1)

        # Each item has a different SO
        self.assertEqual(len(so_ids), 3, "Each item should have separate SO")

    # ═══════════════════════════════════════════════════════════════
    # BR-008: NO EDIT
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_edit_product(self):
        """
        @sad_path @must @BR-008
        Scenario: Cannot change product after creation
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        with self.assertRaises(UserError):
            item.product_id = self.product_bottle.id

    def test_cannot_edit_price(self):
        """
        @sad_path @must @BR-008
        Scenario: Cannot change price after creation
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        with self.assertRaises(UserError):
            item.price_unit = 999.99

    def test_cannot_edit_discount(self):
        """
        @sad_path @must @BR-008
        Scenario: Cannot change discount after creation
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
            'discount': 10,
        })

        with self.assertRaises(UserError):
            item.discount = 50

    def test_can_change_state(self):
        """
        @happy_path @BR-008
        Scenario: CAN change state (allowed field)
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # Should not raise
        item.state = 'reserved'
        self.assertEqual(item.state, 'reserved')

    # ═══════════════════════════════════════════════════════════════
    # LST-010: ADD PRODUCT - SAD PATH
    # ═══════════════════════════════════════════════════════════════

    def test_cannot_add_to_inactive_list(self):
        """
        @sad_path @P10
        Scenario: Cannot add to inactive list
        """
        self.baby_list.state = 'inactive'

        with self.assertRaises((UserError, ValidationError)):
            self.env['baby.list.item'].create({
                'list_id': self.baby_list.id,
                'product_id': self.product_crib.id,
                'price_unit': self.product_crib.list_price,
            })

    def test_cannot_add_to_completed_list(self):
        """
        @sad_path @P10
        Scenario: Cannot add to completed list
        """
        self.baby_list.state = 'completed'

        with self.assertRaises((UserError, ValidationError)):
            self.env['baby.list.item'].create({
                'list_id': self.baby_list.id,
                'product_id': self.product_crib.id,
                'price_unit': self.product_crib.list_price,
            })

    def test_product_is_required(self):
        """
        @sad_path
        Scenario: Product is required
        """
        with self.assertRaises((ValidationError, Exception)):
            self.env['baby.list.item'].create({
                'list_id': self.baby_list.id,
                'price_unit': 100,
                # product_id missing
            })

    # ═══════════════════════════════════════════════════════════════
    # LST-011: PRODUCT DETAILS
    # ═══════════════════════════════════════════════════════════════

    def test_product_image_accessible(self):
        """
        @happy_path @must @LST-011
        Scenario: Product image is accessible via related field
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # product_image is a related field to product_id.image_128
        self.assertTrue(hasattr(item, 'product_image'))

    def test_product_code_accessible(self):
        """
        @happy_path @must @LST-011
        Scenario: Product code is accessible via related field
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        self.assertEqual(item.product_code, 'CRIB001')

    def test_product_details_accessible(self):
        """
        @happy_path @must
        Scenario: Product details are accessible on line
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # Product info should be accessible
        self.assertEqual(item.product_id.name, 'Premium Crib')
        self.assertEqual(item.product_id.default_code, 'CRIB001')

    # ═══════════════════════════════════════════════════════════════
    # LST-012: PRICE CAPTURE AND FINAL PRICE
    # ═══════════════════════════════════════════════════════════════

    def test_price_captured_at_add_time(self):
        """
        @happy_path @must @LST-012
        Scenario: Price captured at add time (not live)
        """
        original_price = self.product_crib.list_price  # 450

        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': original_price,
        })

        # Change product price
        self.product_crib.list_price = 500

        # Item should still have original price
        self.assertEqual(item.price_unit, original_price)

    def test_price_final_calculation(self):
        """
        @happy_path @must @P6 @LST-012
        Scenario: Final price = Price × (1 - Discount/100)
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': 100.00,
            'discount': 10,  # 10%
        })

        # To Pay = 100 * (1 - 0.10) = 90
        self.assertAlmostEqual(item.price_final, 90.00, places=2)

    def test_price_final_no_discount(self):
        """
        @happy_path @LST-012
        Scenario: Final price with no discount
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': 100.00,
            'discount': 0,
        })

        self.assertAlmostEqual(item.price_final, 100.00, places=2)

    def test_price_final_full_discount(self):
        """
        @edge_case @LST-012
        Scenario: Final price with 100% discount
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': 100.00,
            'discount': 100,  # 100%
        })

        self.assertAlmostEqual(item.price_final, 0.00, places=2)

    def test_discount_percentage_format(self):
        """
        @happy_path @LST-012
        Scenario: Discount stored as percentage
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': 100.00,
            'discount': 15.5,  # 15.5%
        })

        self.assertEqual(item.discount, 15.5)
        self.assertAlmostEqual(item.price_final, 84.50, places=2)

    def test_so_line_has_correct_price(self):
        """
        @happy_path @LST-012
        Scenario: SO line has captured price
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': 450.00,
        })

        # Get SO line via SO (1 item = 1 SO = 1 SO line)
        so_line = item.sale_order_id.order_line[0]
        self.assertEqual(
            so_line.price_unit,
            450.00,
            "SO line should have captured price"
        )

    def test_add_product_logs_to_chatter(self):
        """
        @happy_path @P5
        Scenario: Adding product logs to chatter with SO reference
        """
        item = self.env['baby.list.item'].create({
            'list_id': self.baby_list.id,
            'product_id': self.product_crib.id,
            'price_unit': self.product_crib.list_price,
        })

        # Check that a message was logged
        self.assertTrue(len(self.baby_list.message_ids) > 0)
