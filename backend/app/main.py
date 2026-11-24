import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import User
from .routes import router
from .security import hash_password
from .telemetry import register_middleware, setup_telemetry

log = logging.getLogger("app")


def seed_admin():
    email = os.getenv("ADMIN_EMAIL", "admin@tienda.com")
    password = os.getenv("ADMIN_PASSWORD", "Admin123!")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(name="Administrador", email=email, role="admin",
                        password_hash=hash_password(password)))
            db.commit()
            log.info("Usuario admin creado", extra={"endpoint": "seed"})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    seed_admin()
    yield


app = FastAPI(title="Tienda API", version=os.getenv("APP_VERSION", "dev"), lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
register_middleware(app)
setup_telemetry(app, engine)
app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": app.version}
