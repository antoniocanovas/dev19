from odoo import fields, models

PROTECTED_ENTITY_TYPES = ("fabricante", "familia")


class DocumentPage(models.Model):
    _inherit = "document.page"

    _rag_entity_key_uniq = models.Constraint(
        "unique(rag_entity_type, rag_key)",
        "Ya existe una nota con esa clave para ese tipo de entidad RAG.",
    )

    # Links a "wiki" atomic note back to the raw source page it was last
    # curated/updated from. Without this, updating a manual (new PDF
    # version) has no way to find and refresh/remove the notes and
    # rag_documentos rows that trace back to it.
    rag_source_page_id = fields.Many2one(
        "document.page",
        string="Fuente RAG",
        ondelete="set null",
        copy=False,
    )

    # Karpathy-style entity hierarchy: a "dispositivo" note consolidates ALL
    # its technical detail in one place (not one note per isolated fact),
    # and links to a shared "fabricante" and "familia" note reused across
    # every device that mentions them — search-or-create by rag_key, not by
    # embedding similarity, is what actually prevents duplicate
    # manufacturer/family notes across separate document uploads.
    rag_entity_type = fields.Selection(
        [
            ("fabricante", "Fabricante"),
            ("familia", "Familia"),
            ("dispositivo", "Dispositivo"),
        ],
        copy=False,
    )
    rag_key = fields.Char(
        string="Clave RAG",
        index=True,
        copy=False,
        help="Clave estable de búsqueda-o-creación (slug del fabricante, "
        "familia o part number/nombre del dispositivo).",
    )
    rag_part_number = fields.Char(copy=False)
    rag_fabricante_id = fields.Many2one(
        "document.page",
        string="Fabricante",
        domain=[("rag_entity_type", "=", "fabricante")],
        ondelete="set null",
        copy=False,
    )
    rag_familia_id = fields.Many2one(
        "document.page",
        string="Familia",
        domain=[("rag_entity_type", "=", "familia")],
        ondelete="set null",
        copy=False,
    )

    # Replaces the Fabricante/Familia/Dispositivo-as-separate-page design
    # above: those pages were never actually navigated in practice (Knowledge
    # notes with almost no content of their own beyond a name), so their
    # only real value — dedup + filtering by product — is kept as plain CSV
    # tags directly on the RAW page instead. No separate entity to create,
    # search-or-create by HTTP, or protect from cascade delete. A page can
    # legitimately touch several fabricantes/familias/part numbers (a
    # compatibility catalog listing parts across manufacturers), hence CSV
    # rather than a single value.
    rag_fabricantes = fields.Char(
        string="Fabricantes (CSV)",
        copy=False,
        help="Fabricantes mencionados en este documento, separados por coma.",
    )
    rag_familias = fields.Char(
        string="Familias (CSV)",
        copy=False,
        help="Familias de producto mencionadas en este documento, separadas por coma.",
    )
    rag_part_numbers = fields.Char(
        string="Part numbers (CSV)",
        copy=False,
        help="Part numbers de los dispositivos identificados en este documento, "
        "separados por coma — cada uno tiene un ancla propia "
        "(#dispositivo-{part_number}) dentro del content HTML de esta página.",
    )
    rag_html_source_count = fields.Integer(
        default=0,
        copy=False,
        help="Cuántos adjuntos han aportado ya HTML al content de esta página — "
        "0 significa 'reemplazar' en /rag_bridge/set_page_html, >0 significa "
        "'concatenar' (un segundo PDF, p.ej. un addendum, se añade en vez de "
        "machacar el primero).",
    )

    # Showing content_parsed (rendered, read-only) and content (raw HTML,
    # editable) at the same time doubles the DOM for these large manuals
    # (~16MB/272 images each) with no visual separator between them. This
    # toggle keeps only one on screen at a time instead.
    rag_editing_html = fields.Boolean(
        string="Editando HTML",
        default=False,
        copy=False,
    )

    def action_toggle_rag_editing_html(self):
        for record in self:
            record.rag_editing_html = not record.rag_editing_html

    def unlink(self):
        # rag_documentos is a plain SQL table (not an Odoo model) with no FK
        # or cascade at all — deleting a page here would otherwise leave
        # dangling rows forever, still surfaced by future pgvector searches.
        # Cascade to curated notes that trace back to any page deleted here
        # — except shared fabricante/familia entities, which stay even if
        # the one document that happened to create them is removed; other
        # devices may still reference them.
        candidates = (
            self.env["document.page"].search(
                [("rag_source_page_id", "in", self.ids)]
            )
            - self
        )
        wiki_notes = candidates.filtered(
            lambda p: p.rag_entity_type not in PROTECTED_ENTITY_TYPES
        )
        page_ids = self.ids + wiki_notes.ids
        if page_ids:
            self.env.cr.execute(
                "DELETE FROM rag_documentos WHERE page_id IN %s",
                (tuple(page_ids),),
            )
        result = super().unlink()
        if wiki_notes:
            wiki_notes.unlink()
        return result
