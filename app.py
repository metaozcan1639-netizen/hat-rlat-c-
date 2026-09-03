import os
import secrets
from datetime import date, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Veritabanı Yapılandırması ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_tracker.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    task_date = Column(Date, default=date.today)
    is_completed = Column(Boolean, default=False)

class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default="Genel")
    content = Column(Text, default="")
    created_at = Column(Date, default=date.today)

Base.metadata.create_all(bind=engine)

# --- Güvenlik: HTTP Basic Auth ---
security = HTTPBasic()
AUTH_USERNAME = os.getenv("APP_USER", "admin")
AUTH_PASSWORD = os.getenv("APP_PASSWORD", "1234")

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, AUTH_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, AUTH_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetkisiz erişim",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(dependencies=[Depends(authenticate)])

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kişisel Çalışma & Takip Paneli</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- FullCalendar -->
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
  <!-- Markdown Renderer -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    .markdown-body pre { background-color: #1f2937; padding: 0.5rem; border-radius: 0.375rem; overflow-x: auto; margin: 0.5rem 0; }
    .markdown-body code { font-family: monospace; color: #38bdf8; font-size: 0.85rem; }
    .markdown-body ul { list-style-type: disc; margin-left: 1.25rem; }
    .markdown-body ol { list-style-type: decimal; margin-left: 1.25rem; }
    .markdown-body h1, .markdown-body h2 { font-weight: bold; color: #fbbf24; margin-top: 0.5rem; }
  </style>
</head>
<body class="bg-gray-950 text-gray-100 p-3 md:p-6 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Üst İlerleme & İstatistik Barı -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-lg">
      <div class="flex items-center gap-4">
        <div class="bg-emerald-950/80 border border-emerald-600/40 px-4 py-2 rounded-lg">
          <span class="text-xs text-emerald-400 block font-semibold uppercase tracking-wider">Aktif Streak</span>
          <span class="text-2xl font-black text-emerald-300">{{ streak }} Gün 🔥</span>
        </div>
        <div>
          <h1 class="text-lg font-bold text-gray-200">Kişisel Dashboard</h1>
          <p class="text-xs text-gray-400">Son 30 Günlük Aktivite & Odaklanma</p>
        </div>
      </div>

      <!-- GitHub Tarzı Mini Heatmap (Son 30 Gün) -->
      <div class="flex items-center gap-1.5 overflow-x-auto py-1">
        {% for day in heatmap_days %}
          <div title="{{ day.date }}: {{ day.count }} tamamlanan" 
               class="w-3.5 h-3.5 rounded-sm transition-transform hover:scale-125
               {% if day.count == 0 %}bg-gray-800 border border-gray-700/50
               {% elif day.count == 1 %}bg-emerald-900 border border-emerald-700
               {% elif day.count == 2 %}bg-emerald-600
               {% else %}bg-emerald-400{% endif %}">
          </div>
        {% endfor %}
      </div>
    </div>

    <!-- Orta Alan: Sol Araçlar & Sağ Takvim -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <div class="space-y-6">
        <!-- Pomodoro Timer -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md text-center">
          <div class="flex justify-between items-center mb-2">
            <h3 class="text-xs font-bold uppercase tracking-wider text-rose-400">🍅 Pomodoro Sayacı</h3>
            <span id="pomoMode" class="text-xs px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800">Çalışma (25 dk)</span>
          </div>
          <div id="pomoTimer" class="text-4xl font-mono font-bold tracking-widest text-gray-100 my-2">25:00</div>
          <div class="flex justify-center gap-2">
            <button onclick="startPomodoro()" class="bg-rose-600 hover:bg-rose-500 text-xs font-semibold px-4 py-1.5 rounded transition">Başlat</button>
            <button onclick="pausePomodoro()" class="bg-gray-700 hover:bg-gray-600 text-xs font-semibold px-4 py-1.5 rounded transition">Duraklat</button>
            <button onclick="resetPomodoro()" class="bg-gray-800 hover:bg-gray-700 text-xs font-semibold px-3 py-1.5 rounded text-gray-400 transition">Sıfırla</button>
          </div>
        </div>

        <!-- Görev / Takvim Girdisi -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h2 class="text-sm font-bold mb-3 text-cyan-400">📅 Yeni Takvim Hedefi</h2>
          <form action="/task/add" method="POST" class="space-y-2.5">
            <input type="text" name="title" placeholder="Hedef / Yapılacak iş" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            <input type="date" name="task_date" value="{{ today }}" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            <textarea name="description" placeholder="Açıklama veya kriter..." rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500"></textarea>
            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-1.5 rounded font-semibold text-xs transition">Takvime Kaydet</button>
          </form>
        </div>

        <!-- Görev Listesi -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h3 class="text-sm font-bold mb-2 text-gray-200">İlerlemeler</h3>
          <div class="space-y-2 max-h-56 overflow-y-auto pr-1">
            {% for task in tasks %}
            <div class="flex items-center justify-between p-2 bg-gray-800/60 rounded border border-gray-700/60 text-xs">
              <div class="truncate mr-2">
                <p class="{{ 'line-through text-gray-500' if task.is_completed else 'text-gray-200' }} font-medium truncate">{{ task.title }}</p>
                <span class="text-[10px] text-gray-400">{{ task.task_date }}</span>
              </div>
              <div class="flex items-center gap-1.5 shrink-0">
                <a href="/task/toggle/{{ task.id }}" class="px-2 py-0.5 {{ 'bg-emerald-700' if task.is_completed else 'bg-gray-700 hover:bg-cyan-600' }} rounded text-[11px] transition">
                  {{ '✓' if task.is_completed else 'Yap' }}
                </a>
                <a href="/task/delete/{{ task.id }}" onclick="return confirm('Bu görevi silmek istediğine emin misin?');" class="px-2 py-0.5 bg-rose-950/60 hover:bg-rose-600 text-rose-300 hover:text-white rounded border border-rose-900 text-[11px] transition">
                  Sil
                </a>
              </div>
            </div>
            {% endfor %}
            {% if not tasks %}
            <p class="text-xs text-gray-500 text-center py-3">Görev bulunamadı.</p>
            {% endif %}
          </div>
        </div>
      </div>

      <!-- Sağ: Takvim -->
      <div class="lg:col-span-2 bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
        <div id="calendar"></div>
      </div>
    </div>

    <!-- Alt Alan: Not Defteri & Markdown Desteği -->
    <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 border-b border-gray-800 pb-3">
        <div>
          <h2 class="text-lg font-bold text-amber-400">📝 Not Defteri & Dokümantasyon</h2>
          <span class="text-xs text-gray-400">Markdown ve etiketleme destekli</span>
        </div>
        <!-- Filtreleme / Arama -->
        <input type="text" id="noteSearch" onkeyup="filterNotes()" placeholder="Not veya #etiket ara..." class="bg-gray-800 border border-gray-700 text-xs rounded-lg px-3 py-1.5 w-full sm:w-64 focus:outline-none focus:border-amber-400">
      </div>

      <!-- Not Ekleme Formu -->
      <form action="/note/add" method="POST" class="grid grid-cols-1 md:grid-cols-5 gap-3 mb-5 bg-gray-800/30 p-3 rounded-lg border border-gray-800">
        <div class="md:col-span-2">
          <input type="text" name="title" placeholder="Not başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
        </div>
        <div class="md:col-span-1">
          <input type="text" name="category" placeholder="Etiket (örn: #kod, #fikir)" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
        </div>
        <div class="md:col-span-2">
          <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 py-2 rounded font-semibold text-xs transition">Notu Oluştur</button>
        </div>
        <div class="md:col-span-5">
          <textarea name="content" placeholder="Markdown formatında içerik, kod blokları, yapılacaklar..." rows="3" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs font-mono focus:outline-none focus:border-amber-400"></textarea>
        </div>
      </form>

      <!-- Not Kartları Grid -->
      <div id="notesContainer" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        {% for note in notes %}
        <div class="note-card bg-gray-800/40 p-4 rounded-lg border border-gray-700/70 flex flex-col justify-between hover:border-gray-600 transition" data-search="{{ note.title|lower }} {{ note.category|lower }} {{ note.content|lower }}">
          <div>
            <div class="flex justify-between items-start mb-2">
              <h4 class="font-semibold text-amber-300 text-sm truncate mr-2">{{ note.title }}</h4>
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-400 border border-amber-800 shrink-0">{{ note.category }}</span>
            </div>
            <!-- Markdown Render Hedefi -->
            <div class="markdown-body text-xs text-gray-300 leading-relaxed max-h-48 overflow-y-auto pr-1" data-raw="{{ note.content }}"></div>
          </div>
          <div class="mt-3 pt-2 border-t border-gray-700/50 flex justify-between items-center text-[11px] text-gray-500">
            <span>{{ note.created_at }}</span>
            <a href="/note/delete/{{ note.id }}" onclick="return confirm('Bu notu silmek istediğine emin misin?');" class="text-rose-400 hover:text-rose-300">
              Sil 🗑
            </a>
          </div>
        </div>
        {% endfor %}
        {% if not notes %}
        <p class="text-xs text-gray-500 col-span-3 text-center py-4">Henüz kayıtlı bir not yok.</p>
        {% endif %}
      </div>
    </div>

  </div>

  <script>
    // FullCalendar Kurulumu
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

      // Markdown İçeriklerini Render Etme
      document.querySelectorAll('.markdown-body').forEach(function(el) {
        var raw = el.getAttribute('data-raw');
        if(raw) {
          el.innerHTML = marked.parse(raw);
        }
      });
    });

    // Not Arama / Filtreleme
    function filterNotes() {
      var query = document.getElementById('noteSearch').value.toLowerCase();
      var cards = document.querySelectorAll('.note-card');
      cards.forEach(function(card) {
        var text = card.getAttribute('data-search');
        if(text.includes(query)) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    }

    // Pomodoro Mantığı
    let pomoTime = 25 * 60;
    let pomoInterval = null;
    let isBreak = false;

    function updatePomoDisplay() {
      let m = Math.floor(pomoTime / 60);
      let s = pomoTime % 60;
      document.getElementById('pomoTimer').innerText = 
        (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    }

    function startPomodoro() {
      if (pomoInterval) return;
      pomoInterval = setInterval(function() {
        if (pomoTime > 0) {
          pomoTime--;
          updatePomoDisplay();
        } else {
          clearInterval(pomoInterval);
          pomoInterval = null;
          isBreak = !isBreak;
          pomoTime = isBreak ? 5 * 60 : 25 * 60;
          document.getElementById('pomoMode').innerText = isBreak ? 'Mola (5 dk)' : 'Çalışma (25 dk)';
          alert(isBreak ? 'Süre doldu! 5 dakikalık mola zamanı.' : 'Mola bitti! Odaklanma oturumuna dön.');
          updatePomoDisplay();
        }
      }, 1000);
    }

    function pausePomodoro() {
      clearInterval(pomoInterval);
      pomoInterval = null;
    }

    function resetPomodoro() {
      pausePomodoro();
      isBreak = false;
      pomoTime = 25 * 60;
      document.getElementById('pomoMode').innerText = 'Çalışma (25 dk)';
      updatePomoDisplay();
    }
  </script>
</body>
</html>
"""

def calculate_streak_and_heatmap(db):
    today = date.today()
    # Son 30 günlük ısı haritası verisi
    heatmap_days = []
    for i in range(29, -1, -1):
      d = today - timedelta(days=i)
      cnt = db.query(Task).filter(Task.task_date == d, Task.is_completed == True).count()
      heatmap_days.append({"date": d.isoformat(), "count": cnt})

    # Kesintisiz aktif gün sayısı (Streak)
    streak = 0
    check_day = today
    while True:
        cnt = db.query(Task).filter(Task.task_date == check_day, Task.is_completed == True).count()
        if cnt > 0:
            streak += 1
            check_day -= timedelta(days=1)
        else:
            # Bugün henüz bir şey tamamlanmadıysa dünün serisini kontrol et
            if check_day == today:
                check_day -= timedelta(days=1)
                cnt_yesterday = db.query(Task).filter(Task.task_date == check_day, Task.is_completed == True).count()
                if cnt_yesterday > 0:
                    continue
            break

    return streak, heatmap_days

@app.get("/", response_class=HTMLResponse)
def index():
    from jinja2 import Template
    db = SessionLocal()
    tasks = db.query(Task).order_by(Task.task_date.desc()).all()
    notes = db.query(Note).order_by(Note.id.desc()).all()
    streak, heatmap_days = calculate_streak_and_heatmap(db)
    db.close()
    
    t = Template(HTML_TEMPLATE)
    return t.render(
        tasks=tasks, 
        notes=notes, 
        today=date.today().isoformat(),
        streak=streak,
        heatmap_days=heatmap_days
    )

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

@app.post("/note/add")
def add_note(title: str = Form(...), category: str = Form("Genel"), content: str = Form("")):
    tag = category.strip()
    if tag and not tag.startswith("#"):
        tag = f"#{tag}"
    db = SessionLocal()
    new_note = Note(title=title, category=tag if tag else "Genel", content=content, created_at=date.today())
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
