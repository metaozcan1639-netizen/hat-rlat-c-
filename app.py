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

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modeller ---
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    task_date = Column(Date, default=date.today)
    start_time = Column(String(10), nullable=True) # Örn: "14:30"
    end_time = Column(String(10), nullable=True)   # Örn: "16:00"
    priority = Column(String(10), default="normal") # "high", "normal", "low"
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

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    last_done_date = Column(Date, nullable=True)

Base.metadata.create_all(bind=engine)
app = FastAPI()

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    error_details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(error_details)
    return PlainTextResponse(f"Sistem Hatası:\n\n{error_details}", status_code=500)

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
  <title>Command Center - Kişisel Panel</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- FullCalendar -->
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
  <!-- Markdown Renderer -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    .markdown-body pre { background-color: #111827; padding: 0.5rem; border-radius: 0.375rem; overflow-x: auto; margin: 0.5rem 0; }
    .markdown-body code { font-family: monospace; color: #38bdf8; font-size: 0.85rem; }
    .markdown-body ul { list-style-type: disc; margin-left: 1.25rem; }
    .markdown-body ol { list-style-type: decimal; margin-left: 1.25rem; }
    .markdown-body h1, .markdown-body h2 { font-weight: bold; color: #fbbf24; margin-top: 0.5rem; }
  </style>
</head>
<body class="bg-gray-950 text-gray-100 p-3 md:p-6 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Üst Kontrol Barı & Hızlı Linkler -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
      <div class="flex items-center gap-4">
        <div class="bg-emerald-950/80 border border-emerald-600/40 px-3.5 py-1.5 rounded-lg text-center">
          <span class="text-[9px] text-emerald-400 block font-semibold uppercase tracking-wider">Aktif Seri</span>
          <span class="text-xl font-black text-emerald-300">{{ streak }} Gün 🔥</span>
        </div>
        <div>
          <h1 class="text-lg font-bold text-gray-100 flex items-center gap-2">
            Kişisel Command Center
            <span class="text-xs font-normal text-gray-500">| {{ today }}</span>
          </h1>
          <!-- Hızlı Başlatıcı (Launchpad) -->
          <div class="flex items-center gap-2 mt-1">
            <a href="https://github.com" target="_blank" class="text-[11px] px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700">GitHub ↗</a>
            <a href="https://chatgpt.com" target="_blank" class="text-[11px] px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700">ChatGPT ↗</a>
            <a href="https://youtube.com" target="_blank" class="text-[11px] px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700">YouTube ↗</a>
            <button onclick="toggleCmdPalette()" class="text-[11px] px-2 py-0.5 rounded bg-cyan-950/70 hover:bg-cyan-900 text-cyan-400 border border-cyan-800 font-mono">Ctrl + K</button>
          </div>
        </div>
      </div>

      <!-- Sağ: 30 Günlük Aktivite Isı Haritası -->
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

    <!-- Orta Ana Panel: Sol Araçlar & Sağ Takvim -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Sol Kolon: Zamanlayıcı, Görev Ekleme, İlerlemeler -->
      <div class="space-y-6">
        
        <!-- Özelleştirilebilir Zamanlayıcı (Pomodoro + Kronometre) -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <div class="flex justify-between items-center mb-2">
            <h3 class="text-xs font-bold uppercase tracking-wider text-rose-400">⏱️ Odaklanma & Sayaç</h3>
            <div class="flex gap-1 text-[11px]">
              <button onclick="setTimerMode('pomodoro')" id="btnPomo" class="px-2 py-0.5 rounded bg-rose-600 text-white font-semibold">Pomodoro</button>
              <button onclick="setTimerMode('stopwatch')" id="btnStop" class="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300">Kronometre</button>
            </div>
          </div>
          
          <div id="timerDisplay" class="text-4xl font-mono font-bold tracking-widest text-center text-gray-100 my-2">25:00</div>
          
          <!-- Manuel Süre Ayar Girişi (Sadece Pomodoro Modunda) -->
          <div id="pomoConfig" class="flex justify-center items-center gap-2 mb-3 text-xs text-gray-400">
            <span>Çalışma:</span>
            <input type="number" id="customWork" value="25" min="1" max="180" class="w-12 bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-center text-gray-100 focus:outline-none">
            <span>dk | Mola:</span>
            <input type="number" id="customBreak" value="5" min="1" max="60" class="w-10 bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-center text-gray-100 focus:outline-none">
            <span>dk</span>
          </div>

          <div class="flex justify-center gap-2">
            <button onclick="startTimer()" id="btnStart" class="bg-rose-600 hover:bg-rose-500 text-xs font-semibold px-4 py-1.5 rounded transition">Başlat</button>
            <button onclick="pauseTimer()" class="bg-gray-700 hover:bg-gray-600 text-xs font-semibold px-3 py-1.5 rounded transition">Duraklat</button>
            <button onclick="resetTimer()" class="bg-gray-800 hover:bg-gray-700 text-xs font-semibold px-3 py-1.5 rounded text-gray-400 transition">Sıfırla</button>
          </div>
        </div>

        <!-- Görev / Takvim Girdisi (Saat & Öncelik Seçimli) -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h2 class="text-sm font-bold mb-3 text-cyan-400">📅 Yeni Takvim Hedefi</h2>
          <form action="/task/add" method="POST" class="space-y-2.5">
            <input type="text" name="title" placeholder="Hedef / Etkinlik başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Tarih</label>
                <input type="date" name="task_date" value="{{ today }}" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-cyan-500">
              </div>
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Öncelik</label>
                <select name="priority" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-cyan-500">
                  <option value="normal">🟡 Normal</option>
                  <option value="high">🔴 Kritik / Yüksek</option>
                  <option value="low">🔵 Düşük</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Başlangıç Saati</label>
                <input type="time" name="start_time" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-cyan-500">
              </div>
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Bitiş Saati (Opsiyonel)</label>
                <input type="time" name="end_time" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-cyan-500">
              </div>
            </div>

            <textarea name="description" placeholder="Açıklama veya kriter..." rows="1" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500"></textarea>
            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-2 rounded font-semibold text-xs transition">Takvime Ekle</button>
          </form>
        </div>

        <!-- Görev Listesi -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
          <h3 class="text-sm font-bold mb-2 text-gray-200">İlerlemeler</h3>
          <div class="space-y-2 max-h-56 overflow-y-auto pr-1">
            {% for task in tasks %}
            <div class="flex items-center justify-between p-2 bg-gray-800/60 rounded border border-gray-700/60 text-xs">
              <div class="truncate mr-2">
                <div class="flex items-center gap-1.5">
                  {% if task.priority == 'high' %}<span class="w-2 h-2 rounded-full bg-rose-500 shrink-0"></span>
                  {% elif task.priority == 'low' %}<span class="w-2 h-2 rounded-full bg-sky-500 shrink-0"></span>
                  {% else %}<span class="w-2 h-2 rounded-full bg-amber-500 shrink-0"></span>{% endif %}
                  <p class="{{ 'line-through text-gray-500' if task.is_completed else 'text-gray-200' }} font-medium truncate">{{ task.title }}</p>
                </div>
                <span class="text-[10px] text-gray-400 pl-3.5">
                  {{ task.task_date }} {% if task.start_time %}• {{ task.start_time }}{% if task.end_time %}-{{ task.end_time }}{% endif %}{% endif %}
                </span>
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

      <!-- Sağ Kolon: Takvim (Aylık & Saat Çizelgeli Haftalık/Günlük Görünüm) -->
      <div class="lg:col-span-2 bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
        <div id="calendar"></div>
      </div>
    </div>

    <!-- 3'lü Fonksiyonel Satır: Rutinler, Anlık Karalama Defteri (Scratchpad), Günlük Log -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      
      <!-- 1. Günlük Rutinler / Alışkanlıklar -->
      <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
        <div>
          <div class="flex justify-between items-center mb-3">
            <h2 class="text-sm font-bold text-violet-400">✨ Günlük Rutinler</h2>
            <span class="text-[11px] text-gray-400">Her gün tekrar edenler</span>
          </div>
          <div class="space-y-2 max-h-48 overflow-y-auto pr-1 mb-3">
            {% for h in habits %}
            <div class="flex items-center justify-between p-2 bg-gray-800/50 rounded text-xs border border-gray-800">
              <span class="{{ 'line-through text-emerald-400' if h.last_done_date == today_date else 'text-gray-200' }}">{{ h.name }}</span>
              <div class="flex items-center gap-2">
                <a href="/habit/toggle/{{ h.id }}" class="px-2 py-0.5 rounded text-[11px] {{ 'bg-emerald-950 text-emerald-300 border border-emerald-700' if h.last_done_date == today_date else 'bg-gray-700 text-gray-300 hover:bg-emerald-700' }}">
                  {{ 'Tamam' if h.last_done_date == today_date else 'Yap' }}
                </a>
                <a href="/habit/delete/{{ h.id }}" class="text-gray-500 hover:text-rose-400 text-[11px]">✕</a>
              </div>
            </div>
            {% endfor %}
            {% if not habits %}
            <p class="text-[11px] text-gray-500 text-center py-2">Rutin eklenmedi.</p>
            {% endif %}
          </div>
        </div>
        <form action="/habit/add" method="POST" class="flex gap-2 pt-2 border-t border-gray-800">
          <input type="text" name="name" placeholder="Örn: 30 dk Okuma, Spor..." required class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-violet-500">
          <button type="submit" class="bg-violet-600 hover:bg-violet-500 px-3 py-1 rounded text-xs font-semibold">+</button>
        </form>
      </div>

      <!-- 2. Uçucu / Anlık Karalama Defteri (Auto-save Scratchpad) -->
      <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
        <div>
          <div class="flex justify-between items-center mb-2">
            <h2 class="text-sm font-bold text-yellow-400">⚡ Hızlı Karalama (Scratchpad)</h2>
            <span class="text-[10px] text-gray-500" id="scratchStatus">Otomatik kaydedildi</span>
          </div>
          <p class="text-[11px] text-gray-400 mb-2">Kaydetmeye basmadan anlık formül, sayı ve geçici not tut.</p>
          <textarea id="scratchpad" rows="6" oninput="saveScratchpad()" placeholder="Aklına geleni buraya bırak, sekme kapansa bile silinmez..." class="w-full bg-gray-800/80 border border-gray-700 rounded p-2.5 text-xs font-mono text-gray-200 focus:outline-none focus:border-yellow-500"></textarea>
        </div>
        <div class="flex justify-end mt-2">
          <button onclick="clearScratchpad()" class="text-[10px] text-rose-400 hover:text-rose-300">Temizle</button>
        </div>
      </div>

      <!-- 3. Günlük Dev Log (Neler Çözüldü?) -->
      <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
        <div>
          <div class="flex justify-between items-center mb-2">
            <h2 class="text-sm font-bold text-indigo-400">📝 Günün Özeti (Dev Log)</h2>
            <span class="text-[11px] text-gray-400">{{ today }}</span>
          </div>
          <form action="/daily-log/save" method="POST" class="space-y-2">
            <textarea name="summary" placeholder="Bugün neyi çözdün? Nerede takıldın?" rows="5" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500">{{ current_log.summary if current_log else '' }}</textarea>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 py-1.5 rounded font-semibold text-xs transition">Günün Logunu Kaydet</button>
          </form>
        </div>
      </div>

    </div>

    <!-- Proje Yol Haritaları & Not Defteri -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Projeler -->
      <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
        <h2 class="text-sm font-bold text-teal-400 mb-3">🎯 Proje Yol Haritaları</h2>
        <form action="/project/add" method="POST" class="flex gap-2 mb-3">
          <input type="text" name="name" placeholder="Yeni Proje Adı..." required class="flex-1 bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-teal-500">
          <button type="submit" class="bg-teal-600 hover:bg-teal-500 text-xs px-3 py-1.5 rounded font-semibold transition">Oluştur</button>
        </form>

        <div class="space-y-3 max-h-72 overflow-y-auto pr-1">
          {% for p in projects %}
          <div class="bg-gray-800/50 p-2.5 rounded-lg border border-gray-700/70">
            <div class="flex justify-between items-center mb-1">
              <span class="font-bold text-xs text-teal-300">{{ p.name }}</span>
              <div class="flex items-center gap-2">
                <span class="text-[11px] font-mono text-gray-300">%{{ p.progress }}</span>
                <a href="/project/delete/{{ p.id }}" onclick="return confirm('Projeyi silmek istiyor musun?');" class="text-rose-400 hover:text-rose-300 text-[11px]">Sil</a>
              </div>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-1.5 mb-2 overflow-hidden">
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

      <!-- Not Defteri (Geniş 2 Kolon) -->
      <div class="lg:col-span-2 bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-3 border-b border-gray-800 pb-2">
          <div>
            <h2 class="text-sm font-bold text-amber-400">📝 Not Defteri</h2>
            <span class="text-[11px] text-gray-400">Markdown & Etiket Destekli</span>
          </div>
          <input type="text" id="noteSearch" onkeyup="filterNotes()" placeholder="Not veya #etiket ara..." class="bg-gray-800 border border-gray-700 text-xs rounded-lg px-2.5 py-1 w-full sm:w-56 focus:outline-none focus:border-amber-400">
        </div>

        <form action="/note/add" method="POST" class="grid grid-cols-1 md:grid-cols-5 gap-2 mb-4 bg-gray-800/30 p-2.5 rounded-lg border border-gray-800">
          <div class="md:col-span-2">
            <input type="text" name="title" placeholder="Not başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-amber-400">
          </div>
          <div class="md:col-span-1">
            <input type="text" name="category" placeholder="Etiket (#kod, #fikir)" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none focus:border-amber-400">
          </div>
          <div class="md:col-span-2">
            <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 py-1.5 rounded font-semibold text-xs transition">Notu Oluştur</button>
          </div>
          <div class="md:col-span-5">
            <textarea name="content" placeholder="Markdown formatında içerik..." rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs font-mono focus:outline-none focus:border-amber-400"></textarea>
          </div>
        </form>

        <div id="notesContainer" class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-72 overflow-y-auto pr-1">
          {% for note in notes %}
          <div class="note-card bg-gray-800/40 p-3 rounded-lg border border-gray-700/70 flex flex-col justify-between hover:border-gray-600 transition" data-search="{{ note.title|lower }} {{ note.category|lower }} {{ note.content|lower }}">
            <div>
              <div class="flex justify-between items-start mb-1.5">
                <h4 class="font-semibold text-amber-300 text-xs truncate mr-2">{{ note.title }}</h4>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-400 border border-amber-800 shrink-0">{{ note.category }}</span>
              </div>
              <div class="markdown-body text-xs text-gray-300 leading-relaxed max-h-36 overflow-y-auto pr-1" data-raw="{{ note.content }}"></div>
            </div>
            <div class="mt-2 pt-1.5 border-t border-gray-700/50 flex justify-between items-center text-[10px] text-gray-500">
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

  </div>

  <!-- Command Palette Modal (Ctrl+K) -->
  <div id="cmdPalette" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-start justify-center pt-20 p-4" onclick="if(event.target===this) closeCmdPalette();">
    <div class="bg-gray-900 border border-gray-700 w-full max-w-xl rounded-xl shadow-2xl overflow-hidden">
      <div class="p-3 border-b border-gray-800 flex items-center gap-2">
        <span class="text-cyan-400 font-mono text-sm">⌘</span>
        <input type="text" id="cmdInput" oninput="handleCmdInput()" onkeydown="handleCmdKeyDown(event)" placeholder="Örn: not: Başlık | Detay  veya  görev: Rapor  (veya aramak için yaz)" class="w-full bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none">
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
    // --- FullCalendar: Aylık, Haftalık Saatli ve Günlük Görünüm ---
    document.addEventListener('DOMContentLoaded', function() {
      var calendarEl = document.getElementById('calendar');
      var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'tr',
        height: 520,
        events: '/api/events',
        slotMinTime: '06:00:00',
        slotMaxTime: '24:00:00',
        allDaySlot: false,
        headerToolbar: {
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek,timeGridDay'
        }
      });
      calendar.render();

      // Markdown Dönüştürme
      document.querySelectorAll('.markdown-body').forEach(function(el) {
        var raw = el.getAttribute('data-raw');
        if(raw) el.innerHTML = marked.parse(raw);
      });

      // Scratchpad Yükleme
      var saved = localStorage.getItem('user_scratchpad');
      if (saved) document.getElementById('scratchpad').value = saved;
    });

    // --- Scratchpad Fonksiyonları ---
    function saveScratchpad() {
      var txt = document.getElementById('scratchpad').value;
      localStorage.setItem('user_scratchpad', txt);
      var st = document.getElementById('scratchStatus');
      st.innerText = 'Kaydediliyor...';
      setTimeout(function(){ st.innerText = 'Otomatik kaydedildi'; }, 500);
    }
    function clearScratchpad() {
      if(confirm('Karalama alanını temizlemek istiyor musun?')) {
        document.getElementById('scratchpad').value = '';
        localStorage.removeItem('user_scratchpad');
      }
    }

    // --- Çok Amaçlı Sayaç (Pomodoro & Kronometre) ---
    let timerMode = 'pomodoro'; // 'pomodoro' veya 'stopwatch'
    let timerInterval = null;
    let timerSeconds = 25 * 60;
    let isBreak = false;

    function setTimerMode(mode) {
      pauseTimer();
      timerMode = mode;
      document.getElementById('btnPomo').className = mode === 'pomodoro' ? 'px-2 py-0.5 rounded bg-rose-600 text-white font-semibold' : 'px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300';
      document.getElementById('btnStop').className = mode === 'stopwatch' ? 'px-2 py-0.5 rounded bg-rose-600 text-white font-semibold' : 'px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300';
      document.getElementById('pomoConfig').style.display = mode === 'pomodoro' ? 'flex' : 'none';
      resetTimer();
    }

    function updateTimerDisplay() {
      let m = Math.floor(timerSeconds / 60);
      let s = timerSeconds % 60;
      document.getElementById('timerDisplay').innerText = (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    }

    function startTimer() {
      if (timerInterval) return;
      timerInterval = setInterval(function() {
        if (timerMode === 'pomodoro') {
          if (timerSeconds > 0) {
            timerSeconds--;
            updateTimerDisplay();
          } else {
            clearInterval(timerInterval);
            timerInterval = null;
            isBreak = !isBreak;
            var w = parseInt(document.getElementById('customWork').value) || 25;
            var b = parseInt(document.getElementById('customBreak').value) || 5;
            timerSeconds = isBreak ? b * 60 : w * 60;
            alert(isBreak ? 'Mola Vakti!' : 'Çalışma Vakti!');
            updateTimerDisplay();
          }
        } else {
          // Kronometre modunda yukarı say
          timerSeconds++;
          updateTimerDisplay();
        }
      }, 1000);
    }

    function pauseTimer() {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    function resetTimer() {
      pauseTimer();
      if (timerMode === 'pomodoro') {
        isBreak = false;
        var w = parseInt(document.getElementById('customWork').value) || 25;
        timerSeconds = w * 60;
      } else {
        timerSeconds = 0;
      }
      updateTimerDisplay();
    }

    // --- Not Arama ---
    function filterNotes() {
      var query = document.getElementById('noteSearch').value.toLowerCase();
      var cards = document.querySelectorAll('.note-card');
      cards.forEach(function(card) {
        var text = card.getAttribute('data-search');
        card.style.display = text.includes(query) ? 'flex' : 'none';
      });
    }

    // --- Command Palette (Ctrl + K) ---
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
        hint.innerHTML = 'İpucu: <span class="text-amber-300 font-mono">not: Başlık | İçerik</span> veya <span class="text-cyan-300 font-mono">görev: Başlık</span>';
        results.innerHTML = '';
        return;
      }

      if (val.toLowerCase().startsWith('not:')) {
        var payload = val.substring(4).split('|');
        hint.innerHTML = '📝 <b class="text-amber-300">Yeni Not:</b> "' + (payload[0].trim() || '...') + '" kaydedilecek.';
        results.innerHTML = '<div class="p-2 text-xs text-gray-400">Enter tuşuna basarak anında kaydet.</div>';
      } else if (val.toLowerCase().startsWith('görev:') || val.toLowerCase().startsWith('gorev:')) {
        var title = val.substring(val.indexOf(':') + 1).trim();
        hint.innerHTML = '📅 <b class="text-cyan-300">Yeni Görev:</b> "' + (title || '...') + '" bugüne eklenecek.';
        results.innerHTML = '<div class="p-2 text-xs text-gray-400">Enter tuşuna basarak anında takvime kaydet.</div>';
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
        tasks = db.query(Task).order_by(Task.task_date.desc(), Task.start_time.asc()).all()
        notes = db.query(Note).order_by(Note.id.desc()).all()
        habits = db.query(Habit).all()
        
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
        streak, heatmap_days = calculate_streak_and_heatmap(db)
    finally:
        db.close()

    t = Template(HTML_TEMPLATE)
    return t.render(
        tasks=tasks, 
        notes=notes, 
        habits=habits,
        projects=projects,
        current_log=current_log,
        today=today_dt.isoformat(),
        today_date=today_dt,
        streak=streak,
        heatmap_days=heatmap_days
    )

# --- Görev İşlemleri ---
@app.post("/task/add")
def add_task(
    title: str = Form(...), 
    description: str = Form(""), 
    task_date: str = Form(None),
    start_time: str = Form(None),
    end_time: str = Form(None),
    priority: str = Form("normal")
):
    try:
        dt = date.fromisoformat(task_date) if task_date else date.today()
    except Exception:
        dt = date.today()

    db = SessionLocal()
    try:
        new_task = Task(
            title=title, 
            description=description, 
            task_date=dt,
            start_time=start_time if start_time else None,
            end_time=end_time if end_time else None,
            priority=priority
        )
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

# --- Rutinler (Habits) ---
@app.post("/habit/add")
def add_habit(name: str = Form(...)):
    db = SessionLocal()
    try:
        h = Habit(name=name)
        db.add(h)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/habit/toggle/{habit_id}")
def toggle_habit(habit_id: int):
    db = SessionLocal()
    try:
        h = db.query(Habit).filter(Habit.id == habit_id).first()
        if h:
            today_dt = date.today()
            h.last_done_date = None if h.last_done_date == today_dt else today_dt
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/habit/delete/{habit_id}")
def delete_habit(habit_id: int):
    db = SessionLocal()
    try:
        h = db.query(Habit).filter(Habit.id == habit_id).first()
        if h:
            db.delete(h)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# --- Not İşlemleri ---
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

# --- Dev Log ---
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

# --- Proje & Alt Adımlar ---
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

# --- Command Palette JSON Uçları ---
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
        new_task = Task(title=body.get("title", "Yeni Görev"), task_date=dt, description="")
        db.add(new_task)
        db.commit()
    finally:
        db.close()
    return JSONResponse({"status": "ok"})

# --- Takvim FullCalendar Etkinlikleri (Saat Entegrasyonlu) ---
@app.get("/api/events")
def get_events():
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        events = []
        for t in tasks:
            color = "#059669" if t.is_completed else ("#e11d48" if t.priority == "high" else ("#0284c7" if t.priority == "normal" else "#64748b"))
            
            # Eğer saat belirtilmişse ISO formatında datetime ver (Böylece haftalık/günlük çizelgede blok olarak görünür)
            if t.start_time:
                start_iso = f"{t.task_date.isoformat()}T{t.start_time}:00"
                end_iso = f"{t.task_date.isoformat()}T{t.end_time}:00" if t.end_time else None
                all_day = False
            else:
                start_iso = t.task_date.isoformat()
                end_iso = None
                all_day = True

            events.append({
                "id": t.id,
                "title": f"{'✓ ' if t.is_completed else ''}{t.title}",
                "start": start_iso,
                "end": end_iso,
                "allDay": all_day,
                "color": color
            })
    finally:
        db.close()
    return events
