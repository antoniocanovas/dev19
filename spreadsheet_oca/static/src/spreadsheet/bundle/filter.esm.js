import * as spreadsheet from "@odoo/o-spreadsheet";
import {Component, onWillStart, useState} from "@odoo/owl";
import {
    getDefaultValue,
    getEmptyFilterValue,
    getFilterTypeOperators,
    globalFieldMatchingRegistry,
    isSetOperator,
} from "@spreadsheet/global_filters/helpers";
import {DefaultDateValue} from "@spreadsheet/global_filters/components/default_date_value/default_date_value";
import {Domain} from "@web/core/domain";
import {DomainSelector} from "@web/core/domain_selector/domain_selector";
import {DomainSelectorDialog} from "@web/core/domain_selector_dialog/domain_selector_dialog";
import {FilterValue} from "@spreadsheet/global_filters/components/filter_value/filter_value";
import {ModelFieldSelector} from "@web/core/model_field_selector/model_field_selector";
import {ModelSelector} from "@web/core/model_selector/model_selector";
import {MultiRecordSelector} from "@web/core/record_selectors/multi_record_selector";
import {TextFilterValue} from "@spreadsheet/global_filters/components/filter_text_value/filter_text_value";
const {Checkbox} = spreadsheet.components;
import {user} from "@web/core/user";

import {_t} from "@web/core/l10n/translation";
import {getOperatorLabel} from "@web/core/tree_editor/tree_editor_operator_editor";
import {useService} from "@web/core/utils/hooks";

const {topbarMenuRegistry} = spreadsheet.registries;
const uuidGenerator = new spreadsheet.helpers.UuidGenerator();

// "file" menu is already registered by o-spreadsheet core in Odoo 19
topbarMenuRegistry.addChild("filters", ["file"], {
    name: _t("Filters"),
    sequence: 70,
    execute: (env) => env.openSidePanel("FilterPanel", {}),
    icon: "o-spreadsheet-Icon.GLOBAL_FILTERS",
});
topbarMenuRegistry.addChild("save", ["file"], {
    name: _t("Save"),
    sequence: 10,
    execute: (env) => env.saveSpreadsheet(),
    icon: "o-spreadsheet-Icon.DOWNLOAD",
});
topbarMenuRegistry.addChild("download", ["file"], {
    name: _t("Download XLSX"),
    sequence: 20,
    execute: (env) => env.downloadAsXLXS(),
    icon: "o-spreadsheet-Icon.EXPORT_XLSX",
});

const {sidePanelRegistry} = spreadsheet.registries;

export class FilterPanel extends Component {
    onEditFilter(filter) {
        this.env.openSidePanel("EditFilterPanel", {filter});
    }
    onAddFilter(type) {
        this.env.openSidePanel("EditFilterPanel", {filter: {type: type}});
    }
    getFilterValue(filterId) {
        return this.env.model.getters.getGlobalFilterValue(filterId);
    }
    setFilterValue(id, value) {
        this.env.model.dispatch("SET_GLOBAL_FILTER_VALUE", {id, value});
    }
}

FilterPanel.template = "spreadsheet_oca.FilterPanel";
FilterPanel.components = {
    FilterValue,
};

// replace() is "add or replace", so this works whether or not the key exists.
sidePanelRegistry.replace("FilterPanel", {title: "Filters", Body: FilterPanel});

