import * as spreadsheet from "@odoo/o-spreadsheet";
import {Many2XAutocomplete} from "@web/views/fields/relational_utils";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

const {
    GenericChartConfigPanel,
    LineConfigPanel,
    BarConfigPanel,
    ScorecardChartConfigPanel,
    GaugeChartConfigPanel,
} = spreadsheet.components;

export const menuChartProps = () => ({
    setup() {
        super.setup(...arguments);
        this.menus = useService("menu");
    },
    get menuProps() {
        return {
            fieldString: _t("Menu Items"),
            resModel: "ir.ui.menu",
            update: this.updateMenu.bind(this),
            activeActions: {},
            getDomain: this.getDomain.bind(this),
            placeholder: _t("Select a menu..."),
            value: this.menuId ? this.menuId[1] : "",
        };
    },

    getDomain() {
        const menus = this.menus
            .getAll()
            .map((menu) => menu.id)
            .filter((menuId) => menuId !== "root");
        return [["id", "in", menus]];
    },
    get menuId() {
        const menu = this.env.model.getters.getChartOdooMenu(this.props.chartId);
        if (menu) {
            return [menu.id, menu.name];
        }
        return false;
    },
    updateMenu(menuId) {
        if (!menuId) {
            this.env.model.dispatch("LINK_ODOO_MENU_TO_CHART", {
                chartId: this.props.chartId,
                odooMenuId: false,
            });
            return;
        }
        const menu = this.env.model.getters.getIrMenu(menuId[0].id);
        this.env.model.dispatch("LINK_ODOO_MENU_TO_CHART", {
            chartId: this.props.chartId,
            odooMenuId: menu.xmlid || menu.id,
        });
    },
});

for (const Panel of [
    GenericChartConfigPanel,
    LineConfigPanel,
    BarConfigPanel,
    ScorecardChartConfigPanel,
    GaugeChartConfigPanel,
]) {
    patch(Panel.prototype, menuChartProps());
    Panel.components = {...Panel.components, Many2XAutocomplete};
}
