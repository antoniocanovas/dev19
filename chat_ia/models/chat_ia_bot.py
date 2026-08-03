import html
import logging

from markupsafe import Markup

from odoo import models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class ChatIaBot(models.AbstractModel):
    """Detects messages addressed to the Chat IA persona in a 1:1 Discuss
    chat and posts the reply.

    Mirrors the core mail_bot module (OdooBot): discuss_channel.py hooks
    ``_message_post_after_hook`` and delegates here, exactly like
    ``discuss_channel._message_post_after_hook`` → ``mail.bot._apply_logic``
    does for base.partner_root. We use our own bot user instead of OdooBot
    so access can be gated by a dedicated group and the reply logic can be
    swapped per business module (see chat.ia.responder).
    """

    _name = "chat.ia.bot"
    _description = "Chat IA — Discuss Dispatcher"

    def _apply_logic(self, channel, values):
        channel.ensure_one()
        bot = self.env.ref("chat_ia.user_chat_ia_bot", raise_if_not_found=False)
        if not bot:
            return
        bot_partner_id = bot.partner_id.id

        # Never react to our own messages (avoids an infinite reply loop) and
        # ignore anything that isn't a plain user message (joins, leaves...).
        if values.get("author_id") == bot_partner_id:
            return
        if values.get("message_type") != "comment":
            return
        # Only 1:1 chats where the bot is actually a member — never group
        # channels or public channels, even if someone adds the bot there.
        if channel.channel_type != "chat":
            return
        if bot_partner_id not in channel.channel_member_ids.partner_id.ids:
            return

        text = html2plaintext(values.get("body") or "").strip()
        if not text:
            return

        if not self.env.user.has_group("chat_ia.group_ai_chat_user"):
            reply = self._not_authorized_reply()
        else:
            reply = self._get_reply(channel, text)

        # reply is plain text (ai.tool output, LLM output, or our own fixed
        # strings) — never raw HTML. Escape it and turn newlines into <br/>
        # before posting, same as domain_chat_mixin.py's _render_history,
        # otherwise: (a) a literal "\n\n" is invisible once rendered as HTML
        # (whitespace collapses, no visible line break), and (b) anything
        # that happens to contain "<"/">"/"&" (a partner name, raw LLM text)
        # would be interpreted as HTML instead of shown as text.
        safe_body = Markup(html.escape(reply).replace("\n", "<br/>"))

        channel.sudo().message_post(
            author_id=bot_partner_id,
            body=safe_body,
            message_type="comment",
            silent=True,
            subtype_xmlid="mail.mt_comment",
        )

    def _not_authorized_reply(self):
        """Single source of truth for the 'not in the group' message, so
        every entry point that gates on chat_ia.group_ai_chat_user (this
        Discuss hook, and mercas_ai's own wizard) says exactly the same
        thing instead of each hardcoding its own copy that can drift."""
        return self.env._(
            "No tienes habilitado este servicio, habla con tu administrador."
        )

    def _get_reply(self, channel, text):
        """Run the actual reply logic for an authorized user and persist
        the exchange. Kept separate from the group gate so a rejection
        message never touches conversation history or costs an LLM call."""
        conversation = self.env["ai.bot.conversation"].sudo().get_or_create(
            "discuss", str(channel.id), platform_user_name=self.env.user.name,
        )
        history = conversation.get_recent_messages(limit=10)
        try:
            reply = self.env["chat.ia.responder"]._get_reply(text, history)
        except Exception:
            _logger.exception(
                "chat_ia: reply generation failed on channel %s", channel.id
            )
            reply = self.env._(
                "Lo siento, ha ocurrido un error generando la respuesta. "
                "Inténtalo de nuevo."
            )
        conversation.sudo().add_message("user", text, None)
        conversation.sudo().add_message("assistant", reply, None)
        return reply
