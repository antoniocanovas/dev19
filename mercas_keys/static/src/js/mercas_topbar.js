import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { MODES, modeAction, addLineAndFocusProduct } from "./mercas_modes";

class MercasTopBar extends Component {
    static template = "mercas_keys.MercasTopBar";
    static props = { "*": true };

    setup() {
        this.modes = MODES;
        this.actionService = useService("action");
    }

    async openMode(mode) {
        await this.actionService.doAction(modeAction(mode));
    }

    addLine() {
        addLineAndFocusProduct();
    }
}

registry.category("systray").add("mercas_topbar", {
    Component: MercasTopBar,
    sequence: 1,
});
