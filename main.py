from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime,Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime 
import shutil, uuid, os

DATABASE_URL = "postgresql://postgres:CJIzUofmYwJiWzpvxPxyhdNZEKLoRZHn@metro.proxy.rlwy.net:15598/railway"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 👈 allow ALL domains
    allow_credentials=False,  # must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="dy2zq2rdt",
    api_key="583655695519391",
    api_secret="rmtvnqj1Axbcaob4EAKU692__3I"
)


class Celebration(Base):
    __tablename__ = "celebration"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)   # 👈 add this
    image = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    
class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    image = Column(String, nullable=False)
    position = Column(Integer, nullable=False)  # 👈 for ordering
    created_at = Column(DateTime, default=datetime.utcnow)
    
# 🗄️ Model
from sqlalchemy import Column, Integer, String, Text, DateTime

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    thumbnail = Column(String, nullable=True)

    excerpt = Column(String, nullable=True)   # 🔥 new
    tags = Column(String, nullable=True)      # 🔥 comma separated

    created_at = Column(DateTime, default=datetime.utcnow)
    

Base.metadata.create_all(bind=engine)

# DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 🖼️ Upload Image
@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    print("uploading...")
    result = cloudinary.uploader.upload(file.file)
    print("uploaded")

    return {
        "url": result["secure_url"]
    }


import re

def generate_excerpt(html):
    text = re.sub('<[^<]+?>', '', html)
    return text[:120] + "..." if len(text) > 120 else text
    
# ➕ Create
@app.post("/posts")
def create_post(
    title: str = Form(...),
    content: str = Form(...),
    thumbnail: str = Form(None),
    tags: str = Form(""),
    db: Session = Depends(get_db)
):
    excerpt = generate_excerpt(content)

    post = Post(
        title=title,
        content=content,
        thumbnail=thumbnail,
        excerpt=excerpt,
        tags=tags
    )

    db.add(post)
    db.commit()
    db.refresh(post)
    return post                                                   
# 📖 Get all
@app.get("/posts")
def get_posts(page: int = 1, limit: int = 6, tag: str = None, db: Session = Depends(get_db)):

    query = db.query(Post)

    # 🏷️ filter by tag
    if tag:
        query = query.filter(Post.tags.like(f"%{tag}%"))

    total = query.count()

    posts = query.order_by(Post.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": posts
    }

# 📄 Get one
@app.get("/posts/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Not found")
    print(post)        
    return post

@app.put("/posts/{post_id}")
def update_post(
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    thumbnail: str = Form(None),
    tags: str = Form(""),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(404, "Not found")

    post.title = title
    post.content = content
    post.tags = tags

    if thumbnail:
        post.thumbnail = thumbnail

    # regenerate excerpt
    post.excerpt = generate_excerpt(content)

    db.commit()
    return {"message": "Updated"}
    

# ❌ Delete
@app.delete("/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Not found")

    db.delete(post)
    db.commit()
    return {"message": "Deleted"}

@app.post("/achievements")
def add_achievement(title: str = Form(...), image: str = Form(...), db: Session = Depends(get_db)):

    # shift all down
    db.query(Achievement).update({
        Achievement.position: Achievement.position + 1
    })

    # delete if more than 5
    items = db.query(Achievement).order_by(Achievement.position.asc()).all()
    if len(items) >= 5:
        last = db.query(Achievement).order_by(Achievement.position.desc()).first()
        db.delete(last)

    # ✅ FIX: set position = 1
    ach = Achievement(
        title=title,
        image=image,
        position=1   # 🔥 IMPORTANT
    )

    db.add(ach)
    db.commit()
    return ach

@app.get("/achievements")
def get_achievements(db: Session = Depends(get_db)):
    return db.query(Achievement).order_by(Achievement.position.asc()).all()                          

@app.delete("/achievements/{id}")
def delete_achievement(id: int, db: Session = Depends(get_db)):
    ach = db.query(Achievement).filter(Achievement.id == id).first()
    if not ach:
        raise HTTPException(404, "Not found")

    db.delete(ach)
    db.commit()
    return {"message": "Deleted"}                                            
@app.put("/achievements/{id}/move")
def move_achievement(id: int, direction: str, db: Session = Depends(get_db)):

    ach = db.query(Achievement).filter(Achievement.id == id).first()

    if not ach:
        raise HTTPException(404, "Not found")

    if direction == "up":
        other = db.query(Achievement)\
            .filter(Achievement.position < ach.position)\
            .order_by(Achievement.position.desc()).first()

    elif direction == "down":
        other = db.query(Achievement)\
            .filter(Achievement.position > ach.position)\
            .order_by(Achievement.position.asc()).first()

    else:
        raise HTTPException(400, "Invalid direction")

    if other:
        ach.position, other.position = other.position, ach.position
        db.commit()

    return {"message": "Moved"}    

@app.post("/celebration")
def set_celebration(
    title: str = Form(...),
    image: str = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db)
):
    existing = db.query(Celebration).first()

    if existing:
        existing.title = title
        existing.image = image
        existing.is_active = is_active
    else:
        new = Celebration(title=title, image=image, is_active=is_active)
        db.add(new)

    db.commit()
    return {"message": "Saved"}

@app.put("/celebration/toggle")
def toggle_celebration(is_active: bool = Form(...), db: Session = Depends(get_db)):
    item = db.query(Celebration).first()
    if not item:
        raise HTTPException(404, "Not found")

    item.is_active = is_active
    db.commit()
    return {"message": "Updated"}

@app.get("/celebration")
def get_celebration(db: Session = Depends(get_db)):
    return db.query(Celebration).first()
    
@app.delete("/celebration")
def delete_celebration(db: Session = Depends(get_db)):
    item = db.query(Celebration).first()

    if not item:
        raise HTTPException(404, "Not found")

    db.delete(item)
    db.commit()

    return {"message": "Deleted"} 

                                                                           

