/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Patch PosStore to handle undefined payment_ids in shouldCreatePendingOrder.
 * 
 * The shouldCreatePendingOrder method can be called with orders that have
 * undefined payment_ids during initialization, causing a TypeError.
 */
patch(PosStore.prototype, {
    /**
     * Override shouldCreatePendingOrder to safely handle undefined payment_ids.
     * 
     * @param {Object} order - The POS order to check
     * @returns {Boolean} True if a pending order should be created
     */
    shouldCreatePendingOrder(order) {
        // Safely check if order has lines
        const hasLines = order.lines && order.lines.length > 0;
        
        // Safely check if order has pay_later payments
        const hasPayLater = order.payment_ids && order.payment_ids.some(
            (p) => p.payment_method_id && p.payment_method_id.type === "pay_later"
        );
        
        return hasLines || hasPayLater;
    },
});
