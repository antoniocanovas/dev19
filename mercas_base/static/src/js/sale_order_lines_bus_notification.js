import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onWillUnmount, useEffect } from "@odoo/owl";

const NOTIFICATION_TYPE = "mercas_sale_order_lines_updated";

function busChannel(resId) {
    return `mercas_sale_order_lines-${resId}`;
}

patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel !== "sale.order") {
            return;
        }

        const busService = useService("bus_service");
        const notificationService = useService("notification");

        useEffect(
            (resId) => {
                if (!resId) {
                    return;
                }
                const channel = busChannel(resId);
                busService.addChannel(channel);
                return () => busService.deleteChannel(channel);
            },
            () => [this.model.root.resId]
        );

        const onLinesUpdated = (payload) => {
            const resId = this.model.root.resId;
            if (!resId || payload.order_id !== resId) {
                return;
            }
            if (payload.user_id === user.userId) {
                return;
            }
            notificationService.add(
                _t(
                    "%(user)s ha modificado las líneas de este pedido. Haz clic aquí para recargar.",
                    { user: payload.user_name }
                ),
                {
                    title: _t("Pedido actualizado"),
                    type: "warning",
                    sticky: true,
                    buttons: [
                        {
                            name: _t("Recargar"),
                            primary: true,
                            onClick: () => this.model.load(),
                        },
                    ],
                }
            );
        };

        busService.subscribe(NOTIFICATION_TYPE, onLinesUpdated);
        onWillUnmount(() => busService.unsubscribe(NOTIFICATION_TYPE, onLinesUpdated));
    },
});
