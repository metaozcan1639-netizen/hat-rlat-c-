import os
from datetime import date
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Görev ve Takvim Etkinlikleri
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    task_date = Column(Date, default=date.today)
    is_completed = Column(Boolean, default=False)

# Bağımsız Notlar
class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    created_at = Column(Date, default=date.today)

Base.metadata.create_all(bind=engine)
app = FastAPI()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Takip & Not Paneli</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
</head>
<body class="bg-gray-950 text-gray-100 p-4 md:p-8 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-6">
    
    <!-- Üst Panel: Takvim ve Görevler -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Sol: Görev Ekle & İlerleme Listesi -->
      <div class="space-y-6">
        <!-- Görev Ekleme Kartı -->
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
          <h2 class="text-lg font-bold mb-3 text-cyan-400">📅 Yeni Takvim / Hedef</h2>
          <form action="/task/add" method="POST" class="space-y-3">
            <input type="text" name="title" placeholder="Hedef veya etkinlik başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm focus:outline-none focus:border-cyan-500">
            <input type="date" name="task_date" value="{{ today }}" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm focus:outline-none focus:border-cyan-500">
            <textarea name="description" placeholder="Açıklama (opsiyonel)..." rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm focus:outline-none focus:border-cyan-500"></textarea>
            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-2 rounded font-semibold text-sm transition">Takvime Ekle</button>
          </form>
        </div>

        <!-- Görev Listesi & Silme -->
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
          <h3 class="text-md font-bold mb-3 text-gray-200">İlerlemeler & Görevler</h3>
          <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
            {% for task in tasks %}
            <div class="flex items-center justify-between p-2.5 bg-gray-800/60 rounded border border-gray-700 text-sm">
              <div class="flex flex-col">
                <span class="{{ 'line-through text-gray-500' if task.is_completed else 'text-gray-100' }} font-medium">{{ task.title }}</span>
                <span class="text-xs text-gray-400">{{ task.task_date }}</span>
              </div>
              <div class="flex items-center gap-2">
                <a href="/task/toggle/{{ task.id }}" class="text-xs px-2 py-1 {{ 'bg-emerald-700' if task.is_completed else 'bg-gray-700 hover:bg-cyan-600' }} rounded transition">
                  {{ '✓' if task.is_completed else 'Yap' }}
                </a>
                <a href="/task/delete/{{ task.id }}" onclick="return confirm('Bu görevi silmek istediğine emin misin?');" class="text-xs px-2 py-1 bg-rose-950/60 hover:bg-rose-600 text-rose-300 hover:text-white rounded border border-rose-800 transition">
                  Sil
                </a>
              </div>
            </div>
            {% endfor %}
            {% if not tasks %}
            <p class="text-xs text-gray-500 text-center py-4">Henüz görev eklenmedi.</p>
            {% endif %}
          </div>
        </div>
      </div>

      <!-- Sağ: Takvim -->
      <div class="lg:col-span-2 bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <div id="calendar"></div>
      </div>
    </div>

    <!-- Alt Panel: Not Defteri Bölümü -->
    <div class="bg-gray-900 p-6 rounded-xl border border-gray-800 shadow-md">
      <div class="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
        <h2 class="text-xl font-bold text-amber-400">📝 Not Defteri</h2>
        <span class="text-xs text-gray-400">{{ notes|length }} kayıtlı not</span>
      </div>

      <!-- Not Ekleme Formu -->
      <form action="/note/add" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6 bg-gray-800/40 p-4 rounded-lg border border-gray-800">
        <div class="md:col-span-1">
          <input type="text" name="title" placeholder="Not başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm focus:outline-none focus:border-amber-400">
        </div>
        <div class="md:col-span-2">
          <textarea name="content" placeholder="Ayrıntılı not, fikirler, kod parçaları..." rows="1" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm focus:outline-none focus:border-amber-400"></textarea>
        </div>
        <div class="md:col-span-1">
          <button type="submit" class="w-full h-full bg-amber-600 hover:bg-amber-500 py-2 rounded font-semibold text-sm transition">Notu Kaydet</button>
        </div>
      </form>

      <!-- Not Kartları Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        {% for note in notes %}
        <div class="bg-gray-800/50 p-4 rounded-lg border border-gray-700/80 flex flex-col justify-between hover:border-gray-600 transition">
          <div>
            <div class="flex justify-between items-start mb-2">
              <h4 class="font-semibold text-amber-300 text-sm">{{ note.title }}</h4>
              <span class="text-[11px] text-gray-400">{{ note.created_at }}</span>
            </div>
            <p class="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">{{ note.content }}</p>
          </div>
          <div class="mt-4 pt-2 border-t border-gray-700/50 flex justify-end">
            <a href="/note/delete/{{ note.id }}" onclick="return confirm('Bu notu silmek istediğine emin misin?');" class="text-xs text-rose-400 hover:text-rose-300">
              Sil 🗑
            </a>
          </div>
        </div>
        {% endfor %}
        {% if not notes %}
        <p class="text-xs text-gray-500 col-span-3 text-center py-6">Kayıtlı not bulunmuyor.</p>
        {% endif %}
      </div>
    </div>

  </div>

  <script>
    document.addEventListener('DOMContentLoaded', function() {
      var calendarEl = document.getElementById('calendar');
      var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'tr',
        height: 480,
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
    tasks = db.query(Task).order_by(Task.task_date.desc()).all()
    notes = db.query(Note).order_by(Note.id.desc()).all()
    db.close()
    
    t = Template(HTML_TEMPLATE)
    return t.render(tasks=tasks, notes=notes, today=date.today().isoformat())

# Görev İşlemleri
@app.post("/task/add")
def add_task(title: str = Form(...), description: str = Form(""), task_date: str = Form(...)):
    db = SessionLocal()
    new_task = Task(title=title, description=description, task_date=date.fromisoformat(task_date))
    db.add(new_task)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/task/toggle/{task_id}")
def toggle_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.is_completed = not task.is_completed
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/task/delete/{task_id}")
def delete_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

# Not İşlemleri
@app.post("/note/add")
def add_note(title: str = Form(...), content: str = Form("")):
    db = SessionLocal()
    new_note = Note(title=title, content=content, created_at=date.today())
    db.add(new_note)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/note/delete/{note_id}")
def delete_note(note_id: int):
    db = SessionLocal()
    note = db.query(Note).filter(Note.id == note_id).first()
    if note:
        db.delete(note)
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

# Takvim API'si
@app.get("/api/events")
def get_events():
    db = SessionLocal()
    tasks = db.query(Task).all()
    db.close()
    return [
        {
            "id": t.id,
            "title": f"{'✓ ' if t.is_completed else ''}{t.title}",
            "start": t.task_date.isoformat(),
            "color": "#059669" if t.is_completed else "#0284c7"
        }
        for t in tasks
    ]
