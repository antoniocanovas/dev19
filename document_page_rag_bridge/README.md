# Document Page RAG Bridge

Envía a n8n, para su ingesta en el pipeline RAG, cualquier adjunto que se suba a una
página de Knowledge (`document.page`) archivada bajo la categoría **"raw"**.

Es el primer eslabón del Flujo 1 (ingesta de manuales) del proyecto *Soporte IA + RAG*:
sube un PDF a una página bajo "raw" → este módulo avisa a n8n → n8n lo pasa por OCR
(texto, Mistral vía OpenRouter) y por docling (HTML con imágenes embebidas), etiqueta
la propia página raw con fabricante/familia/part numbers, e indexa el texto en
pgvector con esas mismas etiquetas para poder filtrar por producto en el chat del
ticket.

**Rediseño (agosto 2026):** la primera versión de este pipeline generaba una nota
Knowledge separada por cada Dispositivo/Fabricante/Familia, enlazadas entre sí. Se
abandonó — en la práctica nadie navegaba esas notas (Fabricante/Familia solían quedar
casi vacías, un nombre y poco más), y mantenerlas vivas costó la mayor parte de la
depuración real de este módulo (condiciones de carrera de bajo nivel, `pairedItem`
ambiguo con varios dispositivos, etc. — ver la lista de bugs más abajo). El diseño
actual es mucho más simple: **una página raw = un documento navegable con sus fotos**,
sin notas satélite.

## Cómo funciona

- **Trigger**: Automated Action (`base.automation`) sobre `ir.attachment`, no sobre
  `document.page`. `document.page` no expone ningún campo que cambie al subir un
  adjunto, así que un trigger en la página nunca se dispararía al añadir un PDF a una
  página ya existente — el evento real es la creación del `ir.attachment`.
- **Filtro**: `filter_domain = [('res_model', '=', 'document.page')]` a nivel de
  Automated Action; el filtro fino se hace en Python — la página padre debe ser
  realmente la categoría "raw" **y** el adjunto no puede ser una imagen (ver bug 16
  más abajo: las imágenes que este mismo módulo sube a la página raw no deben
  re-disparar la ingesta sobre sí mismas).
- **Idempotencia**: no hay campo de estado a nivel de página — el estado
  (`rag_status`/`rag_sent_date`/`rag_error`) vive en el propio `ir.attachment`, porque
  una página puede tener varios adjuntos y cada uno se procesa de forma independiente.
- **Payload enviado a n8n** (POST JSON):
  ```json
  {
    "_model": "document.page",
    "page_id": 12,
    "page_name": "Manual XR200",
    "attachment_id": 543,
    "attachment_name": "manual_xr200.pdf",
    "mimetype": "application/pdf",
    "checksum": "...",
    "content_base_url": "http://odoo:8069/web/content/543",
    "access_token": "...",
    "image_engine": "docling"
  }
  ```
  `content_base_url` + `access_token` son campos separados a propósito — no una URL ya
  montada con query string — porque el nodo HTTP Request de n8n en modo descarga
  binaria (`responseFormat: file`) corrompe una query string embebida en un único
  string de expresión. n8n debe construir la query él mismo (`sendQuery: true` +
  parámetros). `image_engine` viene de `res.company.rag_image_engine`.

## El modelo actual: una página raw, HTML con fotos, etiquetas CSV

Cada página "raw" termina con:

- **`content`** = el HTML que devuelve docling (`to_formats: ['html']`,
  `image_export_mode: 'embedded'`) sobre el PDF adjunto — fotos y diagramas
  incluidos como `<img src="data:...">` inline, no como adjuntos sueltos. Si la
  página ya tenía contenido de un adjunto anterior (p. ej. un addendum subido
  después del manual principal), el nuevo HTML se **concatena**, no lo reemplaza.
- **Un `<a id="dispositivo-{clave}">`** insertado justo antes de la primera mención
  de cada dispositivo detectado por el curador — así el chat del ticket puede
  enlazar a la sección exacta (`{page}#dispositivo-{clave}`) en vez de al principio
  del documento.
- **Tres campos de texto CSV** con lo que el curador identificó en ese documento:
  `rag_fabricantes`, `rag_familias`, `rag_part_numbers`. Un documento puede
  legítimamente mencionar varios fabricantes (un catálogo de piezas compatibles
  entre marcas), de ahí CSV y no un valor único ni un `Many2one`.

