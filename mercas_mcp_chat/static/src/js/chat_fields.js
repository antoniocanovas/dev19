/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useEffect, useRef } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { TextField, textField } from "@web/views/fields/text/text_field";

// Read-only chat transcript: keeps the scrollbar pinned to the bottom
// (the newest message) instead of leaving the user scrolled to the top
// after the form reloads.
export class ChatHistoryField extends Component {
    static template = "mercas_mcp_chat.ChatHistoryField";
    static props = { ...standardFieldProps };

    setup() {
        this.boxRef = useRef("box");
        useEffect(
            (el) => {
                if (el) {
                    el.scrollTop = el.scrollHeight;
                }
            },
            () => [this.value, this.boxRef.el]
        );
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("mercas_chat_history", {
    component: ChatHistoryField,
    supportedTypes: ["html"],
});

// Message input: adds Ctrl+Enter (Windows/Linux) / Cmd+Enter (macOS) as a
// shortcut for the "Enviar" button, in addition to the regular TextField
// behaviour it extends.
export class ChatMessageField extends TextField {
    setup() {
        super.setup();
        useEffect(
            (el) => {
                if (!el) {
                    return undefined;
                }
                const onKeydown = (ev) => this.onSendShortcut(ev);
                el.addEventListener("keydown", onKeydown);
                return () => el.removeEventListener("keydown", onKeydown);
            },
            () => [this.textareaRef.el]
        );
    }

    async onSendShortcut(ev) {
        if (!((ev.ctrlKey || ev.metaKey) && ev.key === "Enter")) {
            return;
        }
        ev.preventDefault();
        await this.props.record.update({ [this.props.name]: ev.target.value });
        const form = ev.target.closest(".o_form_view");
        const button = form && form.querySelector(".o_mercas_chat_send");
        if (button) {
            button.click();
        }
    }
}

registry.category("fields").add("mercas_chat_message", {
    ...textField,
    component: ChatMessageField,
});