export class EditFilterPanel extends Component {
    setup() {
        this.filterId = this.props.filter.id;
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        const filter = this.props.filter;
        const defaultValue = filter.defaultValue;
        this.state = useState({
            label: filter.label,
            type: filter.type,
            // Since 19.0 a filter value is operator based: the operator drives
            // which value key ("ids" or "strings") is meaningful. Both are kept
            // in the state so switching operators back and forth is lossless.
            operator: defaultValue?.operator || getDefaultValue(filter.type)?.operator,
            ids: defaultValue?.ids ?? [],
            strings: defaultValue?.strings ?? [],
            // Date filters keep a plain string default ("this_month", ...)
            dateDefaultValue: filter.type === "date" ? defaultValue : undefined,
            modelData: {technical: filter.modelName, label: null},
            objects: {},
            domainOfAllowedValues: filter.domainOfAllowedValues,
            valuesRestricted: Boolean(filter.domainOfAllowedValues?.length),
        });
        onWillStart(this.willStart.bind(this));
    }
    async willStart() {
        const getters = this.env.model.getters;
        if (this.state.modelData.technical) {
            const modelLabel = await this.orm.call("ir.model", "display_name_for", [
                [this.state.modelData.technical],
            ]);
            this.state.modelData.label = modelLabel[0] && modelLabel[0].display_name;
        }
        const ModelFields = [];
        for (const [objectType, matcher] of globalFieldMatchingRegistry.getEntries()) {
            for (const objectId of matcher.getIds(getters)) {
                const fields = matcher.getFields(getters, objectId);
                this.state.objects[objectType + "_" + objectId] = {
                    id: objectType + "_" + objectId,
                    objectId: objectId,
                    name: matcher.getDisplayName(getters, objectId),
                    tag: await matcher.getTag(getters, objectId),
                    fieldMatch:
                        matcher.getFieldMatching(getters, objectId, this.props.filter.id) ||
                        {},
                    fields: fields,
                    type: objectType,
                    model: matcher.getModel(getters, objectId),
                };
                ModelFields.push(fields);
            }
        }
        this.models = [
            ...new Set(
                ModelFields.map((field_items) => Object.values(field_items))
                    .flat()
                    .filter((field) => field.relation)
                    .map((field) => field.relation)
            ),
        ];
    }
    get operators() {
        if (this.state.type === "date") {
            return [];
        }
        return getFilterTypeOperators(this.state.type);
    }
    operatorLabel(operator) {
        return getOperatorLabel(operator);
    }
    /**
     * The value key expected by the current operator: "ids", "strings", or
     * undefined for the "set"/"not set" operators, which carry no value.
     *
     * @returns {string | undefined}
     */
    get valueKey() {
        if (this.state.type === "date" || isSetOperator(this.state.operator)) {
            return undefined;
        }
        const emptyValue = getEmptyFilterValue(
            {type: this.state.type},
            this.state.operator
        );
        return "ids" in emptyValue ? "ids" : "strings";
    }
    /**
     * Build the default value in the shape expected by Odoo 19.
     *
     * @returns {Object | string | undefined}
     */
    buildDefaultValue() {
        if (this.state.type === "date") {
            return this.state.dateDefaultValue || undefined;
        }
        const operator = this.state.operator;
        const key = this.valueKey;
        if (!key) {
            // "set" / "not set" are fully described by their operator
            return {operator};
        }
        const value = this.state[key];
        if (value === "current_user") {
            return {operator, ids: "current_user"};
        }
        // Empty values are rejected by the validators, so an empty input means
        // "no default value at all" rather than an empty one.
        if (!value?.length) {
            return undefined;
        }
        return {operator, [key]: value};
    }
    get dateOffset() {
        return [
            {value: 0, name: ""},
            {value: -1, name: _t("Previous")},
            {value: -2, name: _t("Before Previous")},
            {value: 1, name: _t("Next")},
            {value: 2, name: _t("After next")},
        ];
    }
    onChangeFieldMatchOffset(object, ev) {
        this.state.objects[object.id].fieldMatch.offset = parseInt(ev.target.value, 10);
    }
    async onModelSelected(ev) {
        this.state.modelData.technical = ev.technical;
        this.state.modelData.label = ev.label;
        this.state.ids = [];
        this.state.domainOfAllowedValues = [];
    }
    onRecordsSelected(resIds) {
        this.state.ids = resIds;
    }
    onTextValuesChanged(strings) {
        this.state.strings = strings;
    }
    onDateDefaultValueChanged(value) {
        this.state.dateDefaultValue = value;
    }
    onUpdateDomain(domain) {
        this.state.domainOfAllowedValues = domain;
    }
    getCorrectDomain() {
        const domain = this.state.domainOfAllowedValues;
        if (domain) {
            return new Domain(domain).toList(user.context);
        }
        return [];
    }
    changeDomainRestriction(value) {
        this.state.valuesRestricted = value;
        this.state.domainOfAllowedValues = [];
    }
    editDomain() {
        this.dialog.add(DomainSelectorDialog, {
            resModel: this.state.modelData.technical,
            domain: this.getCorrectDomain(),
            readonly: false,
            isDebugMode: Boolean(this.env.debug),
            onConfirm: this.onUpdateDomain.bind(this),
        });
    }
    onSave() {
        const action = this.props.filter.id
            ? "EDIT_GLOBAL_FILTER"
            : "ADD_GLOBAL_FILTER";

        const filter = {
            id: this.props.filter.id || uuidGenerator.uuidv4(),
            type: this.state.type,
            label: this.state.label || "",
            defaultValue: this.buildDefaultValue(),
        };
        if (this.state.type === "relation") {
            filter.modelName = this.state.modelData.technical;
            filter.domainOfAllowedValues = this.state.domainOfAllowedValues;
        }
        const filterMatching = {};
        Object.values(this.state.objects).forEach((object) => {
            filterMatching[object.type] = filterMatching[object.type] || {};
            const fieldMatch = object.fieldMatch ? {...object.fieldMatch} : {};
            filterMatching[object.type][object.objectId] = fieldMatch;
        });
        this.env.model.dispatch(action, {
            filter,
            ...filterMatching,
        });
        this.env.openSidePanel("FilterPanel", {});
    }
    onCancel() {
        this.env.openSidePanel("FilterPanel", {});
    }
    onRemove() {
        if (this.props.filter.id) {
            this.env.model.dispatch("REMOVE_GLOBAL_FILTER", {
                id: this.props.filter.id,
            });
        }
        this.env.openSidePanel("FilterPanel", {});
    }
    onFieldMatchUpdate(object, path, fieldInfo) {
        if (!path) {
            // Clear the field match if no path selected
            this.state.objects[object.id].fieldMatch = {};
            return;
        }
        this.state.objects[object.id].fieldMatch = {
            chain: path,
            type: fieldInfo?.fieldDef?.type || "",
        };
    }
    getModelField(fieldMatch) {
        if (!fieldMatch || !fieldMatch.chain) {
            return "";
        }
        return fieldMatch.chain;
    }
    filterModelFieldSelectorField(field, path, coModel) {
        if (!field.searchable) {
            return false;
        }

        // TODO: Define allowed field types based on filter type
        const ALLOWED_FIELD_TYPES = [
            "char",
            "text",
            "selection",
            "many2one",
            "date",
            "datetime",
        ];

        if (field.name === "id" && this.state.type === "relation") {
            const paths = path.split(".");
            const lastField = paths.at(-2);
            if (!lastField || (lastField.relation && lastField.relation === coModel)) {
                return true;
            }
            return false;
        }
        return ALLOWED_FIELD_TYPES.includes(field.type) || Boolean(field.relation);
    }
}

EditFilterPanel.template = "spreadsheet_oca.EditFilterPanel";
EditFilterPanel.components = {
    Checkbox,
    DefaultDateValue,
    DomainSelector,
    ModelSelector,
    ModelFieldSelector,
    MultiRecordSelector,
    TextFilterValue,
};

sidePanelRegistry.replace("EditFilterPanel", {
    title: "Edit Filter",
    Body: EditFilterPanel,
});