| Campo | Para qué |
|---|---|
| `rag_fabricantes` / `rag_familias` / `rag_part_numbers` | CSV de lo detectado en este documento — sustituyen a las notas Fabricante/Familia/Dispositivo separadas de antes; el dedup real ocurre a nivel de fila en `rag_documentos` (ver más abajo), no aquí |
| `rag_html_source_count` | Cuántos adjuntos han aportado ya HTML a `content` — 0 = reemplazar, >0 = concatenar. No se puede inferir de si `content` "está vacío", porque un documento puede legítimamente no tener ningún dispositivo identificado y aun así necesitar que el *siguiente* adjunto se añada en vez de machacar el primero |

Los campos `rag_entity_type`, `rag_key`, `rag_fabricante_id`, `rag_familia_id`,
`rag_part_number` y el constraint `unique(rag_entity_type, rag_key)` siguen
existiendo en el modelo por compatibilidad con instalaciones antiguas, pero **el
pipeline actual ya no los usa** — no crea páginas con `rag_entity_type` relleno.

### `unlink()` en cascada

Al borrar una página "raw": se borran las filas correspondientes de `rag_documentos`
(tabla SQL plana, sin FK real — sin este código quedarían huérfanas para siempre y
seguirían apareciendo en búsquedas de pgvector). Los `ir.attachment` (el PDF
original) se borran solos: Odoo core (mixin `mail.thread`) ya cascada los adjuntos
de un registro al borrar el registro — comprobado en vivo, no hace falta código
propio para eso. Como las imágenes ya no son adjuntos sueltos sino HTML embebido en
`content`, desaparecen con la propia página sin necesitar ningún tratamiento aparte.

## Endpoints expuestos (n8n → Odoo)

Todos son rutas públicas (`auth="public"`, n8n no tiene sesión de Odoo) protegidas por
el secreto compartido `document_page_rag_bridge.n8n_shared_secret`, comprobado con
`consteq()`.

### `POST /rag_bridge/set_page_html`

El endpoint central del diseño actual. Fija (o concatena) el `content` de la página
raw y funde las etiquetas CSV.

```json
{
  "token": "...", "source_page_id": 15, "html_content": "<!DOCTYPE html>...",
  "fabricantes": ["Yamaha"], "familias": ["Teclados electrónicos"],
  "part_numbers": ["PSR-SX900", "PSR-SX700"]
}
→ {"page_id": 15}
```

`fabricantes`/`familias`/`part_numbers` se **fusionan** (unión, sin duplicados) con
lo que ya hubiera en la página, no se sobrescriben — un segundo adjunto puede añadir
fabricantes nuevos sin perder los que ya había.

### `POST /rag_bridge/upload_image` *(sin uso en el pipeline actual)*

Seguía existiendo del diseño anterior (imágenes como adjuntos sueltos, subidas una a
una) — se mantiene sin borrar por si se necesita puntualmente, pero el flujo de
ingesta actual no lo llama: las imágenes ya vienen embebidas en el HTML de
`set_page_html`.

### `POST /rag_bridge/upsert_entity_page`, `POST /rag_bridge/refresh_wiki_links` *(obsoletos)*

Del diseño de notas Dispositivo/Fabricante/Familia. El código sigue en el
controlador (por si hace falta consultarlo o revertir), pero **ningún workflow de
n8n los llama ya**.

## docling: HTML directo, no Markdown

La llamada a docling pide `to_formats: ['html']` directamente (antes pedía `['md']`
y había que sacar las imágenes del blob de markdown con una regex) — un solo campo
`document.html_content` con las imágenes ya embebidas, sin parseo intermedio.
`do_ocr: false` — solo interesa la estructura/imágenes, el texto real lo sigue
sacando Mistral OCR vía OpenRouter en la rama paralela de texto (sin cambios); con
OCR de texto activado en docling, un documento de 130 páginas pasa de ~7 min a
~15-25 min, y además se comprobó en real que la calidad de texto de Mistral es mejor
que la de docling/RapidOCR en contenido denso multi-idioma (ver más abajo).

