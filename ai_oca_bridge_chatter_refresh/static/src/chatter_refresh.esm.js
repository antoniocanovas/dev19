import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";

// ai_oca_bridge's own onClickAiBridge (chatter.esm.js) only reacts to
// result.action / result.notification. A "Post a Message" result posts the
// message server-side and returns neither, so nothing tells the chatter to
// reload — same gap onPostCallback exists to close for the composer's own
// posts ("Load new messages ... due to lack of auto-sync in chatter").
// Re-run that same reload after every AI Bridge execution.
const originalOnClickAiBridge = Chatter.prototype.onClickAiBridge;

patch(Chatter.prototype, {
    async onClickAiBridge(aiBridge) {
        const result = await originalOnClickAiBridge.call(this, aiBridge);
        this.load(this.state.thread, this.afterPostRequestList);
        return result;
    },
});
