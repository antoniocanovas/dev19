# Mercas MCP Chat

Consolas de chat con IA integradas en el propio backend de Odoo, construidas sobre
`odoo_mcp_manager` (el MCP Gateway de Cybrosys). No requiere clientes externos (Claude
Desktop, curl, etc.) ni tener configurada una MCP API Key: todo se ejecuta por ORM dentro
del propio proceso de Odoo.

## Estado / continuidad (para retomar la sesión)

Todo lo descrito en este README está implementado y probado **por ORM** (`odoo-bin shell`,
simulando exactamente lo que hace cada botón). El comportamiento en navegador real (JS/CSS) no
siempre se ha podido verificar de primera mano en las sesiones de agente (sin ruta de red a
`localhost:8069` desde ese entorno) — confirmarlo visualmente sigue siendo responsabilidad del
usuario, pero un bug ya detectado y corregido así fue: el auto-scroll del historial
(`static/src/js/chat_fields.js`, widget `mercas_chat_history`) usaba
`useEffect((el) => {...}, () => [this.value, this.boxRef.el])` — Owl invoca el callback de
`useEffect` con las dependencias **por posición**, así que `el` recibía `this.value` (el string
HTML del historial), no `this.boxRef.el` (el nodo DOM); `el.scrollTop = el.scrollHeight` sobre
un string es un no-op silencioso, sin error en consola. Arreglado leyendo `this.boxRef.el` desde
el cierre en vez de por posición. Si aparece otro comportamiento raro de un widget Owl en este
módulo, sospechar primero de este mismo patrón (deps posicionales de `useEffect`) antes de asumir
un problema de timing/API de la build de Odoo 19.

El atajo de teclado Ctrl+Enter / Cmd+Enter (widget `mercas_chat_message`, mismo fichero) no usa
este patrón (lee `ev.target` directamente), así que no debería tener el mismo problema, pero
sigue pendiente de confirmación visual en navegador.

**Recordatorio operativo**: cada vez que se toque este módulo con Odoo ya arrancado, hay que
reiniciar el proceso para que los cambios se vean (ver "Limitaciones conocidas" más abajo) — es
la fuente más probable de "no veo el cambio" en la próxima sesión.

## Dependencias

| Módulo | Para qué |
|---|---|
| `odoo_mcp_manager` | Aporta `ai.provider`, `ai.model`, `ai.tool`, `ai.bot.conversation` y el motor de enrutado LLM (`LLMRouter`) que este módulo reutiliza. |
| `sale`, `purchase`, `account`, `stock` | Modelos sobre los que consultan las herramientas de informes (`sale.order`, `purchase.order`, `account.move`, `stock.move`). |

## Qué instala

### 1. Fix: `ai.bot.channel.platform` sin la opción "Web Widget"

`odoo_mcp_manager` implementa el adaptador del canal Web (`_connect_web`, el controlador
`/bot/web`, las vistas), pero el campo `platform` de `ai.bot.channel` nunca incluye
`('web', 'Web Widget')` en su Selection — así que esa opción no aparece en el desplegable del
formulario de canales. `models/ai_bot_channel.py` lo corrige con un `selection_add`.

### 2. Cuatro herramientas de informe deterministas (`models/ai_tool.py`)

El problema que motivó este módulo: pedirle a la IA que sume importes a partir de un volcado
de registros (`search_records`) no funciona — ese tool ni siquiera expone campos financieros,
así que el modelo alucina totales. Estas herramientas hacen un `read_group` real en Odoo y
devuelven cifras exactas; la IA solo redacta la respuesta a partir de datos ya calculados.

| Tool | Modelo | Agrupa por | Suma | Extra |
|---|---|---|---|---|
| `sales_report` | `sale.order` | cliente (`customer`) y/o día | `amount_total` | |
| `purchase_report` | `purchase.order` | proveedor (`vendor`) y/o día | `amount_total` | |
| `invoice_report` | `account.move` (solo `state='posted'`) | cliente/proveedor y/o día | `amount_total` | `move_type`: `customer`/`vendor`/`all` |
| `stock_report` | `stock.move` (solo `state='done'`) | producto y/o día | `quantity` | `direction`: `in`/`out`/`internal`; `only_boxes`: solo productos con `is_box=True` (ver más abajo) |

Parámetros comunes: `date_from` / `date_to` (`YYYY-MM-DD`), `group_by`. Estas herramientas
también quedan disponibles para el resto del ecosistema MCP (el chat general, el MCP Gateway
externo, Telegram/WhatsApp/Web) — no son exclusivas de la consola de este módulo.

