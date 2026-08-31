import json
import logging

from odoo import api, http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)

WIKI_CATEGORY_NAME = "wiki"


def _check_token(data):
    expected = (
        request.env["ir.config_parameter"]
        .sudo()
        .get_param("document_page_rag_bridge.n8n_shared_secret")
    )
    return expected and consteq(data.get("token") or "", expected)


def _error(message, status=403):
    return request.make_response(
        json.dumps({"error": message}),
        status=status,
        headers=[("Content-Type", "application/json")],
    )


class RagBridgeController(http.Controller):
    @http.route(
        "/rag_bridge/upsert_entity_page",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def upsert_entity_page(self, **kwargs):
        """Search-or-create (or, for 'dispositivo', search-or-update) a wiki
        note for one entity of the Karpathy hierarchy: fabricante, familia,
        or dispositivo.

        Dedup here is by an exact key (rag_entity_type + rag_key), not fuzzy
        embedding similarity — a "Yamaha" manufacturer note is reused as-is
        across every device that names it, instead of a new near-duplicate
        note per document. A 'dispositivo' note with no matching key is
        created; a matching one gets the new technical content appended
        instead of spawning a sibling note for the same device.

        Body: {token, entity_type, key, title, content, mode,
               part_number?, fabricante_page_id?, familia_page_id?,
               source_page_id}
        mode: "append" (dispositivo — merge new detail into the existing
              note) or "create_only" (fabricante/familia — reused as-is,
              content never rewritten by a later document).
        Response: {page_id, created}
        """
        data = json.loads(request.httprequest.get_data() or b"{}")
        if not _check_token(data):
            return _error("invalid or missing token")

        entity_type = data.get("entity_type")
        key = (data.get("key") or "").strip()
        if entity_type not in ("fabricante", "familia", "dispositivo"):
            return _error("invalid entity_type", status=400)
        if not key:
            # Optional entity (e.g. no fabricante mentioned in this
            # document) — nothing to do, not an error.
            return request.make_response(
                json.dumps({"page_id": None, "created": False}),
                headers=[("Content-Type", "application/json")],
            )

        Page = request.env["document.page"].sudo()
        wiki_category = Page.search(
            [("name", "=", WIKI_CATEGORY_NAME), ("type", "=", "category")], limit=1
        )
        if not wiki_category:
            return _error("wiki category not found", status=404)

        reference = f"{entity_type}_{key}"
        title = (data.get("title") or "").strip() or "Nota sin título"
        content = data.get("content") or ""
        mode = data.get("mode") or "create_only"
        source_page_id = data.get("source_page_id")

        existing = Page.search(
            [("rag_entity_type", "=", entity_type), ("rag_key", "=", key)], limit=1
        )
        if existing:
            if mode == "append" and content:
                separator = (
                    "<hr/><p><em>Información añadida desde otro documento"
                    "</em></p>"
                )
                existing.write(
                    {
                        # existing.content is a markupsafe.Markup instance —
                        # Markup + plain str auto-HTML-escapes the plain str
                        # operand (XSS protection), which would silently
                        # mangle the new HTML into literal "&lt;h4&gt;" text.
                        # str() first to concatenate as plain strings.
                        "content": str(existing.content or "") + separator + content,
                        "rag_source_page_id": source_page_id or existing.rag_source_page_id.id,
                    }
                )
            return request.make_response(
                json.dumps({"page_id": existing.id, "created": False}),
                headers=[("Content-Type", "application/json")],
            )

        vals = {
            "name": title,
            "type": "content",
            "parent_id": wiki_category.id,
            "content": content,
            "reference": reference,
            "rag_entity_type": entity_type,
            "rag_key": key,
        }
        if data.get("part_number"):
            vals["rag_part_number"] = data["part_number"]
        if data.get("fabricante_page_id"):
            vals["rag_fabricante_id"] = int(data["fabricante_page_id"])
        if data.get("familia_page_id"):
            vals["rag_familia_id"] = int(data["familia_page_id"])
        if source_page_id:
            source_page = Page.browse(int(source_page_id))
            if source_page.exists():
                vals["rag_source_page_id"] = source_page.id

        # Two devices in the same document (or two concurrent uploads) can
        # both pass the search-or-create check above before either commits —
        # a real race, not hypothetical (hit it testing a 2-device catalog).
        # The DB-level unique constraint on (rag_entity_type, rag_key) turns
        # the loser's create() into a catchable IntegrityError instead of a
        # silent duplicate; on conflict, just return the winner's record.
        try:
            with request.env.cr.savepoint():
                page = Page.create(vals)
        except Exception:
            # Odoo cursors run at REPEATABLE READ (snapshot isolation, see
            # odoo/sql_db.py) — the losing request's transaction took its
            # snapshot before the winner committed, so re-searching on
            # request.env.cr (same transaction, same snapshot) can NEVER see
            # the winner's row, no matter how many times you retry the
            # SELECT. Confirmed by reproducing two genuinely concurrent HTTP
            # requests for the same new key: the loser's re-search returned
            # nothing even after the winner's create had already logged
            # success. A brand new cursor (fresh connection = fresh
            # snapshot, taken now, after the winner's commit) is required.
            with request.env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, request.env.uid, request.env.context)
                existing = (
                    new_env["document.page"]
                    .sudo()
                    .search(
                        [("rag_entity_type", "=", entity_type), ("rag_key", "=", key)],
                        limit=1,
                    )
                )
                existing_id = existing.id if existing else None
            if not existing_id:
                raise
            existing = Page.browse(existing_id)
            return request.make_response(
                json.dumps({"page_id": existing.id, "created": False}),
                headers=[("Content-Type", "application/json")],
            )
        _logger.info(
            "RAG curator created %s page %s (%r) key=%s",
            entity_type,
            page.id,
            title,
            key,
        )
        return request.make_response(
            json.dumps({"page_id": page.id, "created": True}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/rag_bridge/refresh_wiki_links",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def refresh_wiki_links(self, **kwargs):
        """Re-resolve {{reference}} cross-links for every wiki note last
        touched by one source page.

        content_parsed is a stored compute — it's fixed at the moment a note
        is written, before entities it links to (fabricante/familia,
        possibly created moments later in the same curation run)
        necessarily exist yet. Call this once, after the whole batch for a
        source page has been created/updated, to resolve links that pointed
        at not-yet-existing notes at write time.
        """
        data = json.loads(request.httprequest.get_data() or b"{}")
        if not _check_token(data):
            return _error("invalid or missing token")

        source_page_id = data.get("source_page_id")
        notes = (
            request.env["document.page"]
            .sudo()
            .search([("rag_source_page_id", "=", int(source_page_id))])
        )
        notes._compute_content_parsed()
        return request.make_response(
            json.dumps({"refreshed": len(notes)}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/rag_bridge/upload_image",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def upload_image(self, **kwargs):
        """Attach one image extracted from a raw PDF (by docling) to its
        source page, so the technician sees the manual's real diagrams/photos
        instead of the OCR text alone.

        Images are deliberately attached to the RAW source page only, not to
        the curated wiki notes — matching each figure to the exact paragraph
        it illustrates would need the curator LLM to reason image-by-image,
        which is a lot more fragile than "see all the manual's images here".

        Body: {token, source_page_id, filename, mimetype, base64_data}
        Response: {attachment_id}
        """
        data = json.loads(request.httprequest.get_data() or b"{}")
        if not _check_token(data):
            return _error("invalid or missing token")

        source_page_id = data.get("source_page_id")
        base64_data = data.get("base64_data")
        if not source_page_id or not base64_data:
            return _error("missing source_page_id or base64_data", status=400)

        Page = request.env["document.page"].sudo()
        page = Page.browse(int(source_page_id))
        if not page.exists():
            return _error("source_page_id not found", status=404)

        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": data.get("filename") or "image.png",
                    "res_model": "document.page",
                    "res_id": page.id,
                    "datas": base64_data,
                    "mimetype": data.get("mimetype") or "image/png",
                }
            )
        )
        return request.make_response(
            json.dumps({"attachment_id": attachment.id}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/rag_bridge/set_page_html",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def set_page_html(self, **kwargs):
        """Set the RAW page's own content to the rendered HTML of its
        attachment (docling, images embedded inline) instead of creating
        separate Dispositivo/Fabricante/Familia notes nobody was navigating
        to in practice.

        First attachment on a page replaces its (placeholder/empty) content;
        a second attachment on the same page (e.g. an addendum PDF added
        later) gets concatenated onto the existing content instead of
        overwriting it — tracked via rag_html_source_count, not by checking
        whether content looks "empty", since a document can legitimately
        have zero identified fabricantes/familias/part_numbers on its first
        pass and still need the *next* attachment appended rather than
        replacing it.

        fabricantes/familias/part_numbers are merged (union, de-duplicated)
        into the page's existing CSV tag fields rather than overwritten, for
        the same reason.

        Body: {token, source_page_id, html_content,
               fabricantes?: [...], familias?: [...], part_numbers?: [...]}
        Response: {page_id}
        """
        data = json.loads(request.httprequest.get_data() or b"{}")
        if not _check_token(data):
            return _error("invalid or missing token")

        source_page_id = data.get("source_page_id")
        html_content = data.get("html_content")
        if not source_page_id or html_content is None:
            return _error("missing source_page_id or html_content", status=400)

        Page = request.env["document.page"].sudo()
        page = Page.browse(int(source_page_id))
        if not page.exists():
            return _error("source_page_id not found", status=404)

        def _merge_csv(existing, new_values):
            current = [v.strip() for v in (existing or "").split(",") if v.strip()]
            for v in new_values or []:
                v = (v or "").strip()
                if v and v not in current:
                    current.append(v)
            return ",".join(current)

        if page.rag_html_source_count:
            new_content = (
                str(page.content or "")
                + "<hr/><p><em>Contenido añadido desde otro anexo</em></p>"
                + html_content
            )
        else:
            new_content = html_content

        page.write(
            {
                "content": new_content,
                "rag_html_source_count": page.rag_html_source_count + 1,
                "rag_fabricantes": _merge_csv(
                    page.rag_fabricantes, data.get("fabricantes")
                ),
                "rag_familias": _merge_csv(page.rag_familias, data.get("familias")),
                "rag_part_numbers": _merge_csv(
                    page.rag_part_numbers, data.get("part_numbers")
                ),
            }
        )
        return request.make_response(
            json.dumps({"page_id": page.id}),
            headers=[("Content-Type", "application/json")],
        )
