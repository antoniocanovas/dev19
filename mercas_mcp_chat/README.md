# Mercas MCP Chat

Consolas de chat con IA integradas en el propio backend de Odoo, construidas sobre
`odoo_mcp_manager` (el MCP Gateway de Cybrosys). No requiere clientes externos (Claude
Desktop, curl, etc.) ni tener configurada una MCP API Key: todo se ejecuta por ORM dentro
del propio proceso de Odoo.

## Estado / continuidad (para retomar la sesión)

Todo lo descrito en este README está implementado y probado **por ORM** (`odoo-bin shell`,
simulando exactamente lo que hace cada botón). Lo único que **no** se ha podido verificar de
primera mano es el comportamiento en un navegador real: el entorno de agente usado en estas
sesiones no tiene ruta de red hacia `localhost:8069` de esta máquina (confirmado con
`ERR_CONNECTION_REFUSED` navegando a `localhost`/`127.0.0.1`, mientras `curl` desde el propio
Mac sí llega sin problema). En concreto, pendiente de que el usuario confirme visualmente:

- **Auto-scroll del historial** (`static/src/js/chat_fields.js`, widget
  `mercas_chat_history`): al enviar un mensaje, el cuadro de conversación debería quedarse
  desplazado abajo del todo (última respuesta visible) en vez de arriba del todo.
- **Atajo de teclado Ctrl+Enter / Cmd+Enter** (widget `mercas_chat_message`, mismo fichero):
  debería enviar el formulario sin necesidad de hacer click en "Enviar". Comprobado que el
  bundle de assets se sirve sin 404 (`/mercas_mcp_chat/static/src/js/chat_fields.js` etc.) y
  que el JS/XML son sintácticamente válidos, pero no se ha ejecutado en un navegador real.

Si algo de esto no funciona tal cual al probarlo, lo más probable es un detalle de la API de
Owl/`TextField` de esta build concreta de Odoo 19 (nombres de refs, timing del hook
`useInputField`) — revisar `chat_fields.js` con el navegador abierto y la consola de errores.

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

### 3. Dos consolas de chat en el menú **MCP Gateway**

- **Chat IA** (`mercas.mcp.chat.wizard`) — asistente de propósito general: usa el mismo
  `LLMRouter` y el mismo catálogo de tools que el bot gateway (`ask_ai`, `search_records`,
  `create_record`, etc.), pero llamando a `ai.tool.execute()` directamente por ORM en vez de
  saltar por HTTP a `/mcp_gateway`, así que no hace falta una MCP API Key solo para usar esta
  pantalla. Conversación persistida en `ai.bot.conversation` (`platform='web'`,
  `platform_user_id='backend-<uid>'`).

- **Consultas IA** (`mercas.mcp.domain.chat.wizard`) — consola de ámbito cerrado: **solo**
  responde preguntas de ventas, compras, facturación y stock. Una única llamada corta al LLM
  clasifica la pregunta en uno de esos 4 dominios (o `otro`) y extrae los parámetros de
  filtrado; si el dominio es `otro`, responde el mensaje fijo *"Sólo puedo responder preguntas
  de VENTAS, COMPRAS, FACTURACIÓN Y STOCK."* sin llamar a ninguna tool. Si el dominio es válido,
  ejecuta la tool determinista correspondiente y formatea el resultado en Python — **sin**
  una segunda llamada de "humanizar", por eso es notablemente más rápida que el Chat IA
  general (una sola llamada al modelo por pregunta, en vez de dos). Conversación persistida en
  `ai.bot.conversation` con `platform_user_id='domain-<uid>'`.

Ambas consolas recuerdan la conversación del usuario entre visitas al menú (botón "Nueva
conversación" para archivarla y empezar de cero) y usan siempre el proveedor de IA activo de
mayor prioridad configurado en **MCP Gateway → Providers** (en este entorno, Ollama +
`gemma4:latest`).

### 4. Instrucciones de negocio en dos capas (solo "Consultas IA")

En **Ajustes → MCP Gateway → Consultas IA** hay dos campos que se inyectan en el prompt de
clasificación (`_CLASSIFY_PROMPT` en `wizard/ai_domain_chat_wizard.py`):

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
3. En `wizard/ai_domain_chat_wizard.py`: añadir la clave a `_DOMAIN_TOOL`, describir el dominio
   en `_CLASSIFY_PROMPT`, y añadir el caso en `_build_tool_params` / `_format_result`.
4. Si el dominio necesita su propio glosario de negocio, añadirlo a
   `prompts.py::BASE_BUSINESS_INSTRUCTIONS` en vez de tocar `_CLASSIFY_PROMPT` directamente.

No hace falta tocar `odoo_mcp_manager`.