### 3. Una consola de chat en el menú **MCP Gateway**, restringida a su dominio de negocio

- **Chat IA** (`mercas.mcp.chat.wizard`) — **única consola visible por defecto**. Consola de
  ámbito cerrado: **solo** responde preguntas de ventas, compras, facturación y stock. Una
  única llamada corta al LLM clasifica la pregunta en uno de esos 4 dominios (o `otro`) y
  extrae los parámetros de filtrado; si el dominio es `otro`, responde el mensaje fijo *"Sólo
  puedo responder preguntas de VENTAS, COMPRAS, FACTURACIÓN Y STOCK."* sin llamar a ninguna
  tool. Si el dominio es válido, ejecuta la tool determinista correspondiente y formatea el
  resultado en Python — **sin** una segunda llamada de "humanizar" al LLM, por eso los importes
  nunca los redacta/parafrasea la IA (siempre exactos, salen de Odoo). Conversación persistida
  en `ai.bot.conversation` (`platform='web'`, `platform_user_id='backend-<uid>'`).

- **Consultas IA (debug)** (`mercas.mcp.domain.chat.wizard`) — wizard/vista/acción originales,
  **no borrados**: es el código del que se copió la lógica anterior a `ai_chat_wizard.py`. Su
  menú (`mcp_gateway_menu_domain_chat`) lleva `groups="base.group_no_one"`, así que solo
  aparece con el modo desarrollador activo (Ajustes → Activar modo desarrollador, o
  `?debug=1` en la URL). Se mantiene únicamente para depurar/comparar contra `ai_chat_wizard.py`
  sin tener que revertir código; en uso normal ambos wizards se comportan igual, con historiales
  de conversación independientes (`platform_user_id`: `backend-<uid>` vs `domain-<uid>`).

  Históricamente hubo un tercer modo: `ai_chat_wizard.py` usaba `LLMRouter` (el mismo router
  genérico del bot gateway) para elegir libremente entre *cualquier* tool (`ask_ai`,
  `search_records`, `create_record`, `update_record`, `delete_record`, `analyze_records`), y
  humanizaba el resultado con una segunda llamada al LLM. Se retiró porque `LLMRouter` solo
  pasa al modelo la `description` de una línea de cada tool — nunca el `input_schema` — así que
  no tenía forma de conocer parámetros como `only_boxes`, ni las reglas de negocio de
  `prompts.py`, y el paso de "humanizar" arriesgaba a que el LLM alterase cifras ya exactas al
  parafrasearlas. Esa capacidad genérica sigue existiendo en `odoo_mcp_manager` (la usan
  Telegram/WhatsApp/Web bot gateway), simplemente ya no está expuesta en este menú.

