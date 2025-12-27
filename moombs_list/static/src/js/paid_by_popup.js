/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * PaidByPopup - OWL Component for selecting the paying customer.
 *
 * Props:
 *   - beneficiary: The eWallet holder (res.partner object)
 *   - close: Callback function to close the popup (injected by makeAwaitable)
 *
 * State:
 *   - selectedPartner: The chosen paying partner
 *   - searchTerm: Current search input value
 *   - filteredPartners: List of partners matching search
 */
export class PaidByPopup extends Component {
    static template = "moombs_list.PaidByPopup";
    static props = {
        beneficiary: Object,
        close: Function,
        getPayload: { type: Function, optional: true },
    };

    setup() {
        this.pos = usePos();
        this.searchInputRef = useRef("searchInput");
        this.noteInputRef = useRef("noteInput");

        this.state = useState({
            searchTerm: "",
            selectedPartner: null,
            filteredPartners: this._getInitialPartners(),
            note: "",
        });

        // Auto-focus search input on mount
        onMounted(() => {
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        });
    }

    /**
     * Get all partners from the POS models.
     * Odoo 19 pattern: use this.pos.models["model.name"].getAll()
     */
    _getAllPartners() {
        return this.pos.models["res.partner"].getAll();
    }

    /**
     * Get initial partners to display (limited to 8).
     */
    _getInitialPartners() {
        const partners = this._getAllPartners();
        return partners.slice(0, 8);
    }

    /**
     * Handle note input changes.
     */
    onNoteInput(event) {
        this.state.note = event.target.value;
    }

    /**
     * Handle search input changes.
     * Filters partners client-side using Odoo 19 model access.
     */
    onSearchInput(event) {
        const searchTerm = event.target.value.trim();
        this.state.searchTerm = searchTerm;

        if (searchTerm.length < 2) {
            this.state.filteredPartners = this._getInitialPartners();
            return;
        }

        // Filter partners client-side
        const partners = this._getAllPartners();
        const searchLower = searchTerm.toLowerCase();

        const results = partners.filter(p =>
            (p.name && p.name.toLowerCase().includes(searchLower)) ||
            (p.phone && p.phone.includes(searchTerm)) ||
            (p.email && p.email.toLowerCase().includes(searchLower)) ||
            (p.vat && p.vat.toLowerCase().includes(searchLower))
        );

        this.state.filteredPartners = results.slice(0, 8);
    }

    /**
     * Partners to display in the list.
     */
    get displayedPartners() {
        return this.state.filteredPartners;
    }

    /**
     * Check if search is active with no results.
     */
    get noResults() {
        return this.state.searchTerm.length >= 2 &&
               this.state.filteredPartners.length === 0;
    }

    /**
     * Select a partner as the payer.
     */
    selectPartner(partner) {
        this.state.selectedPartner = partner;
    }

    /**
     * Check if a partner is currently selected.
     */
    isSelected(partner) {
        return this.state.selectedPartner &&
               this.state.selectedPartner.id === partner.id;
    }

    /**
     * Confirm selection and close popup.
     * Returns the selected partner and note to the caller.
     */
    confirm() {
        if (!this.state.selectedPartner) {
            return;
        }
        const payload = {
            partner: this.state.selectedPartner,
            note: this.state.note,
        };
        if (this.props.getPayload) {
            this.props.getPayload(payload);
        }
        this.props.close(payload);
    }

    /**
     * Skip selection - use wallet owner as payer.
     * Returns null to indicate no different payer, but includes note.
     */
    skipSelection() {
        const payload = {
            partner: null,
            note: this.state.note,
        };
        if (this.props.getPayload) {
            this.props.getPayload(payload);
        }
        this.props.close(payload);
    }

    /**
     * Handle keyboard navigation.
     */
    onKeydown(event) {
        if (event.key === "Escape") {
            this.skipSelection();
        } else if (event.key === "Enter" && this.state.selectedPartner) {
            this.confirm();
        }
    }

    /**
     * Format partner display with VAT if available.
     */
    formatPartnerInfo(partner) {
        if (partner.vat) {
            return `${partner.name} - ${partner.vat}`;
        }
        return partner.name;
    }
}

// Register the popup in the POS popups registry
registry.category("pos_popups").add("PaidByPopup", PaidByPopup);
