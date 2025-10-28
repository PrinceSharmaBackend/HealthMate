from app import db, bcrypt, User

name = "Admin"
email = "admin@healthcare.com"
password = bcrypt.generate_password_hash("admin123").decode('utf-8')

admin = User(name=name, email=email, password=password, is_admin=True)
db.session.add(admin)
db.session.commit()
print("✅ Admin created successfully:", email)