Ambas consolas recuerdan la conversación del usuario entre visitas al menú (botón "Nueva
conversación" para archivarla y empezar de cero) y usan siempre el proveedor de IA activo de
mayor prioridad configurado en **MCP Gateway → Providers**.

### 4. Instrucciones de negocio en dos capas

En **Ajustes → MCP Gateway → Chat IA** hay dos campos que se inyectan en el prompt de
clasificación (`_CLASSIFY_PROMPT`, definido igual en `wizard/ai_chat_wizard.py` y en
`wizard/ai_domain_chat_wizard.py`):

- **Instrucciones generales (fijas)** — de solo lectura en el UI, vienen de
  `prompts.py::BASE_BUSINESS_INSTRUCTIONS` (no editable desde Ajustes; para cambiarlas hay que
  tocar ese fichero y actualizar el módulo). Contenido actual:
  - Ceñir la respuesta exclusivamente al producto/cliente/proveedor que se pregunta, sin
    mezclar cifras de otros.
  - "Cajas" o "envases" no son un nombre de producto: se traducen al parámetro
    `only_boxes: true` del dominio `stock` (filtra `product_id.is_box = True`, campo de
    `mercas_base`), dejando `product` vacío salvo que además se nombre un producto concreto.
- **Instrucciones personalizadas** — campo de texto libre editable, guardado en
  `ir.config_parameter` (`mercas_mcp_chat.custom_instructions`) vía `get_values`/`set_values`
  en `models/res_config_settings.py`. Se añade al prompt en cada consulta.

  ⚠️ Los campos de settings que se persisten como `ir.config_parameter` con el atajo
  `config_parameter="..."` **solo admiten** boolean/integer/float/char/selection/many2one/
  datetime — un `fields.Text` con ese atajo revienta `res.config.settings` en cuanto alguien
  abre Ajustes (`Exception: Field ... must have type ...`). Por eso este campo usa
  `get_values`/`set_values` manuales en vez del atajo. Si se añade algún campo de texto largo
  más a settings en este módulo, seguir el mismo patrón.

### 5. Widgets de chat (`static/src/js/chat_fields.js`)

Dos widgets de campo (Owl) usados en ambas vistas de wizard:

- `mercas_chat_history` (en `history_display`, tipo Html): envuelve el contenido en un
  `<div class="o_mercas_chat_history">` con scroll propio (`max-height: 60vh`) y lo desplaza
  al fondo en cada montaje/actualización (`useEffect` sobre `el.scrollTop = el.scrollHeight`).
- `mercas_chat_message` (en `message`, extiende el `TextField` estándar): añade un listener de
  `keydown` que, con Ctrl+Enter o Cmd+Enter, guarda el valor en el registro
  (`record.update(...)`) y hace click en el botón con clase `o_mercas_chat_send` (el "Enviar"
  de cada formulario) — de ahí que ambos botones "Enviar" lleven esa clase además de
  `btn-primary`.

Ambas vistas de formulario (`ai_chat_wizard_views.xml`, `ai_domain_chat_wizard_views.xml`)
deliberadamente no usan `<sheet>`: desde Odoo 16.3, un `<form>` sin `<sheet>` recibe
automáticamente la clase `o_form_nosheet` (`form_compiler.js`), que ocupa todo el ancho
disponible en vez del `max-width` centrado que aplica `.o_form_sheet_bg`
(`form_controller.scss`). Es el mecanismo soportado por el framework, no un CSS a mano — si se
le vuelve a añadir `<sheet>`, el chat volverá a quedarse estrecho.

## Limitaciones conocidas

- **`stock_report` sin filtro de producto ni `only_boxes`**: si no se especifica ninguno de
  los dos, la cantidad total se suma entre productos que pueden tener unidades de medida
  distintas (unidades, kg, litros…) y no se muestra ninguna UdM en el resumen. Es una
  simplificación deliberada para mantener la tool ligera.
- **`invoice_report` y ambigüedad cliente/proveedor**: si la pregunta no dice si son facturas
  emitidas o recibidas, se traen ambas mezcladas (`move_type='all'`). El clasificador intenta
  inferirlo, pero en preguntas ambiguas puede no acertar.
- **Tras instalar o actualizar el módulo, si Odoo ya estaba en marcha, hace falta reiniciar el
  proceso.** El mecanismo estándar de Odoo para que un proceso vivo recargue su registro tras
  cambios hechos desde otro proceso (`orm_signaling_registry`) no se ha mostrado fiable en este
  entorno de desarrollo — el proceso en marcha puede seguir sirviendo el registro antiguo
  (`KeyError` / 404 en el modelo, o una vista/campo desactualizado) pese a que la base de datos
  ya tiene el módulo actualizado. Reiniciar el proceso de Odoo lo soluciona siempre; hasta ahora
  no se ha encontrado una vía fiable de forzarlo en caliente en este entorno.
- La primera pregunta tras un rato de inactividad de Ollama tarda notablemente más (~20-60 s):
  es el tiempo que tarda Ollama en recargar el modelo en memoria, no algo controlable desde
  este módulo.
- El comportamiento de los widgets JS (auto-scroll, atajo de teclado) no se ha verificado en
  un navegador real — ver sección "Estado / continuidad" arriba.

## Ampliar a un nuevo dominio

1. Añadir una tool determinista nueva en `models/ai_tool.py` (`_execute_builtin` + método
   `_builtin_<nombre>`), siguiendo el patrón de `_read_group_amount` si es un total monetario.
2. Registrar el `ai.tool` correspondiente en un XML de datos (ver
   `data/ai_tool_domain_reports.xml`).
3. En `wizard/ai_chat_wizard.py` (consola visible): añadir la clave a `_DOMAIN_TOOL`, describir
   el dominio en `_CLASSIFY_PROMPT`, y añadir el caso en `_build_tool_params` / `_format_result`.
   Replicar el mismo cambio en `wizard/ai_domain_chat_wizard.py` (el gemelo debug-only) para que
   no se desincronicen — ambos ficheros llevan una copia literal de esta lógica a propósito, ver
   sección 3.
4. Si el dominio necesita su propio glosario de negocio, añadirlo a
   `prompts.py::BASE_BUSINESS_INSTRUCTIONS` en vez de tocar `_CLASSIFY_PROMPT` directamente
   (esto sí lo comparten ambos wizards, no hay que duplicarlo).

No hace falta tocar `odoo_mcp_manager`.
