import * as spreadsheet from "@odoo/o-spreadsheet";

import {Many2XAutocomplete} from "@web/views/fields/relational_utils";
import {menuChartProps} from "./chart_panels.esm";
import {patch} from "@web/core/utils/patch";

const {chartSidePanelComponentRegistry} = spreadsheet.registries;
const {PieChartDesignPanel} = spreadsheet.components;
const {Component} = owl;

export class OdooPanel extends Component {}
// Same "link to an Odoo menu" behaviour as the patched core config panels.
patch(OdooPanel.prototype, menuChartProps());
OdooPanel.template = "spreadsheet_oca.OdooPanel";
OdooPanel.components = {Many2XAutocomplete};

class OdooStackablePanel extends OdooPanel {
    onChangeStacked(ev) {
        this.props.updateChart(this.props.chartId, {
            stacked: ev.target.checked,
        });
    }
}
OdooStackablePanel.template = "spreadsheet_oca.OdooStackablePanel";

// Odoo 19 core registers no side panel for the odoo_* chart types, but replace()
// is "add or replace" so the module stays idempotent if that ever changes.
chartSidePanelComponentRegistry.replace("odoo_line", {
    configuration: OdooStackablePanel,
    design: PieChartDesignPanel,
});
chartSidePanelComponentRegistry.replace("odoo_bar", {
    configuration: OdooStackablePanel,
    design: PieChartDesignPanel,
});
chartSidePanelComponentRegistry.replace("odoo_pie", {
    configuration: OdooPanel,
    design: PieChartDesignPanel,
});

// The odoo_* chartSubtypeRegistry entries are registered by Odoo 19 core
// (addons/spreadsheet/static/src/chart/index.js), together with the
// odoo_horizontal_bar / odoo_horizontal_stacked_bar / odoo_combo /
// odoo_doughnut subtypes. Re-registering them here would overwrite core with
// an older, narrower definition, so this module no longer does.