**docling vs. Mistral para el texto — comparado en real, mismo PDF, mismas 5
páginas**: en el contenido normal del manual, calidad equivalente. En una página
densa con texto pequeño multi-idioma (garantías legales en 15 idiomas), Mistral
mantuvo la tabla como tabla y el texto mayormente correcto; docling/RapidOCR rompió
la tabla y mezcló texto de varios idiomas sin sentido. Por eso el texto para
embeddings/curación sigue siendo Mistral — docling solo aporta la estructura+fotos
del documento "de consulta".

**OpenRouter también puede devolver imágenes** (mismo plugin `file-parser` +
`engine: mistral-ocr`, partes `{type: 'image_url', ...}` en la misma anotación) —
pero capa la extracción a **8 imágenes por PDF, no configurable**. Para manuales
técnicos reales deja fuera casi todos los diagramas, así que no es alternativa
válida para producción. Queda como interruptor de comparación
(`res.company.rag_image_engine`, default `docling`) sin usarse en el pipeline actual
más que como guarda (`image_engine !== 'docling'` corta la rama entera).

## Búsqueda con contexto de producto (chat del ticket)

El flujo de consulta (workflow n8n `Helpdesk - Sugerir respuesta`, fuera de este
módulo pero dependiente de su esquema) hace top-5 por similitud de embedding sobre
`rag_documentos`. Sin más, eso puede colar contenido de **otro producto** cuando el
vocabulario es parecido (confirmado en real: una pregunta sobre "el teclado no
arranca" para el PSR-999 sacaba notas de otro teclado, por pura cercanía semántica
de "encendido"). Dos piezas cierran esto:

1. **`product_id` del ticket → `part_number`**: el `ai.bridge` del chat manda
   `product_id` en el payload. Odoo serializa un Many2one como `[id, display_name]`,
   y `display_name` de un producto con referencia va como `"[código] nombre"` — el
   workflow extrae el código con una regex, sin tocar nada en Odoo aparte de añadir
   el campo a `field_ids` del bridge.
2. **`rag_documentos.part_number`** en *todas* las filas de una página (tanto
   `tipo='fuente'` como `tipo='dispositivo'`), no solo en las de dispositivo — al
   terminar cada ingesta se etiquetan también las filas `fuente` con el/los
   `part_number` que identificó el curador en ese documento (lista CSV si hay
   varios dispositivos).

La consulta filtra con
`part_number IS NULL OR $producto = ANY(string_to_array(part_number, ','))` — las
filas sin etiquetar siguen pasando siempre (contenido genérico); las de un producto
concreto solo si coincide con el del ticket.

Los enlaces de "Fuentes" en la respuesta usan `part_number` para construir el ancla
de respaldo: `#dispositivo-{slugify(part_number)}` — mismo `slugify` que usa el
workflow de ingesta al inyectar el ancla en el HTML, tienen que coincidir letra por
letra o el enlace cae al principio del documento en vez de a la sección.

**Consistencia del `part_number`**: el curador no siempre rellena un campo
`part_number` formal — para muchos productos de consumo el "nombre del modelo" (p.
ej. "PSR-SX900") ya hace de identificador, sin un SKU aparte. Tanto la clave del
ancla como las etiquetas CSV usan el mismo *fallback* `part_number || nombre` — si
solo una de las dos rutas lo aplica, las claves dejan de coincidir entre sí (bug
real, ver más abajo).

### Ancla de sección, no solo de dispositivo

`#dispositivo-{clave}` marca dónde empieza la sección de un aparato entero — no
sirve para llevar al técnico al párrafo exacto que responde su pregunta (p. ej.
preguntar por "instalación de firmware" y aterrizar al principio del manual
completo). Columna nueva `rag_documentos.ancla`:

1. Al construir el HTML de la página raw, cada encabezado real de docling
   (`<h1>`-`<h6>`, ya vienen así del propio docling, no hay que inventarlos) recibe
   un `id="seccion-{slug del texto}"`.
2. Tras esa ingesta, cada fila `tipo='fuente'` intenta casar los primeros ~60
   caracteres de su `contenido` contra ese HTML (búsqueda de substring, no fuzzy) y
   se queda con el `id` del encabezado más cercano hacia atrás, si lo encuentra.
   Se guarda en `rag_documentos.ancla`.
3. El chat prioriza `ancla` sobre `#dispositivo-{clave}` si existe.

