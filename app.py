import os
import traceback
from datetime import date, timedelta
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# --- Veritabanı Yapılandırması ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_tracker.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite için thread kilidini kaldır, Postgres için normal bağlan
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
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

class DailyLog(Base):
    __tablename__ = "daily_logs"
    id = Column(Integer, primary_key=True, index=True)
    log_date = Column(Date, default=date.today, unique=True)
    summary = Column(Text, default="")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")

class ProjectItem(Base):
    __tablename__ = "project_items"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String(200), nullable=False)
    is_done = Column(Boolean, default=False)
    project = relationship("Project", back_populates="items")

Base.metadata.create_all(bind=engine)
app = FastAPI()

# Beklenmedik bir hata olursa siyah ekran yerine hatayı ekrana bas
@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    error_details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(error_details)
    return PlainTextResponse(f"HATA OLUŞTU:\n\n{error_details}", status_code=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kişisel Çalışma & Takip Paneli</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
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

    <!-- Üst Kontrol Barı -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-lg">
      <div class="flex items-center gap-4">
        <div class="bg-emerald-950/80 border border-emerald-600/40 px-4 py-2 rounded-lg">
          <span class="text-[10px] text-emerald-400 block font-semibold uppercase tracking-wider">Aktif Streak</span>
          <span class="text-2xl font-black text-emerald-300">{{ streak }} Gün 🔥</span>
        </div>
        <div>
          <h1 class="text-lg font-bold text-gray-100">Kişisel Dashboard</h1>
          <p class="text-xs text-gray-400">
            Hızlı Menü: <button onclick="toggleCmdPalette()" class="bg-gray-800 px-2 py-0.5 rounded border border-gray-700 text-cyan-400 font-mono text-[11px] hover:border-cyan-500">Ctrl + K</button>
          </p>
        </div>
      </div>

      <!-- Sağ: Isı Haritası -->
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

    <!-- Orta Alan: Sol Paneller & Sağ Takvim -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="space-y-6">
        <!-- Pomodoro -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md text-center">
          <div class="flex justify-between items-center mb-2">
            <h3 class="text-xs font-bold uppercase tracking-wider text-rose-400">🍅 Pomodoro Sayacı</h3>
            <span id="pomoMode" class="text-xs px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800">Çalışma (25 dk)</span>
          </div>
          <div id="pomoTimer" class="text-3xl font-mono font-bold tracking-widest text-gray-100 my-1">25:00</div>
          <div class="flex justify-center gap-2">
            <button onclick="startPomodoro()" class="bg-rose-600 hover:bg-rose-500 text-xs font-semibold px-3 py-1 rounded transition">Başlat</button>
            <button onclick="pausePomodoro()" class="bg-gray-700 hover:bg-gray-600 text-xs font-semibold px-3 py-1 rounded transition">Duraklat</button>
            <button onclick="resetPomodoro()" class="bg-gray-800 hover:bg-gray-700 text-xs font-semibold px-2.5 py-1 rounded text-gray-400 transition">Sıfırla</button>
          </div>
        </div>

        <!-- Görev Ekle -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h2 class="text-sm font-bold mb-3 text-cyan-400">📅 Yeni Takvim Hedefi</h2>
          <form action="/task/add" method="POST" class="space-y-2.5">
            <input type="text" name="title" placeholder="Hedef / Görev" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            <input type="date" name="task_date" value="{{ today }}" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            <textarea name="description" placeholder="Açıklama (opsiyonel)..." rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500"></textarea>
            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-1.5 rounded font-semibold text-xs transition">Takvime Kaydet</button>
          </form>
        </div>

        <!-- Görev Listesi -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h3 class="text-sm font-bold mb-2 text-gray-200">İlerlemeler</h3>
          <div class="space-y-2 max-h-52 overflow-y-auto pr-1">
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
                <a href="/task/delete/{{ task.id }}" onclick="return confirm('Silmek istediğine emin misin?');" class="px-2 py-0.5 bg-rose-950/60 hover:bg-rose-600 text-rose-300 hover:text-white rounded border border-rose-900 text-[11px] transition">
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

      <div class="lg:col-span-2 bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
        <div id="calendar"></div>
      </div>
    </div>

    <!-- Dev Log & Projeler -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-md font-bold text-indigo-400">⚡ Günlük Dev Log</h2>
            <span class="text-xs text-gray-400">{{ today }}</span>
          </div>
          <form action="/daily-log/save" method="POST" class="space-y-3">
            <textarea name="summary" placeholder="Bugün neyi çözdün? Nerede takıldın?" rows="4" class="w-full bg-gray-800 border border-gray-700 rounded p-2.5 text-xs text-gray-200 focus:outline-none focus:border-indigo-500">{{ current_log.summary if current_log else '' }}</textarea>
            <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-xs px-4 py-2 rounded font-semibold transition">Günün Logunu Kaydet</button>
          </form>
        </div>

        <div class="mt-4 pt-3 border-t border-gray-800">
          <span class="text-xs font-semibold text-gray-400 block mb-2">Geçmiş Kayıtlar:</span>
          <div class="space-y-2 max-h-36 overflow-y-auto pr-1">
            {% for log in past_logs %}
            <div class="bg-gray-800/40 p-2 rounded text-xs border border-gray-800">
              <span class="text-indigo-300 font-mono text-[10px] block">{{ log.log_date }}</span>
              <p class="text-gray-300 whitespace-pre-wrap mt-0.5">{{ log.summary }}</p>
            </div>
            {% endfor %}
            {% if not past_logs %}
            <p class="text-[11px] text-gray-500">Henüz geçmiş log bulunmuyor.</p>
            {% endif %}
          </div>
        </div>
      </div>

      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <h2 class="text-md font-bold text-teal-400 mb-3">🎯 Proje Yol Haritaları</h2>
        <form action="/project/add" method="POST" class="flex gap-2 mb-4">
          <input type="text" name="name" placeholder="Yeni Proje Adı..." required class="flex-1 bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-teal-500">
          <button type="submit" class="bg-teal-600 hover:bg-teal-500 text-xs px-3 py-1.5 rounded font-semibold transition">Oluştur</button>
        </form>

        <div class="space-y-4 max-h-80 overflow-y-auto pr-1">
          {% for p in projects %}
          <div class="bg-gray-800/50 p-3 rounded-lg border border-gray-700/70">
            <div class="flex justify-between items-center mb-1.5">
              <span class="font-bold text-xs text-teal-300">{{ p.name }}</span>
              <div class="flex items-center gap-2">
                <span class="text-xs font-mono text-gray-300">%{{ p.progress }}</span>
                <a href="/project/delete/{{ p.id }}" onclick="return confirm('Projeyi silmek istiyor musun?');" class="text-rose-400 hover:text-rose-300 text-[11px]">Sil</a>
              </div>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-1.5 mb-2.5 overflow-hidden">
              <div class="bg-teal-400 h-1.5 rounded-full transition-all duration-500" style="width: {{ p.progress }}%"></div>
            </div>
            <div class="space-y-1 pl-1">
              {% for it in p.items %}
              <div class="flex items-center justify-between text-xs text-gray-300">
                <div class="flex items-center gap-1.5">
                  <a href="/project-item/toggle/{{ it.id }}" class="cursor-pointer {{ 'text-teal-400' if it.is_done else 'text-gray-500' }}">
                    {{ '☑' if it.is_done else '☐' }}
                  </a>
                  <span class="{{ 'line-through text-gray-500' if it.is_done else '' }} text-[11px]">{{ it.title }}</span>
                </div>
                <a href="/project-item/delete/{{ it.id }}" class="text-gray-600 hover:text-rose-400 text-[10px]">✕</a>
              </div>
              {% endfor %}
            </div>
            <form action="/project-item/add" method="POST" class="flex gap-2 mt-2 pt-2 border-t border-gray-700/50">
              <input type="hidden" name="project_id" value="{{ p.id }}">
              <input type="text" name="title" placeholder="Yeni adım ekle..." required class="flex-1 bg-gray-700/60 border border-gray-600 rounded px-2 py-0.5 text-[11px] focus:outline-none">
              <button type="submit" class="bg-gray-700 hover:bg-gray-600 px-2 py-0.5 rounded text-[11px]">+</button>
            </form>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Not Defteri -->
    <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 border-b border-gray-800 pb-3">
        <div>
          <h2 class="text-lg font-bold text-amber-400">📝 Not Defteri</h2>
          <span class="text-xs text-gray-400">Markdown & Etiket Destekli</span>
        </div>
        <input type="text" id="noteSearch" onkeyup="filterNotes()" placeholder="Not veya #etiket ara..." class="bg-gray-800 border border-gray-700 text-xs rounded-lg px-3 py-1.5 w-full sm:w-64 focus:outline-none focus:border-amber-400">
      </div>

      <form action="/note/add" method="POST" class="grid grid-cols-1 md:grid-cols-5 gap-3 mb-5 bg-gray-800/30 p-3 rounded-lg border border-gray-800">
        <div class="md:col-span-2">
          <input type="text" name="title" placeholder="Not başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
        </div>
        <div class="md:col-span-1">
          <input type="text" name="category" placeholder="Etiket (#kod, #fikir)" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
        </div>
        <div class="md:col-span-2">
          <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 py-2 rounded font-semibold text-xs transition">Notu Oluştur</button>
        </div>
        <div class="md:col-span-5">
          <textarea name="content" placeholder="Markdown formatında içerik..." rows="3" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs font-mono focus:outline-none focus:border-amber-400"></textarea>
        </div>
      </form>

      <div id="notesContainer" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        {% for note in notes %}
        <div class="note-card bg-gray-800/40 p-4 rounded-lg border border-gray-700/70 flex flex-col justify-between hover:border-gray-600 transition" data-search="{{ note.title|lower }} {{ note.category|lower }} {{ note.content|lower }}">
          <div>
            <div class="flex justify-between items-start mb-2">
              <h4 class="font-semibold text-amber-300 text-sm truncate mr-2">{{ note.title }}</h4>
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-400 border border-amber-800 shrink-0">{{ note.category }}</span>
            </div>
            <div class="markdown-body text-xs text-gray-300 leading-relaxed max-h-48 overflow-y-auto pr-1" data-raw="{{ note.content }}"></div>
          </div>
          <div class="mt-3 pt-2 border-t border-gray-700/50 flex justify-between items-center text-[11px] text-gray-500">
            <span>{{ note.created_at }}</span>
            <a href="/note/delete/{{ note.id }}" onclick="return confirm('Silmek istediğine emin misin?');" class="text-rose-400 hover:text-rose-300">
              Sil 🗑
            </a>
          </div>
        </div>
        {% endfor %}
      </div>
    </div>

  </div>

  <!-- Command Palette -->
  <div id="cmdPalette" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-start justify-center pt-20 p-4" onclick="if(event.target===this) closeCmdPalette();">
    <div class="bg-gray-900 border border-gray-700 w-full max-w-xl rounded-xl shadow-2xl overflow-hidden">
      <div class="p-3 border-b border-gray-800 flex items-center gap-2">
        <span class="text-cyan-400 font-mono text-sm">⌘</span>
        <input type="text" id="cmdInput" oninput="handleCmdInput()" onkeydown="handleCmdKeyDown(event)" placeholder="Yazmaya başla... (örn: not: Başlık | Detay veya görev: Rapor)" class="w-full bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none">
        <button onclick="closeCmdPalette()" class="text-[10px] bg-gray-800 hover:bg-gray-700 border border-gray-700 px-2 py-1 rounded text-gray-400">ESC</button>
      </div>
      <div id="cmdActionHint" class="p-3 bg-gray-950/80 border-b border-gray-800 text-xs text-gray-400 flex items-center justify-between">
        <span id="cmdStatusText">Komut bekleniyor...</span>
        <span class="text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800 px-2 py-0.5 rounded font-mono">Enter ↵</span>
      </div>
      <div id="cmdResults" class="max-h-60 overflow-y-auto divide-y divide-gray-800/40 p-2 space-y-1"></div>
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

      document.querySelectorAll('.markdown-body').forEach(function(el) {
        var raw = el.getAttribute('data-raw');
        if(raw) el.innerHTML = marked.parse(raw);
      });
    });

    function filterNotes() {
      var query = document.getElementById('noteSearch').value.toLowerCase();
      var cards = document.querySelectorAll('.note-card');
      cards.forEach(function(card) {
        var text = card.getAttribute('data-search');
        card.style.display = text.includes(query) ? 'flex' : 'none';
      });
    }

    // Pomodoro
    let pomoTime = 25 * 60, pomoInterval = null, isBreak = false;
    function updatePomoDisplay() {
      let m = Math.floor(pomoTime / 60), s = pomoTime % 60;
      document.getElementById('pomoTimer').innerText = (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    }
    function startPomodoro() {
      if (pomoInterval) return;
      pomoInterval = setInterval(function() {
        if (pomoTime > 0) { pomoTime--; updatePomoDisplay(); }
        else {
          clearInterval(pomoInterval); pomoInterval = null;
          isBreak = !isBreak; pomoTime = isBreak ? 5 * 60 : 25 * 60;
          document.getElementById('pomoMode').innerText = isBreak ? 'Mola (5 dk)' : 'Çalışma (25 dk)';
          alert(isBreak ? 'Mola zamanı!' : 'Çalışma zamanı!');
          updatePomoDisplay();
        }
      }, 1000);
    }
    function pausePomodoro() { clearInterval(pomoInterval); pomoInterval = null; }
    function resetPomodoro() { pausePomodoro(); isBreak = false; pomoTime = 25 * 60; document.getElementById('pomoMode').innerText = 'Çalışma (25 dk)'; updatePomoDisplay(); }

    // Command Palette
    window.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggleCmdPalette();
      }
      if (e.key === 'Escape') closeCmdPalette();
    });

    function toggleCmdPalette() {
      var modal = document.getElementById('cmdPalette');
      if (modal.classList.contains('hidden')) {
        modal.classList.remove('hidden');
        document.getElementById('cmdInput').focus();
        handleCmdInput();
      } else closeCmdPalette();
    }

    function closeCmdPalette() {
      document.getElementById('cmdPalette').classList.add('hidden');
      document.getElementById('cmdInput').value = '';
    }

    function handleCmdInput() {
      var val = document.getElementById('cmdInput').value.trim();
      var hint = document.getElementById('cmdStatusText');
      var results = document.getElementById('cmdResults');

      if (!val) {
        hint.innerHTML = 'İpucu: <span class="text-amber-300 font-mono">not: Başlık | İçerik</span> veya <span class="text-cyan-300 font-mono">görev: Başlık</span> yazabilirsin.';
        results.innerHTML = '';
        return;
      }

      if (val.toLowerCase().startsWith('not:')) {
        var payload = val.substring(4).split('|');
        hint.innerHTML = '📝 <b class="text-amber-300">Yeni Not:</b> "' + (payload[0].trim() || '...') + '" eklenecek.';
        results.innerHTML = '<div class="p-2 text-xs text-gray-400">Enter tuşuna basarak hemen kaydedebilirsin.</div>';
      } else if (val.toLowerCase().startsWith('görev:') || val.toLowerCase().startsWith('gorev:')) {
        var title = val.substring(val.indexOf(':') + 1).trim();
        hint.innerHTML = '📅 <b class="text-cyan-300">Yeni Görev:</b> "' + (title || '...') + '" bugüne eklenecek.';
        results.innerHTML = '<div class="p-2 text-xs text-gray-400">Enter tuşuna basarak hemen takvime kaydedebilirsin.</div>';
      } else {
        hint.innerHTML = '🔍 Mevcut notlarda aranıyor: "' + val + '"';
        var matches = [];
        document.querySelectorAll('.note-card').forEach(function(card) {
          if (card.getAttribute('data-search').includes(val.toLowerCase())) {
            var title = card.querySelector('h4').innerText;
            matches.push('<div class="p-2 rounded hover:bg-gray-800 text-xs text-amber-200 cursor-pointer" onclick="closeCmdPalette(); document.getElementById(\\'noteSearch\\').value=\\''+title+'\\'; filterNotes();">📝 ' + title + '</div>');
          }
        });
        results.innerHTML = matches.length > 0 ? matches.join('') : '<div class="p-2 text-xs text-gray-500">Eşleşen not bulunamadı.</div>';
      }
    }

    async function handleCmdKeyDown(e) {
      if (e.key === 'Enter') {
        var val = document.getElementById('cmdInput').value.trim();
        if (!val) return;

        if (val.toLowerCase().startsWith('not:')) {
          var payload = val.substring(4).split('|');
          var title = payload[0].trim();
          var content = payload.length > 1 ? payload[1].trim() : '';
          
          let res = await fetch('/api/quick-note-json', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: title, content: content, category: '#quick'})
          });
          if(res.ok) window.location.reload();
        } else if (val.toLowerCase().startsWith('görev:') || val.toLowerCase().startsWith('gorev:')) {
          var title = val.substring(val.indexOf(':') + 1).trim();
          let res = await fetch('/api/quick-task-json', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: title, task_date: '{{ today }}'})
          });
          if(res.ok) window.location.reload();
        } else {
          document.getElementById('noteSearch').value = val;
          filterNotes();
          closeCmdPalette();
        }
      }
    }
  </script>
