import os
from datetime import date
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date
from sqlalchemy.orm import declarative_base, sessionmaker

# Neon.tech veya Supabase connection string'i Render ortam değişkenlerinden (DATABASE_URL) alacak
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_test.db")
# Render'daki postgres:// protokolünü SQLAlchemy postgresql:// olarak bekler:
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Entry(Base):
    __tablename__ = "entries"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    entry_date = Column(Date, default=date.today)
    is_completed = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)
app = FastAPI()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Kişisel Takip Paneli</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
</head>
<body class="bg-gray-900 text-gray-100 p-4 md:p-8">
  <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
    
    <!-- Sol Panel: Yeni Kayıt Ekle & İlerleme Listesi -->
    <div class="space-y-6">
      <div class="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg">
        <h2 class="text-xl font-bold mb-4 text-cyan-400">Yeni Görev / Not</h2>
        <form action="/add" method="POST" class="space-y-3">
          <input type="text" name="title" placeholder="Başlık / Görev" required class="w-full bg-gray-700 border border-gray-600 rounded p-2 text-sm focus:outline-none focus:border-cyan-400">
          <textarea name="content" placeholder="Not veya detay..." rows="3" class="w-full bg-gray-700 border border-gray-600 rounded p-2 text-sm focus:outline-none focus:border-cyan-400"></textarea>
          <input type="date" name="entry_date" value="{{ today }}" class="w-full bg-gray-700 border border-gray-600 rounded p-2 text-sm focus:outline-none focus:border-cyan-400">
          <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-2 rounded font-semibold text-sm transition">Kaydet</button>
        </form>
      </div>

      <!-- İlerleme Özeti -->
      <div class="bg-gray-800 p-5 rounded-xl border border-gray-700">
        <h3 class="text-lg font-bold mb-3 text-cyan-400">İlerlemeler</h3>
        <div class="space-y-2 max-h-72 overflow-y-auto">
          {% for item in items %}
          <div class="flex items-center justify-between p-2 bg-gray-700/50 rounded border border-gray-700 text-sm">
            <span class="{{ 'line-through text-gray-400' if item.is_completed else 'text-gray-100' }}">{{ item.title }}</span>
            <div class="flex gap-2">
              <a href="/toggle/{{ item.id }}" class="text-xs px-2 py-1 bg-gray-600 hover:bg-cyan-600 rounded">
                {{ 'Geri Al' if item.is_completed else 'Tamamla' }}
              </a>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Sağ Panel: Takvim Görünümü -->
    <div class="md:col-span-2 bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg">
      <div id="calendar"></div>
    </div>
  </div>

  <script>
    document.addEventListener('DOMContentLoaded', function() {
      var calendarEl = document.getElementById('calendar');
      var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        themeSystem: 'standard',
        events: '/api/events',
        headerToolbar: {
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek'
        }
      });
      calendar.render();
    });
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    from jinja2 import Template
    db = SessionLocal()
    items = db.query(Entry).order_by(Entry.entry_date.desc()).all()
    db.close()
    
    t = Template(HTML_TEMPLATE)
    return t.render(items=items, today=date.today().isoformat())

@app.post("/add")
def add_entry(title: str = Form(...), content: str = Form(""), entry_date: str = Form(...)):
    db = SessionLocal()
    new_entry = Entry(title=title, content=content, entry_date=date.fromisoformat(entry_date))
    db.add(new_entry)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/toggle/{item_id}")
def toggle_item(item_id: int):
    db = SessionLocal()
    item = db.query(Entry).filter(Entry.id == item_id).first()
    if item:
        item.is_completed = not item.is_completed
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/events")
def get_events():
    db = SessionLocal()
    items = db.query(Entry).all()
    db.close()
    return [
        {
            "id": i.id,
            "title": f"{'✓ ' if i.is_completed else ''}{i.title}",
            "start": i.entry_date.isoformat(),
            "color": "#10b981" if i.is_completed else "#0284c7"
        }
        for i in items
    ]