/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { onMounted } from "@odoo/owl";
import { PaidByPopup } from "./paid_by_popup";

/**
 * Extend PaymentScreen to intercept eWallet payments.
 *
 * When an eWallet payment method is selected:
 * 1. Check if order has a partner (beneficiary)
 * 2. Check if paidByPartner is not already set
 * 3. Show PaidByPopup to select the paying customer
 * 4. Set paidByPartner on order if selected
 * 5. Continue with normal payment flow
 */
patch(PaymentScreen.prototype, {
    /**
     * Override addNewPaymentLine to intercept eWallet payments.
     * Shows "Paid By" popup when eWallet is selected for the first time.
     */
    async addNewPaymentLine(paymentMethod) {
        const order = this.currentOrder;

        // Check if this is an eWallet payment that needs the popup
        const shouldShowPopup = this._shouldShowPaidByPopup(paymentMethod, order);

        if (shouldShowPopup) {
            const partner = order.getPartner();

            try {
                // Use makeAwaitable to properly handle the popup dialog
                const payload = await makeAwaitable(this.dialog, PaidByPopup, {
                    beneficiary: partner,
                });

                // If user selected a different partner, set it on order
                if (payload && payload.partner) {
                    order.setPaidByPartner(payload.partner);
                }

                // Set note on order if provided
                if (payload && payload.note) {
                    order.setPopupNote(payload.note);
                }
            } catch (error) {
                console.error("[PaidByPopup] Error showing popup:", error);
            }
        }

        // Continue with normal payment selection
        return super.addNewPaymentLine(...arguments);
    },

    /**
     * Determine if the Paid By popup should be shown.
     *
     * Conditions:
     * 1. Order has a partner (the beneficiary)
     * 2. Paid by partner not already set on this order
     * 3. TRIGGER:
     *    a) Order contains an eWallet Top-up product (User's main flow)
     *    OR
     *    b) Payment method is eWallet (Spending flow)
     */
    _shouldShowPaidByPopup(paymentMethod, order) {
        // 1. Must have a partner (beneficiary) set
        const partner = order.getPartner();
        if (!partner) {
            return false;
        }

        // 2. Don't show if already set
        if (order.paidByPartner) {
            return false;
        }

        // 3a. Check for eWallet Top-up (Product lines)
        const isTopUp = this._isEwalletTopUp(order);
        if (isTopUp) {
            return true;
        }

        // 3b. Check for eWallet Payment (Spending)
        const isEwalletPayment = this._isEwalletPaymentMethod(paymentMethod);
        if (isEwalletPayment) {
            return true;
        }

        return false;
    },

    /**
     * Check if the order contains any eWallet top-up lines.
     */
    _isEwalletTopUp(order) {
        return order.lines.some((line) => {
            // Check if line is linked to an ewallet program
            // getEWalletGiftCardProgramType is defined in pos_loyalty
            if (line.getEWalletGiftCardProgramType && line.getEWalletGiftCardProgramType() === 'ewallet') {
                // It's an eWallet line. Now check if it's a top-up (positive price).
                // Usually negative price is spending (if handled as product), positive is top-up.
                // But safer to just return true if it's an ewallet line that isn't a reward?
                // In Odoo 19, top-ups are sold as products.
                return line.price_unit > 0;
            }
            return false;
        });
    },

    /**
     * Check if payment method is an eWallet type.
     * checks multiple identifiers for compatibility.
     */
    _isEwalletPaymentMethod(paymentMethod) {
        // Check by type (pos_loyalty eWallet)
        if (paymentMethod.type === 'ewallet') {
            return true;
        }

        // Scan loaded loyalty programs to see if this PM is linked?
        // (Reserved for future improvement if needed)

        // Check by code
        if (paymentMethod.code === 'ewallet') {
            return true;
        }

        // Check by name as fallback
        const name = (paymentMethod.name || '').toLowerCase();
        if (name.includes('wallet') || name.includes('ewallet') || name.includes('monedero')) {
            return true;
        }

        return false;
    },

    /**
     * Setup method to initialize payment button label tracking.
     */
    setup() {
        super.setup(...arguments);
        // Update button label after component is mounted
        onMounted(() => {
            this._updatePaymentButtonLabel();
            // Update periodically to catch order changes (fallback method)
            // This ensures the label updates even if order changes after mount
            this._labelUpdateInterval = setInterval(() => {
                this._updatePaymentButtonLabel();
            }, 500);
        });
    },

    /**
     * Cleanup interval on unmount.
     */
    onWillUnmount() {
        super.onWillUnmount?.();
        if (this._labelUpdateInterval) {
            clearInterval(this._labelUpdateInterval);
            this._labelUpdateInterval = null;
        }
    },

    /**
     * Get the payment button label.
     * Returns "Pay Gift" if order is from Gift List, otherwise "Payment".
     * This is a computed getter that can be used in templates.
     * 
     * @returns {String} Button label
     */
    get paymentButtonLabel() {
        const order = this.currentOrder;
        if (order && order.isGiftListOrder && order.isGiftListOrder()) {
            return "Pay Gift";
        }
        return "Payment";
    },

    /**
     * Update the Payment button label in the DOM.
     * This is called when order changes to update the button text dynamically.
     */
    _updatePaymentButtonLabel() {
        // Use requestAnimationFrame and setTimeout to ensure DOM is ready
        requestAnimationFrame(() => {
            setTimeout(() => {
                // In OWL components, we need to access the component's root element
                // Try multiple ways to get the element
                let rootElement = null;
                
                // Method 1: Try this.el (if available)
                if (this.el) {
                    rootElement = this.el;
                }
                // Method 2: Try document.querySelector for payment screen
                else {
                    rootElement = document.querySelector('.payment-screen, [class*="PaymentScreen"]');
                }
                // Method 3: Try finding by component structure
                if (!rootElement) {
                    // Payment screen usually has specific structure
                    rootElement = document.querySelector('.pos-content, .payment-screen-container');
                }
                
                if (!rootElement) {
                    // Don't log warning every time - only occasionally
                    if (Math.random() < 0.01) {  // Log only 1% of the time to reduce noise
                        console.warn("[MOOMBS] PaymentScreen element not found");
                    }
                    return;
                }
                
                const newLabel = this.paymentButtonLabel;
                let button = null;
                
                // Method 1: Try finding button by class
                button = rootElement.querySelector('button.payment-button, button[class*="payment"]');
                
                // Method 2: Try finding button by text content
                if (!button) {
                    const buttons = Array.from(rootElement.querySelectorAll('button'));
                    button = buttons.find(btn => {
                        const text = btn.textContent.trim();
                        return text === 'Payment' || text === 'Validate' || text === 'Pay';
                    });
                }
                
                // Method 3: Try finding the last button in the payment area (usually the Payment button)
                if (!button) {
                    const paymentArea = rootElement.querySelector('.payment-screen, .payment-controls, .payment-methods, .payment-buttons');
                    if (paymentArea) {
                        const buttons = paymentArea.querySelectorAll('button');
                        if (buttons.length > 0) {
                            // Usually the Payment button is the last one
                            button = buttons[buttons.length - 1];
                        }
                    }
                }
                
                // Method 4: Try finding button in footer
                if (!button) {
                    const footer = rootElement.querySelector('footer, .footer, .payment-footer');
                    if (footer) {
                        button = footer.querySelector('button:last-child');
                    }
                }
                
                // Method 5: Try finding by data attributes or specific IDs
                if (!button) {
                    button = rootElement.querySelector('button[data-name="validate"], button[name="validate"]');
                }
                
                if (button) {
                    const currentText = button.textContent.trim();
                    if (currentText !== newLabel) {
                        button.textContent = newLabel;
                        console.log("[MOOMBS] Payment button label updated: '%s' → '%s'", currentText, newLabel);
                    }
                }
                // Removed warning log to reduce console noise
            }, 300);
        });
    },

});
