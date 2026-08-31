import {Component, markup} from "@odoo/owl";
import {usePopover} from "@web/core/popover/popover_hook";

export class ChatterAIItemPopover extends Component {
    static template = "ai_oca_bridge.ChatterAIItemPopover";
}

export class ChatterAIItem extends Component {
    static template = "ai_oca_bridge.ChatterAIItem";
    static props = {bridge: Object};

    setup() {
        super.setup();
        this.popover = usePopover(ChatterAIItemPopover, {
            closeOnClickAway: true,
            position: "top",
        });
    }
    get tooltipInfo() {
        return {
            help: markup(this.props.bridge.description || ""),
        };
    }
    onMouseEnter(ev) {
        this.popover.open(ev.currentTarget, this.tooltipInfo);
    }

    onMouseLeave() {
        this.closeTooltip();
    }

    closeTooltip() {
        this.popover.close();
    }
}
