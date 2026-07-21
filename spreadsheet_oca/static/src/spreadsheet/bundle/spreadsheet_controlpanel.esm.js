import {Component, useState, useSubEnv} from "@odoo/owl";
import {Breadcrumbs} from "@web/search/breadcrumbs/breadcrumbs";
import {ControlPanel} from "@web/search/control_panel/control_panel";

export class SpreadsheetName extends Component {
    setup() {
        this.state = useState({
            name: this.props.name,
        });
    }
    _onNameChanged(ev) {
        if (this.props.isReadonly) {
            return;
        }
        if (ev.target.value) {
            this.env.saveRecord({name: ev.target.value});
        }
        this.state.name = ev.target.value;
    }
}
SpreadsheetName.template = "spreadsheet_oca.SpreadsheetName";
SpreadsheetName.props = {
    name: String,
    isReadonly: Boolean,
};

/**
 * Standard breadcrumbs, with the last item (the current record name) replaced
 * by an editable input so the spreadsheet can be renamed in place.
 */
export class SpreadsheetBreadcrumbs extends Breadcrumbs {}
SpreadsheetBreadcrumbs.template = "spreadsheet_oca.Breadcrumbs";
SpreadsheetBreadcrumbs.components = {
    ...Breadcrumbs.components,
    SpreadsheetName,
};

export class SpreadsheetControlPanel extends ControlPanel {
    setup() {
        super.setup();
        // The standard web.ControlPanel template instantiates Breadcrumbs
        // without forwarding our own props, so the record is passed through
        // the env instead.
        useSubEnv({spreadsheetRecord: this.props.record});
    }
}
SpreadsheetControlPanel.template = "web.ControlPanel";
SpreadsheetControlPanel.props = {
    ...ControlPanel.props,
    record: Object,
};
SpreadsheetControlPanel.components = {
    ...ControlPanel.components,
    Breadcrumbs: SpreadsheetBreadcrumbs,
};