**Tasa de acierto real, no perfecta**: probado con el manual de Yamaha (18 fragmentos
`fuente`), 8/18 casaron con un encabezado (~44%). El texto de `fuente` sale de
Mistral (que a veces conserva sintaxis markdown literal, `## AVISO`) y el HTML de
`ancla` sale de docling (encabezados reales, sin el `##`) — dos lecturas OCR
distintas del mismo PDF no siempre coinciden palabra por palabra en los primeros 60
caracteres. Cuando no casa, `ancla` queda `NULL` y se cae al ancla de dispositivo o
al documento entero — degradación segura, nunca un enlace roto.

**Deduplicar por página ya no es tan simple**: con dispositivo y fuente compartiendo
`page_id`, el top-5 puede traer dos filas de la misma página — si `Construir
contexto` se queda con la primera que aparece sin más criterio, puede perder la fila
con `ancla` precisa a favor de la genérica de dispositivo (pasó de verdad en la
prueba). Al deduplicar por `page_id`, si la fila que ya se tiene no tiene `ancla` y
la nueva sí, se sustituye.

## Parámetros de sistema requeridos

Configurables en **Ajustes → Técnico → Parámetros → Parámetros del sistema**:

| Clave | Obligatorio | Descripción |
|---|---|---|
| `document_page_rag_bridge.n8n_ingest_url` | Sí | URL del webhook de n8n que recibe el payload de ingesta. Si falta, el adjunto queda en `rag_status = error` con un mensaje explicativo — no falla en silencio. |
| `document_page_rag_bridge.odoo_internal_url` | No (default `http://odoo:8069`) | Host:puerto por el que **n8n** alcanza a Odoo dentro de la red Docker para descargar el adjunto. Deliberadamente distinto de `web.base.url` (esa es para enlaces abiertos por un humano en el navegador; esta es para que un contenedor hermano llame de vuelta a Odoo). |
| `document_page_rag_bridge.n8n_shared_secret` | Sí | Token que n8n debe mandar en todos los endpoints `/rag_bridge/*` para que Odoo acepte la petición. |

## Detalles no obvios / bugs ya resueltos

Si vuelves a tocar esto, ten en cuenta lo siguiente — cada uno costó una ronda de
depuración real:

1. **Token de descarga**: usa `attachment._get_raw_access_token()` (HMAC sin estado,
   scope `"binary"`, campo `"raw"`), **no** `attachment.generate_access_token()` (el
   UUID clásico). El controlador `/web/content` de Odoo 19 comprueba primero el token
   nuevo (`verify_limited_field_access_token`) y **revienta con `ValueError`** si el
   token no tiene el formato esperado, antes de llegar al fallback que sí habría
   aceptado el UUID clásico — el síntoma es un 404 genérico sin pista real del motivo.
2. **`env.cr.commit()` antes de avisar a n8n**: el adjunto se crea dentro de la misma
   transacción de Odoo que la Automated Action. n8n descarga el fichero desde una
   conexión a Postgres distinta, que no puede ver una fila no confirmada (MVCC) — sin
   el commit explícito, la descarga devuelve 404 aunque el registro "exista" en la
   transacción que lo creó.
3. **Payload sin URL premontada**: `content_base_url` + `access_token` como campos
   separados — el nodo HTTP Request de n8n en modo descarga binaria corrompe una
   query string embebida en un único string de expresión.
4. **Sintaxis de enlaces**: `document_page_reference` usa `{{referencia}}` (un slug
   por página, campo `reference`), **no** `[[Título]]` estilo Obsidian.
5. **`content_parsed` es un compute *almacenado***: se fija en el momento de crear
   cada nota, antes de que otras páginas que enlaza necesariamente existan todavía.
   *(Relevante solo si vuelves a crear páginas con `{{referencia}}` entre sí — el
   pipeline actual no lo hace.)*
6. **Contenido duplicado en la vista de formulario genérica**: la vista que
   `document_page_reference` parchea (`document_page_form_view`, prioridad 10)
   muestra `content_parsed` y el `content` crudo a la vez, apilados.
   `views/document_page.xml` de este módulo lo oculta también ahí.
7. **`Markup` de markupsafe auto-escapa al concatenar**: `existing.content` es un
   `markupsafe.Markup` — `Markup + str_plano` **escapa el operando str** (protección
   XSS de por sí correcta, pero mangla el HTML nuevo en literal `&lt;h4&gt;`). Hay
   que forzar `str(x or "")` antes de concatenar para que sea texto plano + texto
   plano. *(Aplica también al `content` + `html_content` de `set_page_html`.)*
