
def require_admin(ctx):
    if ctx["perfil"] != "admin":
        raise PermissionError("Acesso restrito ao administrador.")


