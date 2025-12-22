import uuid
from app.core.auth import hash_password
from app.db import SessionLocal
from app.models import Tenant, User, UserRole


def seed():
    session = SessionLocal()
    tenant = Tenant(id="demo", name="Demo Tenant", default_currency="USD")
    session.merge(tenant)
    users = [
        ("admin@demo.com", UserRole.ADMIN),
        ("ops@demo.com", UserRole.OPS),
        ("analyst@demo.com", UserRole.ANALYST),
        ("auditor@demo.com", UserRole.AUDITOR),
        ("readonly@demo.com", UserRole.READ_ONLY),
    ]
    for email, role in users:
        existing = session.query(User).filter_by(tenant_id=tenant.id, email=email).one_or_none()
        user_id = existing.id if existing else str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
        user = User(
            id=user_id,
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password"),
            role=role,
        )
        session.merge(user)
    session.commit()
    session.close()


if __name__ == "__main__":
    seed()
