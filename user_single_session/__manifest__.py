{
    'name': 'User Single Session',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'license': 'AGPL-3',
    'summary': 'Restringe a los usuarios a una única sesión activa por login',
    'description': """
Sesión única por usuario
=========================

Si un usuario inicia sesión mientras ya tiene otra sesión activa en otro
dispositivo/navegador, se le muestra -tras validar sus credenciales- la
lista de sesiones abiertas con la opción de cerrarlas una a una o todas
de golpe. Hasta que no quede ninguna otra sesión activa, no se le concede
acceso al backend.

Se apoya en el registro nativo de sesiones de Odoo (``res.device.log`` /
``res.device``), reutilizando el mismo mecanismo que usa ``auth_totp``
para forzar un paso adicional antes de finalizar el login
(``res.users._mfa_url()``).
""",
    'author': 'Serincloud',
    'website': 'https://ingenieriacloud.com',
    'depends': ['web'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/single_session_templates.xml',
    ],
    'installable': True,
    'application': False,
}
