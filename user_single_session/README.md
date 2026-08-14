# User Single Session

Restringe a cada usuario interno a **una única sesión activa** a la vez. Si alguien
inicia sesión mientras ya tiene otra abierta en otro dispositivo/navegador, tras
validar sus credenciales se le muestra la lista de sesiones abiertas con la opción
de cerrarlas una a una o todas de golpe. Hasta que no quede ninguna otra sesión
activa, no se le concede acceso al backend.

## Dependencias

Solo `web` (módulo `base`, que ya viene con `web`). No añade modelos nuevos: se
apoya por completo en el registro nativo de sesiones de Odoo 19,
`res.device.log` / `res.device` (`odoo/addons/base/models/res_device.py`), el
mismo que alimenta la lista de "Devices" del formulario de usuario.

## Cómo funciona

`Session.authenticate()` (`odoo/http.py`) valida el login, guarda el usuario en
`session['pre_uid']` y, **antes de finalizar la sesión** (asignar `session['uid']`),
llama a `user._mfa_url()`. Si ese método devuelve una URL, la sesión se queda a
medias y el usuario es redirigido ahí en vez de entrar al backend — es el mismo
mecanismo que usa `auth_totp` para forzar el paso del código de verificación en
dos pasos.

Este módulo engancha ahí:

1. **`models/res_users.py`** — override de `_mfa_url()`: llama primero a
   `super()` (respeta cualquier otro paso de login que ya exista, p. ej. un 2FA
   instalado); si no hay nada pendiente y se cumplen las condiciones
   (`_must_close_other_sessions()`), devuelve `/web/login/single_session`.
   Las condiciones son: el toggle global está activo, el usuario es interno
   (`_is_internal()`), no tiene marcada la excepción `allow_multi_session`, y
   `res.device` (sudo) devuelve al menos un dispositivo con
   `session_identifier` distinto al de la sesión que se está autenticando.

2. **`controllers/home.py`** — ruta pública `/web/login/single_session`
   (calcada de `/web/login/totp` de `auth_totp`). En GET lista las sesiones
   ajenas; en POST revoca la indicada (`revoke_device_id`) o todas
   (`revoke_all`) reutilizando `res.device._revoke()` — la misma lógica que ya
   usa el botón nativo "Log out from all devices" (borra el session file del
   disco y marca `revoked=True`). En cuanto no queda ninguna sesión ajena
   activa, llama a `request.session.finalize()` y redirige al backend.

3. **`views/single_session_templates.xml`** — plantilla QWeb de la página de
   bloqueo (`web.login_layout`), con un botón "Cerrar sesión" por dispositivo,
   un botón "Cerrar el resto de sesiones y continuar", y un enlace para
   cancelar el login (logout) y probar con otra cuenta.

4. **Ajustes → General Settings → bloque "Sesión única"** — checkbox que
   activa/desactiva la política para todos los usuarios internos
   (`ir.config_parameter` `user_single_session.enforce`).

5. **Ficha de usuario → pestaña Seguridad** (solo visible para
   Ajustes/System) — checkbox "Permitir varias sesiones para este usuario"
   (`allow_multi_session`), para exceptuar cuentas técnicas o de integración
   sin tener que desactivar la política global.

Nada de esto crea modelos, tablas ni reglas de acceso nuevas: reutiliza
`res.device`/`res.device.log` y sus `ir.rule` ya existentes en `base`.

## Limitaciones conocidas

- **Interacción con `auth_totp` (2FA)**: `_mfa_url()` se evalúa una sola vez,
  al validar la contraseña. El override de este módulo llama a `super()`
  primero, así que si el usuario tiene 2FA activo, el paso de TOTP se resuelve
  primero y su controlador (`auth_totp`) llama a `session.finalize()`
  directamente sin volver a pasar por aquí — es decir, con ambos módulos
  instalados para el mismo usuario, el gate de sesión única **no** se aplica
  en ese login. Sin `auth_totp` instalado (o para usuarios sin 2FA activo) no
  hay ningún conflicto.
- No se ha podido probar en navegador real (arranque/parada de `odoo-bin` lo
  gestiona el usuario). Verificar visualmente el flujo completo
  (login → página de bloqueo → cierre de sesiones → acceso) antes de darlo
  por definitivo.
- La condición de "otra sesión activa" se calcula excluyendo el
  `session_identifier` de la sesión que se está autenticando, no un usuario
  "actual" (todavía no existe `uid` en ese punto del login). Si el navegador
  reutiliza cookies de sesión de formas atípicas (proxies, testing headless
  compartiendo cookie jar, etc.) conviene revisar `_get_other_active_devices()`
  en `models/res_users.py`.

## Instalación / prueba

1. Asegurar que `dev19` está en el `addons_path`.
2. Instalar el módulo (o `-u user_single_session` si Odoo ya está en marcha —
   reiniciar el proceso).
3. Activar el checkbox en **Ajustes → General Settings → Sesión única**.
4. Iniciar sesión con un usuario en dos navegadores/perfiles distintos: el
   segundo login debe quedar bloqueado en `/web/login/single_session` hasta
   cerrar la primera sesión.