</body>
</html>
"""

def calculate_streak_and_heatmap(db):
    today = date.today()
    heatmap_days = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        cnt = db.query(Task).filter(Task.task_date == d, Task.is_completed == True).count()
        heatmap_days.append({"date": d.isoformat(), "count": cnt})

    streak = 0
    check_day = today
    while True:
        cnt = db.query(Task).filter(Task.task_date == check_day, Task.is_completed == True).count()
        if cnt > 0:
            streak += 1
            check_day -= timedelta(days=1)
        else:
            if check_day == today:
                check_day -= timedelta(days=1)
                cnt_yesterday = db.query(Task).filter(Task.task_date == check_day, Task.is_completed == True).count()
                if cnt_yesterday > 0:
                    continue
            break

    return streak, heatmap_days

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    from jinja2 import Template
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.task_date.desc()).all()
        notes = db.query(Note).order_by(Note.id.desc()).all()
        
        raw_projects = db.query(Project).all()
        projects = []
        for p in raw_projects:
            total = len(p.items)
            done = sum(1 for it in p.items if it.is_done)
            progress = int((done / total) * 100) if total > 0 else 0
            projects.append({
                "id": p.id,
                "name": p.name,
                "progress": progress,
                "items": p.items
            })

        today_dt = date.today()
        current_log = db.query(DailyLog).filter(DailyLog.log_date == today_dt).first()
        past_logs = db.query(DailyLog).filter(DailyLog.log_date != today_dt).order_by(DailyLog.log_date.desc()).limit(5).all()
        streak, heatmap_days = calculate_streak_and_heatmap(db)
    finally:
        db.close()

    t = Template(HTML_TEMPLATE)
    return t.render(
        tasks=tasks, 
        notes=notes, 
        projects=projects,
        current_log=current_log,
        past_logs=past_logs,
        today=today_dt.isoformat(),
        streak=streak,
        heatmap_days=heatmap_days
    )

# Güvenli Görev Ekleme
@app.post("/task/add")
def add_task(title: str = Form(...), description: str = Form(""), task_date: str = Form(None)):
    try:
        dt = date.fromisoformat(task_date) if task_date else date.today()
    except Exception:
        dt = date.today()

    db = SessionLocal()
    try:
        new_task = Task(title=title, description=description, task_date=dt)
        db.add(new_task)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/task/toggle/{task_id}")
def toggle_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.is_completed = not task.is_completed
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/task/delete/{task_id}")
def delete_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            db.delete(task)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# Güvenli Not Ekleme
@app.post("/note/add")
def add_note(title: str = Form(...), category: str = Form("Genel"), content: str = Form("")):
    tag = category.strip()
    if tag and not tag.startswith("#"):
        tag = f"#{tag}"
    db = SessionLocal()
    try:
        new_note = Note(title=title, category=tag if tag else "Genel", content=content, created_at=date.today())
        db.add(new_note)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/note/delete/{note_id}")
def delete_note(note_id: int):
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            db.delete(note)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# Dev Log
@app.post("/daily-log/save")
def save_daily_log(summary: str = Form("")):
    db = SessionLocal()
    try:
        today_dt = date.today()
        log = db.query(DailyLog).filter(DailyLog.log_date == today_dt).first()
        if log:
            log.summary = summary
        else:
            log = DailyLog(log_date=today_dt, summary=summary)
            db.add(log)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# Proje İşlemleri
@app.post("/project/add")
def add_project(name: str = Form(...)):
    db = SessionLocal()
    try:
        new_proj = Project(name=name)
        db.add(new_proj)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/project/delete/{project_id}")
def delete_project(project_id: int):
    db = SessionLocal()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if p:
            db.delete(p)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/project-item/add")
def add_project_item(project_id: int = Form(...), title: str = Form(...)):
    db = SessionLocal()
    try:
        it = ProjectItem(project_id=project_id, title=title)
        db.add(it)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/project-item/toggle/{item_id}")
def toggle_project_item(item_id: int):
    db = SessionLocal()
    try:
        it = db.query(ProjectItem).filter(ProjectItem.id == item_id).first()
        if it:
            it.is_done = not it.is_done
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/project-item/delete/{item_id}")
def delete_project_item(item_id: int):
    db = SessionLocal()
    try:
        it = db.query(ProjectItem).filter(ProjectItem.id == item_id).first()
        if it:
            db.delete(it)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# Command Palette JSON APIs
@app.post("/api/quick-note-json")
async def quick_note_json(request: Request):
    body = await request.json()
    db = SessionLocal()
    try:
        new_note = Note(
            title=body.get("title", "Hızlı Not"),
            category=body.get("category", "#quick"),
            content=body.get("content", ""),
            created_at=date.today()
        )
        db.add(new_note)
        db.commit()
    finally:
        db.close()
    return JSONResponse({"status": "ok"})

@app.post("/api/quick-task-json")
async def quick_task_json(request: Request):
    body = await request.json()
    db = SessionLocal()
    try:
        dt = date.fromisoformat(body.get("task_date", date.today().isoformat()))
    except Exception:
        dt = date.today()

    try:
        new_task = Task(
            title=body.get("title", "Yeni Görev"),
            task_date=dt,
            description=""
        )
        db.add(new_task)
        db.commit()
    finally:
        db.close()
    return JSONResponse({"status": "ok"})

@app.get("/api/events")
def get_events():
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        res = [
            {
                "id": t.id,
                "title": f"{'✓ ' if t.is_completed else ''}{t.title}",
                "start": t.task_date.isoformat(),
                "color": "#059669" if t.is_completed else "#0284c7"
            }
            for t in tasks
        ]
    finally:
        db.close()
    return res
