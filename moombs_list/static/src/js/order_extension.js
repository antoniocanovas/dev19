/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

/**
 * Extend POS Order model to support "Paid By" functionality.
 *
 * This patch adds the ability to specify a different paying customer
 * than the eWallet beneficiary. The paidByPartner is stored on the order
 * and synced to the backend for fiscal ticket generation.
 */
patch(PosOrder.prototype, {
    /**
     * Initialize custom state for the Paid By functionality.
     * Uses setup() which is the correct OWL lifecycle method in Odoo 19.
     */
    setup(vals) {
        // Initialize custom properties BEFORE calling super.setup()
        this.paidByPartner = null;
        this.popupNote = null;
        this.originalBeneficiaryId = null;
        this.topupOrderInfo = null;
        
        // Call parent setup
        super.setup(...arguments);
        
        // Capture beneficiary when partner is first set (if partner exists at setup)
        try {
            const initialPartner = this.getPartner();
            if (initialPartner && initialPartner.id) {
                this.originalBeneficiaryId = initialPartner.id;
            }
        } catch (e) {
            // Ignore errors during initialization
        }
    },

    /**
     * Set the paying customer for this order.
     * Single assignment only - once set, cannot be changed.
     * This prevents race conditions from rapid button clicks.
     * 
     * CRITICAL: Captures the current partner_id as beneficiary BEFORE any changes.
     *
     * @param {Object} partner - The partner who is paying
     */
    setPaidByPartner(partner) {
        if (this.paidByPartner) {
            // Already set - ignore subsequent attempts
            return;
        }
        // CRITICAL: Capture beneficiary NOW (before partner_id might change)
        // Store the current partner_id as the original beneficiary
        // If not already captured, capture it now
        if (!this.originalBeneficiaryId) {
            const currentPartner = this.getPartner();
            if (currentPartner && currentPartner.id) {
                this.originalBeneficiaryId = currentPartner.id;
            }
        }
        this.paidByPartner = partner;
    },
    
    /**
     * Override setPartner to capture beneficiary when partner is first set.
     * This ensures we capture the beneficiary even if setPaidByPartner is never called.
     * 
     * For Gift List orders: Capture original customer when first set (before any changes).
     */
    setPartner(partner) {
        // If originalBeneficiaryId not yet captured, capture it now
        // This is the original customer from the Sale Order (Gift List beneficiary)
        if (!this.originalBeneficiaryId && partner && partner.id) {
            this.originalBeneficiaryId = partner.id;
            console.log("[MOOMBS] Captured original beneficiary ID:", partner.id, partner.name);
        }
        return super.setPartner(...arguments);
    },

    /**
     * Clear the paid by partner selection.
     * Used when order is reset or cancelled.
     */
    clearPaidByPartner() {
        this.paidByPartner = null;
        this.originalBeneficiaryId = null;
    },

    /**
     * Set the note from the popup.
     * This note will be added to order lines.
     *
     * @param {String} note - The note text
     */
    setPopupNote(note) {
        this.popupNote = note;
    },

    /**
     * Override serializeForORM to include paid_by_partner_id and ewallet_beneficiary_id in the payload.
     * This ensures the data is synced to the backend.
     * Also adds popup note to order lines.
     * 
     * For Gift List orders: If customer is changed at payment screen, update paid_by_partner_id.
     */
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);

        // For Gift List orders: Check if customer was changed at payment screen
        // If partner_id differs from original beneficiary, set paid_by_partner_id
        if (this.isGiftListOrder && this.isGiftListOrder()) {
            const currentPartner = this.getPartner();
            const originalBeneficiaryId = this.originalBeneficiaryId;
            
            // If customer was changed (current partner != original beneficiary)
            if (currentPartner && originalBeneficiaryId && currentPartner.id !== originalBeneficiaryId) {
                // Set paid_by_partner_id to current partner (payer)
                data.paid_by_partner_id = currentPartner.id;
                // Set ewallet_beneficiary_id to original beneficiary (wallet owner)
                data.ewallet_beneficiary_id = originalBeneficiaryId;
                console.log("[MOOMBS] Gift List: Customer changed - Payer:", currentPartner.id, "Wallet Owner:", originalBeneficiaryId);
            } else if (currentPartner && currentPartner.id) {
                // Same customer, but ensure beneficiary is set
                data.ewallet_beneficiary_id = currentPartner.id;
                if (!data.paid_by_partner_id) {
                    data.paid_by_partner_id = currentPartner.id;
                }
            }
        }

        // Include paid_by_partner_id and ewallet_beneficiary_id in the payload (for wallet top-ups)
        // CRITICAL: Add defensive checks to prevent undefined errors
        if (this.paidByPartner && this.paidByPartner.id) {
            data.paid_by_partner_id = this.paidByPartner.id;
            // CRITICAL: Use stored originalBeneficiaryId (captured when setPaidByPartner was called)
            // Fallback to current partner if not stored (for backward compatibility)
            let beneficiaryId = this.originalBeneficiaryId;
            if (!beneficiaryId) {
                // Use getPartner() instead of this.partner_id (which might be a number)
                const currentPartner = this.getPartner();
                beneficiaryId = currentPartner ? currentPartner.id : null;
            }
            if (beneficiaryId) {
                data.ewallet_beneficiary_id = beneficiaryId;
            }
        } else if (!data.paid_by_partner_id) {
            // Even if no paidByPartner, send beneficiary_id for consistency
            const currentPartner = this.getPartner();
            if (currentPartner && currentPartner.id) {
                data.ewallet_beneficiary_id = currentPartner.id;
            }
        }

        // Add popup note to all order lines if note is set
        // CRITICAL: Only modify lines if note exists, and preserve all original properties
        // IMPORTANT: Be very careful not to break line structure that Odoo expects
        // NOTE: During down payment processing, lines might have special structure - handle carefully
        if (this.popupNote && data.lines && Array.isArray(data.lines)) {
            data.lines = data.lines.map(line => {
                try {
                    // line can be [0, 0, {...}] or just {...}
                    if (Array.isArray(line) && line.length >= 3) {
                        // Format: [0, 0, {...}]
                        // CRITICAL: Ensure line[2] exists and is an object
                        // Preserve all original properties to avoid breaking Odoo's down payment processing
                        const lineData = line[2];
                        if (lineData && typeof lineData === 'object' && lineData !== null && !Array.isArray(lineData)) {
                            // Create a copy to avoid mutating the original
                            // Use Object.assign to preserve all properties including non-enumerable ones
                            const newLineData = Object.assign({}, lineData);
                            newLineData.customer_note = this.popupNote;
                            // CRITICAL: Preserve line[0] and line[1] exactly as they are
                            // Ensure they exist before using them
                            if (line[0] !== undefined && line[1] !== undefined) {
                                return [line[0], line[1], newLineData];
                            }
                            // If line[0] or line[1] are missing, return original
                            return line;
                        }
                        // If line[2] is invalid, return original line unchanged
                        return line;
                    } else if (typeof line === 'object' && line !== null && !Array.isArray(line)) {
                        // Format: {...}
                        // Create a copy to avoid mutating the original
                        // Use Object.assign to preserve all properties
                        const newLine = Object.assign({}, line);
                        newLine.customer_note = this.popupNote;
                        return newLine;
                    }
                    // If line structure is unexpected, return as-is
                    return line;
                } catch (error) {
                    // If anything goes wrong, return original line to prevent breaking Odoo's processing
                    console.warn("[order_extension] Error adding note to line:", error);
                    return line;
                }
            });
        }

        return data;
    },

    /**
     * Get display name of paying customer.
     * Returns null if same as order partner or not set.
     */
    getPaidByDisplayName() {
        if (!this.paidByPartner || !this.paidByPartner.id) {
            return null;
        }
        const orderPartner = this.getPartner();
        if (orderPartner && this.paidByPartner.id === orderPartner.id) {
            return null;
        }
        return this.paidByPartner.name;
    },

    /**
     * Compatibility shim for enterprise modules (like pos_settle_due)
     * that call getChange() as a function, while Odoo 19 core
     * implements it as a getter 'change'.
     */
    getChange() {
        return this.change;
    },

    /**
     * Check if this order is from a Gift List (has Sale Order linked).
     * Used to determine if wallet intermediary flow should be used.
     * 
     * @returns {Boolean} True if order is from Gift List
     */
    isGiftListOrder() {
        // Check if order has sale_order_ids (if pos_sale module is installed)
        if (this.sale_order_ids && this.sale_order_ids.length > 0) {
            return true;
        }
        
        // Check if any line has sale_order_origin_id (for downpayments)
        if (this.orderlines && this.orderlines.length > 0) {
            for (const line of this.orderlines) {
                if (line.sale_order_origin_id) {
                    return true;
                }
                if (line.sale_order_line_id && line.sale_order_line_id.order) {
                    return true;
                }
            }
        }
        
        return false;
    },

    /**
     * Two-Order Flow: Store topup order info for receipt display.
     * Called after backend creates the topup order.
     * 
     * @param {Object} topupInfo - Contains topup_order_id, topup_order_name, amount, etc.
     */
    setTopupOrderInfo(topupInfo) {
        this.topupOrderInfo = topupInfo;
        console.log("[MOOMBS] Stored topup order info:", topupInfo);
    },

    /**
     * Get topup order name for receipt display.
     * @returns {String|null} Topup order name or null
     */
    get topupOrderName() {
        if (this.topupOrderInfo && this.topupOrderInfo.topup_order_name) {
            return this.topupOrderInfo.topup_order_name;
        }
        // Fallback to loaded data from backend
        if (this.topup_order_id && this.topup_order_id.name) {
            return this.topup_order_id.name;
        }
        return null;
    },

    /**
     * Get topup order amount for receipt display.
     * @returns {Number|null} Topup amount or null
     */
    get topupOrderAmount() {
        if (this.topupOrderInfo && this.topupOrderInfo.amount) {
            return this.topupOrderInfo.amount;
        }
        // Fallback to loaded data from backend
        if (this.topup_order_id && this.topup_order_id.amount_total) {
            return this.topup_order_id.amount_total;
        }
        return null;
    },

    /**
     * Get paid by partner name for receipt display.
     * @returns {String|null} Payer name or null
     */
    get paidByPartnerName() {
        if (this.paidByPartner && this.paidByPartner.name) {
            return this.paidByPartner.name;
        }
        if (this.paid_by_partner_id && this.paid_by_partner_id.name) {
            return this.paid_by_partner_id.name;
        }
        return null;
    },

    /**
     * Get topup payment method name for receipt display.
     * @returns {String|null} Payment method name or null
     */
    get topupPaymentMethod() {
        if (this.topupOrderInfo && this.topupOrderInfo.payment_method) {
            return this.topupOrderInfo.payment_method;
        }
        return null;
    },

    /**
     * Check if this is a settlement order (has linked topup order).
     * @returns {Boolean} True if settlement order
     */
    isSettlementOrder() {
        return !!(this.topup_order_id || this.topupOrderInfo);
    },
});


