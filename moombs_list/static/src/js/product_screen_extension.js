/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { _t } from "@web/core/l10n/translation";

/**
 * Extend ProductScreen to validate wallet before adding eWallet top-up products.
 * 
 * When user tries to add an eWallet top-up product:
 * 1. Check if order has a partner (beneficiary)
 * 2. Check if beneficiary has a wallet
 * 3. If no wallet, show alert and prevent adding product
 */
patch(ProductScreen.prototype, {
    
    /**
     * Override clickProduct to intercept eWallet top-up product addition.
     * Validates beneficiary has wallet before allowing product to be added.
     */
    async clickProduct(event) {
        const product = event.detail;
        
        // Check if this is an eWallet top-up product
        const isEwalletTopUp = this._isEwalletTopUpProduct(product);
        
        if (isEwalletTopUp) {
            const order = this.pos.get_order();
            const partner = order ? order.getPartner() : null;
            
            // Must have a partner (beneficiary)
            if (!partner) {
                this._showError(
                    _t("Customer Required"),
                    _t("Please select a customer before adding eWallet top-up products.")
                );
                return;
            }
            
            // Check if beneficiary has a wallet
            const hasWallet = await this._checkPartnerHasWallet(partner);
            
            if (!hasWallet) {
                this._showError(
                    _t("Wallet Required"),
                    _t("Customer '%s' does not have an eWallet. Please create a wallet for this customer first.")
                        .replace('%s', partner.name)
                );
                return;
            }
        }
        
        // Continue with normal product addition
        return super.clickProduct(...arguments);
    },
    
    /**
     * Check if a product is an eWallet top-up product.
     * 
     * @param {Object} product - The product to check
     * @returns {Boolean} True if product is eWallet top-up
     */
    _isEwalletTopUpProduct(product) {
        if (!product) {
            return false;
        }
        
        // Check if product is linked to an eWallet program
        // In Odoo 19, eWallet top-ups are products linked to loyalty programs via rewards
        const programs = this.pos.programs || [];
        const ewalletPrograms = programs.filter(p => 
            p.program_type === 'ewallet' && 
            p.trigger === 'auto'
        );
        
        // Check if product is in any eWallet program's reward products
        for (const program of ewalletPrograms) {
            if (program.reward_ids) {
                for (const reward of program.reward_ids) {
                    if (reward.reward_type === 'product' && reward.reward_product_id) {
                        if (reward.reward_product_id.id === product.id) {
                            return true;
                        }
                    }
                }
            }
        }
        
        // Fallback: Check product name/category for eWallet indicators
        const name = (product.name || '').toLowerCase();
        if (name.includes('wallet') || name.includes('ewallet') || name.includes('top-up') || name.includes('topup')) {
            return true;
        }
        
        return false;
    },
    
    /**
     * Check if a partner has an eWallet.
     * 
     * @param {Object} partner - The partner to check
     * @returns {Promise<Boolean>} True if partner has wallet
     */
    async _checkPartnerHasWallet(partner) {
        if (!partner || !partner.id) {
            return false;
        }
        
        // Get eWallet programs from POS
        const programs = this.pos.programs || [];
        const ewalletPrograms = programs.filter(p => 
            p.program_type === 'ewallet' && 
            p.trigger === 'auto'
        );
        
        if (ewalletPrograms.length === 0) {
            // No eWallet program configured
            return false;
        }
        
        // Check if partner has a wallet card for any eWallet program
        // In Odoo 19 POS, loyalty cards are loaded in pos.loyalty_programs
        const loyaltyCards = this.pos.loyalty_programs || [];
        
        for (const program of ewalletPrograms) {
            // Check if partner has a card for this program
            const partnerCard = loyaltyCards.find(card => 
                card.partner_id && 
                (card.partner_id.id === partner.id || card.partner_id === partner.id) &&
                card.program_id && 
                (card.program_id.id === program.id || card.program_id === program.id)
            );
            
            if (partnerCard) {
                return true;
            }
        }
        
        // If not found in loaded cards, make RPC call to backend
        try {
            // Check if pos.orm exists (might not be available in all contexts)
            if (!this.pos.orm || !this.pos.orm.call) {
                console.warn("[ProductScreen] pos.orm not available, skipping wallet check");
                // Fail closed: require wallet to be in loaded cards
                return false;
            }
            
            const result = await this.pos.orm.call(
                'loyalty.card',
                'search_count',
                [[
                    ('partner_id', '=', partner.id),
                    ('program_id.program_type', '=', 'ewallet'),
                    ('program_id.trigger', '=', 'auto'),
                ]],
                { limit: 1 }
            );
            return result > 0;
        } catch (error) {
            console.error("[ProductScreen] Error checking wallet:", error);
            // On error, fail closed: don't allow product addition without wallet confirmation
            return false;
        }
    },
    
    /**
     * Show error dialog.
     * 
     * @param {String} title - Error title
     * @param {String} message - Error message
     */
    _showError(title, message) {
        // Use browser alert as simple error display
        alert(`${title}\n\n${message}`);
    },
});

