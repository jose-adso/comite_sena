# Routes package — importar todos los módulos para registrar las rutas en auth_bp
from routes.auth import auth_bp
import routes.admin          # noqa: F401
import routes.reclamos       # noqa: F401
import routes.historial_reclamos  # noqa: F401
import routes.notificaciones  # noqa: F401
import routes.registrar_falla  # noqa: F401
import routes.password       # noqa: F401

__all__ = ['auth_bp']