8. **`_sql_constraints` obsoleto en Odoo 19**: sintaxis nueva de clase:
   `campo = models.Constraint("unique(...)", "msg")`.
9. **Condición de carrera creando registros duplicados por clave única**: dos
   peticiones HTTP casi simultáneas pueden pasar ambas el `search()` de "¿existe
   ya?" antes de que ninguna haga commit. Un `unique(...)` a nivel de base de datos
   convierte el duplicado en un `IntegrityError` capturable en vez de un duplicado
   silencioso — pero **capturarlo no basta**, ver el punto 14.
10. **Timeout síncrono bloqueaba la subida del navegador**: un manual real de varios
    cientos de páginas tarda más de lo que aguanta un `requests.post(timeout=X)`
    síncrono desde Odoo. Arreglado con `responseMode: onReceived` en el nodo Webhook
    de n8n (ack inmediato, procesa en background de verdad).
11. **`ocr_engine` ignorado por `/v1/convert/file` de docling-serve**: bug conocido
    ([docling-serve#567](https://github.com/docling-project/docling-serve/issues/567))
    que ignora `ocr_engine`/`ocr_lang`/`force_ocr` y siempre usa `auto` (→ RapidOCR)
    en el endpoint multipart. Hay que usar **`/v1/convert/source`** (JSON) — ahí sí
    se respeta. Para documentos grandes, siempre `/async` + sondeo por `task_id`,
    porque incluso el JSON da 504 fijo a los 2 minutos aunque siga procesando.
12. **Tesseract sin el paquete de idioma español**: la imagen base de docling-serve
    solo trae `eng` — pedir `ocr_lang: spa` sin tenerlo falla en silencio página a
    página. Arreglado instalando `tesseract-langpack-spa` vía `dnf` en el
    `Dockerfile` propio de la imagen.

Los siguientes solo salieron al probar con un manual real grande (132 páginas, 2
dispositivos) de extremo a extremo — ningún PDF de prueba anterior era lo bastante
grande/complejo para dispararlos:

13. **Embedding sin trocear reventaba con documentos reales**: `text-embedding-3-small`
    tiene un límite duro de 8192 tokens por entrada — mandar el texto OCR completo de
    un manual real en una sola llamada fallaba con `"maximum context length"` y
    **abortaba toda la ejecución de n8n** (n8n mata la ejecución entera si una rama
    falla sin `continueOnFail`, no solo esa rama — mata también la rama paralela de
    imágenes). Arreglado troceando en fragmentos de 20.000 caracteres antes de
    generar cada embedding; cada fragmento es su propia fila `fuente`.
14. **La condición de carrera (bug 9) no se recuperaba de verdad con concurrencia
    HTTP real**: reproducido con peticiones `curl` genuinamente simultáneas — el
    `except` se ejecutaba y el `search()` de reintento corría, pero **siempre
    devolvía vacío** aunque el ganador ya hubiera hecho commit. Causa: los cursores
    de Odoo usan **REPEATABLE READ** (`odoo/sql_db.py`,
    `ISOLATION_LEVEL_REPEATABLE_READ`), no READ COMMITTED — la transacción perdedora
    toma su instantánea antes del commit ganador y **nunca puede verlo**, por muchas
    veces que repita el `SELECT` en la misma transacción.
    `env.invalidate_all()` no sirve (solo limpia caché en memoria del ORM). Hace
    falta un cursor nuevo de verdad (`request.env.registry.cursor()` +
    `api.Environment(...)`) solo para la re-búsqueda. Verificado con 3 peticiones
    concurrentes reales.
15. **Ambigüedad de `pairedItem` con varios dispositivos, dos veces seguidas**: con 2
    dispositivos en el mismo documento, cualquier nodo Postgres que reference un
    Code node **a través de** otro nodo Postgres/HTTP intermedio revienta con
    `"Multiple matches found"` — no es cuestión de saltos, es que Postgres/HTTP no
    preservan `pairedItem` de forma fiable con varios items en vuelo. Se intentó
    acortar el salto una vez y volvió a fallar un salto más allá; el arreglo que
    aguantó fue **fundir DELETE+INSERT en una sola sentencia SQL**
    (`WITH deleted AS (DELETE ...) INSERT ...`), eliminando el salto por completo en
    vez de intentar acortarlo.
16. **Consecuencia del rediseño — el DELETE de la sentencia fundida (bug 15) no
    filtraba por dispositivo**: al pasar de "una página por dispositivo" a "todos
    los dispositivos comparten la página raw", `DELETE FROM rag_documentos WHERE
    page_id = $1` (sin más filtro) borraba la fila del dispositivo A al insertar la
    del dispositivo B, porque ahora comparten `page_id`. Arreglado acotando a
    `tipo = 'dispositivo' AND part_number = $4` — cada dispositivo solo toca su
    propia fila.
17. **Subir imágenes al raw volvía a disparar la ingesta completa sobre cada
    imagen** *(bug del diseño anterior, con imágenes como adjuntos sueltos)*:
    `_rag_maybe_ingest()` no filtraba por `mimetype` — cada imagen subida a la
    página raw también disparaba la Automated Action, tratándola como un manual
    nuevo. Un documento con ~100 imágenes generaba ~100 reintentos de ingesta,
    agotando el pool de conexiones de Odoo. Arreglado con
    `if (attachment.mimetype or "").startswith("image/"): continue`. *(El rediseño a
    HTML embebido elimina la causa de raíz — ya no hay adjuntos de imagen sueltos —
    pero el filtro se deja puesto por si acaso.)*
18. **Incluso sin la avalancha, ~100 peticiones HTTP seguidas agotaban el pool
    igual** *(mismo diseño anterior)*: `workers=0` en Odoo, pool máx. 64 — arreglado
    con *batching* (5 peticiones cada 500ms). *(Sin uso ya, mismo motivo que el 17.)*
19. **El curador no siempre rellena `part_number` como campo aparte** — para
    productos de consumo el nombre del modelo ya es el identificador. La clave del
    ancla ya aplicaba el *fallback* `part_number || nombre`; el etiquetado CSV y la
    fila de `rag_documentos` no lo aplicaban, así que un dispositivo con solo
    `nombre` tenía ancla pero no aparecía en `rag_part_numbers` ni se podía filtrar
    por él en el chat. Arreglado aplicando el mismo *fallback* en los tres sitios.
20. **El `<style>` de docling rompía la interfaz entera de Odoo, no solo la página**:
    docling devuelve un documento HTML completo (`<!DOCTYPE>`, `<html>`, `<head>`
    con `<style>`, `<body>`). Un primer intento de arreglo extrajo el CSS y lo
    reinyectó como un `<style>` suelto junto al fragmento — **peor que el problema
    original**: como Odoo es una SPA de una sola página, un `<style>` con reglas
    globales (`html { ... }`, `body { max-width: 800px; margin: 0 auto; }`,
    pensadas para el documento aislado de docling) se aplica a **toda la
    aplicación**, no solo al registro — sidebar, chatter, todo el layout roto,
    confirmado visualmente (pantalla en blanco, menú colapsado). No se puede
    aislar con un prefijo simple porque las reglas van sobre `html`/`body`
    directamente. Arreglado descartando el `<style>` por completo — solo se guarda
    el contenido de `<body>`; las tablas/imágenes se ven con el estilo genérico de
    Odoo, sin la maquetación de docling, pero sin arriesgar la interfaz.

## Limitaciones conocidas (documentadas, no resueltas)

- **Deduplicación de contenido entre documentos distintos**: si dos manuales
  distintos describen el mismo hecho técnico con otras palabras, no hay
  deduplicación por similitud semántica — cada documento añade su propio fragmento a
  `rag_documentos`.
- **Las imágenes se enlazan a nivel de documento, no de párrafo**: el ancla de un
  dispositivo marca dónde empieza su sección de texto, pero las fotos de esa sección
  no están individualmente enlazadas a los párrafos que ilustran — vienen todas
  embebidas en el mismo HTML de la página.

## Dependencias

`document_page` (OCA Knowledge), `base_automation` (núcleo de Odoo, no Enterprise —
no requiere Studio). A nivel de infraestructura (fuera de Odoo): el servicio `docling`
del `docker-compose.yml` de `docker-ia-support` y el workflow de n8n `RAG - Ingesta
documento Raw`.
