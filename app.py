import os
import json
import traceback
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date, ForeignKey, Float
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
    start_time = Column(String(10), nullable=True) # "14:30"
    end_time = Column(String(10), nullable=True)   # "16:00"
    priority = Column(String(10), default="normal") # "high", "normal", "low"
    status = Column(String(20), default="todo")    # "todo", "in_progress", "done"
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
    daily_highlight = Column(String(250), default="")
    highlight_done = Column(Boolean, default=False)

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    last_done_date = Column(Date, nullable=True)

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

class InventoryItem(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(50), default="Genel")
    quantity = Column(Float, default=1.0)
    unit = Column(String(20), default="adet") # "adet", "gram", "metre"
    notes = Column(String(200), default="")

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

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kişisel İşletim Merkezi</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- FullCalendar -->
  <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css' rel='stylesheet' />
  <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js'></script>
  <!-- Markdown & Prism Code Highlighting -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
  <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-bash.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
  <style>
    .markdown-body pre { background-color: #111827; padding: 0.75rem; border-radius: 0.5rem; overflow-x: auto; margin: 0.5rem 0; border: 1px solid #374151; }
    .markdown-body code { font-family: ui-monospace, monospace; color: #38bdf8; font-size: 0.85rem; }
    .markdown-body ul { list-style-type: disc; margin-left: 1.25rem; }
    .markdown-body ol { list-style-type: decimal; margin-left: 1.25rem; }
    .markdown-body h1, .markdown-body h2 { font-weight: bold; color: #fbbf24; margin-top: 0.5rem; }
    .markdown-body img { max-height: 240px; border-radius: 0.375rem; margin: 0.5rem 0; border: 1px solid #4b5563; }
  </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen flex flex-col font-sans">
  
  <!-- Üst Navbar & Sekmeler -->
  <header class="bg-gray-900 border-b border-gray-800 sticky top-0 z-40 px-4 py-2.5 shadow-md">
    <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
      
      <!-- Sol: Başlık & Canlı Durum -->
      <div class="flex items-center gap-3">
        <div class="bg-emerald-950 border border-emerald-600/50 px-2.5 py-1 rounded text-center">
          <span class="text-[9px] text-emerald-400 block font-bold uppercase">Streak</span>
          <span class="text-sm font-black text-emerald-300">{{ streak }} Gün 🔥</span>
        </div>
        <div>
          <a href="/?tab=dashboard" class="font-bold text-sm tracking-wide text-gray-100 flex items-center gap-2 hover:text-cyan-400 transition">
            ⚡ Command Center
          </a>
          <div class="flex items-center gap-2 text-[11px] text-gray-400">
            <span id="liveClock" class="font-mono text-cyan-400 font-semibold">--:--:--</span>
            <span>•</span>
            <span>{{ today }}</span>
            <span>•</span>
            <span class="inline-block w-2 h-2 rounded-full bg-emerald-500" title="Sistem Aktif"></span>
          </div>
        </div>
      </div>

      <!-- Orta: Kategori Sekmeleri -->
      <nav class="flex items-center gap-1 bg-gray-950 p-1 rounded-lg border border-gray-800 text-xs">
        <a href="/?tab=dashboard" class="px-3 py-1.5 rounded-md font-medium transition {{ 'bg-cyan-600 text-white shadow' if current_tab == 'dashboard' else 'text-gray-400 hover:text-gray-200' }}">
          📊 Dashboard
        </a>
        <a href="/?tab=calendar" class="px-3 py-1.5 rounded-md font-medium transition {{ 'bg-cyan-600 text-white shadow' if current_tab == 'calendar' else 'text-gray-400 hover:text-gray-200' }}">
          📅 Takvim & Ajanda
        </a>
        <a href="/?tab=projects" class="px-3 py-1.5 rounded-md font-medium transition {{ 'bg-cyan-600 text-white shadow' if current_tab == 'projects' else 'text-gray-400 hover:text-gray-200' }}">
          🎯 Projeler & Kanban
        </a>
        <a href="/?tab=notes" class="px-3 py-1.5 rounded-md font-medium transition {{ 'bg-cyan-600 text-white shadow' if current_tab == 'notes' else 'text-gray-400 hover:text-gray-200' }}">
          📝 Not Defteri & Kod
        </a>
        <a href="/?tab=tools" class="px-3 py-1.5 rounded-md font-medium transition {{ 'bg-cyan-600 text-white shadow' if current_tab == 'tools' else 'text-gray-400 hover:text-gray-200' }}">
          🧰 Atölye & Araçlar
        </a>
      </nav>

      <!-- Sağ: Hızlı Kısayol Tuşları -->
      <div class="flex items-center gap-2">
        <button onclick="toggleZenMode()" title="Zen Odak Modu (Kısayol: F)" class="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700">
          🧘 Zen (F)
        </button>
        <button onclick="toggleCmdPalette()" class="text-xs px-2.5 py-1 rounded bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 font-mono">
          Ctrl + K
        </button>
      </div>

    </div>
  </header>

  <!-- Ana Sayfa Gövdesi -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6">
    
    <!-- ============================================== -->
    <!-- 1. SEKME: DASHBOARD -->
    <!-- ============================================== -->
    {% if current_tab == 'dashboard' %}
    <div class="space-y-6">
      
      <!-- Günün Odağı (Daily Highlight) Kartı -->
      <div class="bg-gradient-to-r from-amber-950/40 via-gray-900 to-gray-900 border border-amber-600/40 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-lg">
        <div class="flex items-center gap-3 w-full sm:w-auto">
          <span class="text-2xl">🌟</span>
          <div class="flex-1">
            <span class="text-[10px] uppercase tracking-wider font-bold text-amber-400">Günün En Kritik Odağı</span>
            {% if current_log and current_log.daily_highlight %}
              <p class="text-sm font-semibold {{ 'line-through text-gray-500' if current_log.highlight_done else 'text-amber-200' }}">
                {{ current_log.daily_highlight }}
              </p>
            {% else %}
              <p class="text-xs text-gray-400">Günün en önemli tek görevini henüz belirlemedin.</p>
            {% endif %}
          </div>
        </div>
        <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
          {% if current_log and current_log.daily_highlight %}
            <a href="/highlight/toggle" onclick="celebrate()" class="px-3 py-1.5 rounded text-xs font-semibold {{ 'bg-gray-800 text-gray-400' if current_log.highlight_done else 'bg-amber-600 hover:bg-amber-500 text-white' }} transition">
              {{ 'Geri Al' if current_log.highlight_done else 'Tamamladım 🎉' }}
            </a>
          {% endif %}
          <form action="/highlight/set" method="POST" class="flex gap-1.5">
            <input type="text" name="highlight" placeholder="Yeni odak belirle..." required class="bg-gray-800 border border-gray-700 text-xs rounded px-2.5 py-1.5 text-gray-200 focus:outline-none focus:border-amber-400">
            <button type="submit" class="bg-gray-800 hover:bg-gray-700 px-2.5 py-1.5 rounded text-xs border border-gray-700">Ayarla</button>
          </form>
        </div>
      </div>

      <!-- Üst Izgara: Sayaç & Ses, Günlük Rutinler, Isı Haritası -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <!-- Çok Amaçlı Sayaç & Odak Sesleri -->
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
          <div>
            <div class="flex justify-between items-center mb-2">
              <h3 class="text-xs font-bold uppercase tracking-wider text-rose-400">⏱️ Odak Sayacı & Ambiyans</h3>
              <div class="flex gap-1 text-[11px]">
                <button onclick="setTimerMode('pomodoro')" id="btnPomo" class="px-2 py-0.5 rounded bg-rose-600 text-white font-semibold">Pomodoro</button>
                <button onclick="setTimerMode('stopwatch')" id="btnStop" class="px-2 py-0.5 rounded bg-gray-800 text-gray-400">Kronometre</button>
              </div>
            </div>
            
            <div id="timerDisplay" class="text-4xl font-mono font-bold tracking-widest text-center text-gray-100 my-2">25:00</div>
            
            <div id="pomoConfig" class="flex justify-center items-center gap-2 mb-3 text-xs text-gray-400">
              <span>Çalışma:</span>
              <input type="number" id="customWork" value="25" min="1" max="180" class="w-12 bg-gray-800 border border-gray-700 rounded px-1 text-center text-gray-100">
              <span>dk | Mola:</span>
              <input type="number" id="customBreak" value="5" min="1" max="60" class="w-10 bg-gray-800 border border-gray-700 rounded px-1 text-center text-gray-100">
              <span>dk</span>
            </div>

            <div class="flex justify-center gap-2">
              <button onclick="startTimer()" id="btnStart" class="bg-rose-600 hover:bg-rose-500 text-xs font-semibold px-4 py-1.5 rounded transition">Başlat</button>
              <button onclick="pauseTimer()" class="bg-gray-700 hover:bg-gray-600 text-xs font-semibold px-3 py-1.5 rounded transition">Duraklat</button>
              <button onclick="resetTimer()" class="bg-gray-800 hover:bg-gray-700 text-xs font-semibold px-2.5 py-1.5 rounded text-gray-400 transition">Sıfırla</button>
            </div>
          </div>

          <!-- Arka Plan Ses Synth (Doğal Yağmur / Gürültü Sesi - Dosya Gerektirmez) -->
          <div class="mt-4 pt-3 border-t border-gray-800 flex items-center justify-between text-xs">
            <span class="text-gray-400">🌧️ Yağmur Ambiyansı:</span>
            <button onclick="toggleAmbientNoise()" id="btnAmbient" class="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700">
              Sesi Başlat 🔊
            </button>
          </div>
        </div>

        <!-- Günlük Rutinler (Habit Tracker) -->
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
          <div>
            <div class="flex justify-between items-center mb-3">
              <h3 class="text-xs font-bold uppercase tracking-wider text-violet-400">✨ Günlük Rutin Çetelesi</h3>
              <span class="text-[10px] text-gray-500">Her gün yenilenir</span>
            </div>
            <div class="space-y-2 max-h-48 overflow-y-auto pr-1">
              {% for h in habits %}
              <div class="flex items-center justify-between p-2 bg-gray-800/40 rounded text-xs border border-gray-800">
                <span class="{{ 'line-through text-emerald-400' if h.last_done_date == today_date else 'text-gray-200' }}">{{ h.name }}</span>
                <div class="flex items-center gap-2">
                  <a href="/habit/toggle/{{ h.id }}?tab=dashboard" class="px-2 py-0.5 rounded text-[11px] {{ 'bg-emerald-950 text-emerald-300 border border-emerald-700' if h.last_done_date == today_date else 'bg-gray-700 text-gray-300 hover:bg-emerald-700' }}">
                    {{ 'Tamam' if h.last_done_date == today_date else 'Yap' }}
                  </a>
                  <a href="/habit/delete/{{ h.id }}?tab=dashboard" class="text-gray-500 hover:text-rose-400 text-[11px]">✕</a>
                </div>
              </div>
              {% endfor %}
              {% if not habits %}
              <p class="text-xs text-gray-500 text-center py-4">Kayıtlı rutin yok.</p>
              {% endif %}
            </div>
          </div>
          <form action="/habit/add" method="POST" class="flex gap-2 pt-3 border-t border-gray-800">
            <input type="hidden" name="tab" value="dashboard">
            <input type="text" name="name" placeholder="Örn: 30 dk Okuma, Spor..." required class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-violet-500">
            <button type="submit" class="bg-violet-600 hover:bg-violet-500 px-3 py-1 rounded text-xs font-semibold">+</button>
          </form>
        </div>

        <!-- Günlük Dev Log & Isı Haritası -->
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
          <div>
            <div class="flex justify-between items-center mb-2">
              <h3 class="text-xs font-bold uppercase tracking-wider text-indigo-400">⚡ Günlük Dev Log</h3>
              <span class="text-[10px] text-gray-500">{{ today }}</span>
            </div>
            <form action="/daily-log/save" method="POST" class="space-y-2 mb-3">
              <textarea name="summary" placeholder="Bugün ne çözüldü? Hangi adım atıldı?" rows="3" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500">{{ current_log.summary if current_log else '' }}</textarea>
              <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 py-1 rounded font-semibold text-xs transition">Günün Logunu Kaydet</button>
            </form>
          </div>

          <!-- Mini Heatmap -->
          <div class="pt-3 border-t border-gray-800">
            <span class="text-[10px] text-gray-400 block mb-1.5">Son 30 Günlük Aktivite:</span>
            <div class="flex items-center gap-1 overflow-x-auto py-1">
              {% for day in heatmap_days %}
                <div title="{{ day.date }}: {{ day.count }} tamamlanan" 
                     class="w-3 h-3 rounded-sm
                     {% if day.count == 0 %}bg-gray-800 border border-gray-700/50
                     {% elif day.count == 1 %}bg-emerald-900 border border-emerald-700
                     {% elif day.count == 2 %}bg-emerald-600
                     {% else %}bg-emerald-400{% endif %}">
                </div>
              {% endfor %}
            </div>
          </div>
        </div>

      </div>

      <!-- Günün Yaklaşan Görevleri -->
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-sm font-bold text-cyan-400">📋 Bugünkü Planlar & Saatli Etkinlikler</h3>
          <a href="/?tab=calendar" class="text-xs text-cyan-400 hover:underline">Tüm Takvimi Aç ➔</a>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {% for t in today_tasks %}
          <div class="p-3 bg-gray-800/50 rounded-lg border border-gray-700/60 flex items-center justify-between text-xs">
            <div>
              <div class="flex items-center gap-1.5">
                {% if t.priority == 'high' %}<span class="w-2 h-2 rounded-full bg-rose-500"></span>
                {% elif t.priority == 'low' %}<span class="w-2 h-2 rounded-full bg-sky-500"></span>
                {% else %}<span class="w-2 h-2 rounded-full bg-amber-500"></span>{% endif %}
                <span class="{{ 'line-through text-gray-500' if t.is_completed else 'text-gray-100' }} font-medium">{{ t.title }}</span>
              </div>
              <span class="text-[10px] text-gray-400 pl-3.5">
                {% if t.start_time %}{{ t.start_time }}{% if t.end_time %}-{{ t.end_time }}{% endif %}{% else %}Tüm Gün{% endif %}
              </span>
            </div>
            <a href="/task/toggle/{{ t.id }}?tab=dashboard" class="px-2 py-1 {{ 'bg-emerald-700' if t.is_completed else 'bg-gray-700 hover:bg-cyan-600' }} rounded text-[10px]">
              {{ '✓' if t.is_completed else 'Yap' }}
            </a>
          </div>
          {% endfor %}
          {% if not today_tasks %}
          <p class="text-xs text-gray-500 col-span-3 text-center py-4">Bugün için planlanmış görev yok.</p>
          {% endif %}
        </div>
      </div>

    </div>
    {% endif %}

    <!-- ============================================== -->
    <!-- 2. SEKME: TAKVİM & AJANDA -->
    <!-- ============================================== -->
    {% if current_tab == 'calendar' %}
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Sol: Saatli Görev Ekleme Formu & Dış Takvim Linki -->
      <div class="space-y-6">
        <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
          <h2 class="text-sm font-bold mb-3 text-cyan-400">📅 Yeni Saatli Etkinlik / Hedef</h2>
          <form action="/task/add" method="POST" class="space-y-3">
            <input type="hidden" name="tab" value="calendar">
            <input type="text" name="title" placeholder="Etkinlik / Görev Başlığı" required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-cyan-500">
            
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Tarih</label>
                <input type="date" name="task_date" value="{{ today }}" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none">
              </div>
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Öncelik</label>
                <select name="priority" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none">
                  <option value="normal">🟡 Normal</option>
                  <option value="high">🔴 Kritik</option>
                  <option value="low">🔵 Düşük</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Başlangıç Saati</label>
                <input type="time" name="start_time" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none">
              </div>
              <div>
                <label class="text-[10px] text-gray-400 block mb-0.5">Bitiş Saati</label>
                <input type="time" name="end_time" class="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-xs focus:outline-none">
              </div>
            </div>

            <textarea name="description" placeholder="Açıklama veya kriter..." rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none"></textarea>
            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 py-2 rounded font-semibold text-xs transition">Takvime Kaydet</button>
          </form>
        </div>

        <!-- Google Takvim Senkronizasyon Kartı -->
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 text-xs space-y-2">
          <span class="font-bold text-gray-200 block">📱 Dış Takvim Senkronizasyonu</span>
          <p class="text-[11px] text-gray-400 leading-relaxed">
            Buradaki saatli etkinlikleri Google Takvim veya Apple Calendar'a abone etmek için aşağıdaki iCal URL'sini takvimine "URL ile Ekle" olarak yapıştırabilirsin:
          </p>
          <div class="p-2 bg-gray-950 rounded border border-gray-800 font-mono text-[10px] text-cyan-300 break-all select-all">
            {{ app_url }}/api/calendar.ics
          </div>
        </div>
      </div>

      <!-- Sağ: FullCalendar Saat Çizelgeli Takvim -->
      <div class="lg:col-span-2 bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <div id="calendar"></div>
      </div>

    </div>
    {% endif %}

    <!-- ============================================== -->
    <!-- 3. SEKME: PROJELER & KANBAN -->
    <!-- ============================================== -->
    {% if current_tab == 'projects' %}
    <div class="space-y-6">
      
      <!-- Proje Ekleme & Şablon Yükleme Barı -->
      <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 flex flex-wrap items-center justify-between gap-3 shadow-md">
        <form action="/project/add" method="POST" class="flex gap-2 flex-1 max-w-md">
          <input type="text" name="name" placeholder="Yeni Proje Başlığı..." required class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs focus:outline-none focus:border-teal-500">
          <button type="submit" class="bg-teal-600 hover:bg-teal-500 text-xs px-4 py-1.5 rounded font-semibold transition">Proje Oluştur</button>
        </form>

        <!-- Hazır Şablon Butonları -->
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400">Şablon Yükle:</span>
          <a href="/project/template/tech" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-teal-300 border border-gray-700">⚙️ Yazılım / Bot</a>
          <a href="/project/template/3dprint" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-amber-300 border border-gray-700">🖨️ 3D Baskı</a>
        </div>
      </div>

      <!-- Proje İlerleme Kartları Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {% for p in projects %}
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between">
          <div>
            <div class="flex justify-between items-center mb-2">
              <h4 class="font-bold text-sm text-teal-300 truncate">{{ p.name }}</h4>
              <div class="flex items-center gap-2">
                <span class="text-xs font-mono font-bold text-gray-200">%{{ p.progress }}</span>
                <a href="/project/delete/{{ p.id }}" onclick="return confirm('Projeyi silmek istiyor musun?');" class="text-rose-400 text-xs">Sil</a>
              </div>
            </div>
            <!-- İlerleme Çubuğu -->
            <div class="w-full bg-gray-800 rounded-full h-2 mb-3 overflow-hidden">
              <div class="bg-teal-400 h-2 rounded-full transition-all duration-500" style="width: {{ p.progress }}%"></div>
            </div>
            <!-- Alt Adımlar -->
            <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {% for it in p.items %}
              <div class="flex items-center justify-between text-xs p-1.5 rounded bg-gray-800/40">
                <div class="flex items-center gap-2">
                  <a href="/project-item/toggle/{{ it.id }}" class="{{ 'text-teal-400' if it.is_done else 'text-gray-500' }}">
                    {{ '☑' if it.is_done else '☐' }}
                  </a>
                  <span class="{{ 'line-through text-gray-500' if it.is_done else 'text-gray-200' }}">{{ it.title }}</span>
                </div>
                <a href="/project-item/delete/{{ it.id }}" class="text-gray-600 hover:text-rose-400 text-xs">✕</a>
              </div>
              {% endfor %}
            </div>
          </div>
          <form action="/project-item/add" method="POST" class="flex gap-2 mt-3 pt-3 border-t border-gray-800">
            <input type="hidden" name="project_id" value="{{ p.id }}">
            <input type="text" name="title" placeholder="Yeni adım ekle..." required class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none">
            <button type="submit" class="bg-gray-800 hover:bg-gray-700 px-2.5 py-1 rounded text-xs">+</button>
          </form>
        </div>
        {% endfor %}
      </div>

      <!-- 3 Sütunlu İnteraktif Kanban Tahtası -->
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <h3 class="text-sm font-bold text-gray-200 mb-3">📌 Görev Kanban Panosu</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          <!-- Sütun 1: Yapılacaklar -->
          <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
            <div class="flex justify-between items-center mb-2 pb-1 border-b border-gray-800">
              <span class="text-xs font-bold text-amber-400">Yapılacaklar</span>
              <span class="text-[10px] text-gray-500">{{ kanban_todo|length }}</span>
            </div>
            <div class="space-y-2 min-h-[120px]">
              {% for t in kanban_todo %}
              <div class="p-2.5 bg-gray-800/80 rounded border border-gray-700 text-xs flex justify-between items-start">
                <div>
                  <p class="font-medium text-gray-200">{{ t.title }}</p>
                  <span class="text-[10px] text-gray-400">{{ t.task_date }}</span>
                </div>
                <a href="/task/status/{{ t.id }}/in_progress" class="text-[10px] bg-gray-700 px-1.5 py-0.5 rounded text-cyan-300">Başla ➔</a>
              </div>
              {% endfor %}
            </div>
          </div>

          <!-- Sütun 2: Sürüyor (In Progress) -->
          <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
            <div class="flex justify-between items-center mb-2 pb-1 border-b border-gray-800">
              <span class="text-xs font-bold text-cyan-400">Sürüyor / Aktif</span>
              <span class="text-[10px] text-gray-500">{{ kanban_in_progress|length }}</span>
            </div>
            <div class="space-y-2 min-h-[120px]">
              {% for t in kanban_in_progress %}
              <div class="p-2.5 bg-cyan-950/30 rounded border border-cyan-800/60 text-xs flex justify-between items-start">
                <div>
                  <p class="font-medium text-cyan-200">{{ t.title }}</p>
                  <span class="text-[10px] text-gray-400">{{ t.task_date }}</span>
                </div>
                <a href="/task/status/{{ t.id }}/done" class="text-[10px] bg-emerald-800 px-1.5 py-0.5 rounded text-white">Bitti ✓</a>
              </div>
              {% endfor %}
            </div>
          </div>

          <!-- Sütun 3: Tamamlandı -->
          <div class="bg-gray-950 p-3 rounded-lg border border-gray-800">
            <div class="flex justify-between items-center mb-2 pb-1 border-b border-gray-800">
              <span class="text-xs font-bold text-emerald-400">Tamamlandı</span>
              <span class="text-[10px] text-gray-500">{{ kanban_done|length }}</span>
            </div>
            <div class="space-y-2 min-h-[120px]">
              {% for t in kanban_done %}
              <div class="p-2.5 bg-gray-800/40 rounded border border-gray-800 text-xs flex justify-between items-center">
                <span class="line-through text-gray-400">{{ t.title }}</span>
                <a href="/task/status/{{ t.id }}/todo" class="text-[10px] text-gray-500 hover:text-gray-300">Geri Al</a>
              </div>
              {% endfor %}
            </div>
          </div>

        </div>
      </div>

    </div>
    {% endif %}

    <!-- ============================================== -->
    <!-- 4. SEKME: NOT DEFTERİ & KOD -->
    <!-- ============================================== -->
    {% if current_tab == 'notes' %}
    <div class="space-y-6">
      
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Sol: Yeni Not Ekleme & Uçucu Scratchpad -->
        <div class="space-y-6">
          
          <!-- Not Ekle Formu (Panodan Görsel Yapıştırma Desteği) -->
          <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
            <h3 class="text-sm font-bold text-amber-400 mb-3">📝 Yeni Markdown Not</h3>
            <form action="/note/add" method="POST" class="space-y-3">
              <input type="text" name="title" placeholder="Not başlığı..." required class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
              <input type="text" name="category" placeholder="Etiket (#kod, #tasarim, #fikir)" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs focus:outline-none focus:border-amber-400">
              <p class="text-[10px] text-gray-400">İpucu: Metin alanına `Ctrl+V` ile ekran alıntısı yapıştırabilirsin.</p>
              <textarea id="noteContentInput" name="content" placeholder="Markdown içerik, ```python kod blokları```..." rows="6" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs font-mono focus:outline-none focus:border-amber-400"></textarea>
              <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 py-2 rounded font-semibold text-xs transition">Notu Kaydet</button>
            </form>
          </div>

          <!-- Uçucu Scratchpad (Auto-save) -->
          <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
            <div class="flex justify-between items-center mb-1.5">
              <h3 class="text-xs font-bold uppercase tracking-wider text-yellow-400">⚡ Hızlı Karalama (Scratchpad)</h3>
              <span class="text-[9px] text-gray-500" id="scratchStatus">Kaydedildi</span>
            </div>
            <textarea id="scratchpad" rows="4" oninput="saveScratchpad()" placeholder="Geçici sayı, link, formül..." class="w-full bg-gray-800/70 border border-gray-700 rounded p-2 text-xs font-mono text-gray-200 focus:outline-none"></textarea>
          </div>

        </div>

        <!-- Sağ: Not Kartları & Filtreleme -->
        <div class="lg:col-span-2 space-y-4">
          <div class="flex items-center justify-between gap-3 bg-gray-900 p-3 rounded-xl border border-gray-800">
            <input type="text" id="noteSearch" onkeyup="filterNotes()" placeholder="Notlarda veya #etiketlerde canlı ara..." class="bg-gray-800 border border-gray-700 text-xs rounded-lg px-3 py-1.5 w-full focus:outline-none focus:border-amber-400">
            <span class="text-xs text-gray-400 whitespace-nowrap">{{ notes|length }} Not</span>
          </div>

          <div id="notesContainer" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            {% for n in notes %}
            <div class="note-card bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-md flex flex-col justify-between hover:border-gray-700 transition" data-search="{{ n.title|lower }} {{ n.category|lower }} {{ n.content|lower }}">
              <div>
                <div class="flex justify-between items-start mb-2">
                  <h4 class="font-bold text-amber-300 text-sm truncate mr-2">{{ n.title }}</h4>
                  <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 shrink-0">{{ n.category }}</span>
                </div>
                <div class="markdown-body text-xs text-gray-300 leading-relaxed max-h-56 overflow-y-auto pr-1" data-raw="{{ n.content }}"></div>
              </div>
              <div class="mt-3 pt-2 border-t border-gray-800 flex justify-between items-center text-[10px] text-gray-500">
                <span>{{ n.created_at }}</span>
                <a href="/note/delete/{{ n.id }}?tab=notes" onclick="return confirm('Notu silmek istiyor musun?');" class="text-rose-400 hover:text-rose-300">Sil 🗑</a>
              </div>
            </div>
            {% endfor %}
          </div>
        </div>

      </div>

    </div>
    {% endif %}

    <!-- ============================================== -->
    <!-- 5. SEKME: ATÖLYE & ARAÇLAR -->
    <!-- ============================================== -->
    {% if current_tab == 'tools' %}
    <div class="space-y-6">
      
      <!-- Mühendislik Birim Dönüştürücü & Mini Hesaplama -->
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <h3 class="text-sm font-bold text-cyan-400 mb-3">📐 Hızlı Birim Dönüştürücü</h3>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          
          <!-- Tork Dönüştürücü -->
          <div class="p-3 bg-gray-950 rounded-lg border border-gray-800 space-y-2">
            <span class="font-bold text-gray-200 block">Tork ($Nm \leftrightarrow lb\cdot ft$)</span>
            <input type="number" id="valNm" oninput="convertTorque('nm')" placeholder="Nm gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
            <input type="number" id="valLbft" oninput="convertTorque('lbft')" placeholder="lb-ft gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
          </div>

          <!-- Basınç Dönüştürücü -->
          <div class="p-3 bg-gray-950 rounded-lg border border-gray-800 space-y-2">
            <span class="font-bold text-gray-200 block">Basınç ($bar \leftrightarrow psi$)</span>
            <input type="number" id="valBar" oninput="convertPressure('bar')" placeholder="Bar gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
            <input type="number" id="valPsi" oninput="convertPressure('psi')" placeholder="psi gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
          </div>

          <!-- Sıcaklık Dönüştürücü -->
          <div class="p-3 bg-gray-950 rounded-lg border border-gray-800 space-y-2">
            <span class="font-bold text-gray-200 block">Sıcaklık ($^\circ C \leftrightarrow ^\circ F$)</span>
            <input type="number" id="valC" oninput="convertTemp('c')" placeholder="°C gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
            <input type="number" id="valF" oninput="convertTemp('f')" placeholder="°F gir..." class="w-full bg-gray-800 border border-gray-700 rounded p-1.5">
          </div>

        </div>
      </div>

      <!-- Atölye / Malzeme Envanter Takipçisi -->
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-sm font-bold text-emerald-400">📦 Atölye & Malzeme Envanteri (Filament, Parça vb.)</h3>
        </div>

        <form action="/inventory/add" method="POST" class="grid grid-cols-1 sm:grid-cols-5 gap-2 mb-4 bg-gray-950 p-3 rounded-lg border border-gray-800">
          <input type="text" name="name" placeholder="Malzeme Adı (örn: PLA Siyah Filament)" required class="sm:col-span-2 bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs focus:outline-none">
          <input type="text" name="category" placeholder="Kategori (#filament, #vida)" class="bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs focus:outline-none">
          <div class="flex gap-1">
            <input type="number" step="0.1" name="quantity" placeholder="Miktar" required class="w-20 bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs focus:outline-none">
            <input type="text" name="unit" placeholder="Birim (gr/adet)" value="adet" class="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs focus:outline-none">
          </div>
          <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 rounded text-xs font-semibold py-1.5 transition">Stoğa Ekle</button>
        </form>

        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {% for item in inventory %}
          <div class="p-3 bg-gray-950 rounded-lg border border-gray-800 flex justify-between items-center text-xs">
            <div>
              <p class="font-bold text-gray-200">{{ item.name }}</p>
              <span class="text-[10px] text-gray-400">{{ item.category }} • <b class="text-emerald-400">{{ item.quantity }} {{ item.unit }}</b></span>
            </div>
            <a href="/inventory/delete/{{ item.id }}" class="text-gray-500 hover:text-rose-400 text-xs">Sil ✕</a>
          </div>
          {% endfor %}
        </div>
      </div>

      <!-- Sistem Yedekleme (Backup / JSON Export) -->
      <div class="bg-gray-900 p-5 rounded-xl border border-gray-800 shadow-md flex justify-between items-center">
        <div>
          <h4 class="text-sm font-bold text-gray-200">💾 Tam Veritabanı Yedeği</h4>
          <p class="text-xs text-gray-400">Tüm görevlerini, notlarını, projelerini ve envanterini tek tıkla JSON olarak kaydet.</p>
        </div>
        <a href="/api/backup" download class="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-4 py-2 rounded text-xs font-semibold text-cyan-300">
          JSON Yedeği İndir 📥
        </a>
      </div>

    </div>
    {% endif %}

  </main>

  <!-- ============================================== -->
  <!-- MODALLAR & ARKA PLAN BİLEŞENLERİ -->
  <!-- ============================================== -->

  <!-- 1. Command Palette (Ctrl + K) -->
  <div id="cmdPalette" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-start justify-center pt-20 p-4" onclick="if(event.target===this) closeCmdPalette();">
    <div class="bg-gray-900 border border-gray-700 w-full max-w-xl rounded-xl shadow-2xl overflow-hidden">
      <div class="p-3 border-b border-gray-800 flex items-center gap-2">
        <span class="text-cyan-400 font-mono text-sm">⌘</span>
        <input type="text" id="cmdInput" oninput="handleCmdInput()" onkeydown="handleCmdKeyDown(event)" placeholder="Örn: görev: yarın 15:30 rapor teslimi !kritik  veya  not: Başlık | Detay" class="w-full bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none">
        <button onclick="closeCmdPalette()" class="text-[10px] bg-gray-800 border border-gray-700 px-2 py-1 rounded text-gray-400">ESC</button>
      </div>
      <div class="p-2.5 bg-gray-950 border-b border-gray-800 text-xs text-gray-400 flex items-center justify-between">
        <span id="cmdStatusText">Doğal dil komutu veya arama bekleniyor...</span>
        <span class="text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800 px-2 py-0.5 rounded font-mono">Enter ↵</span>
      </div>
      <div id="cmdResults" class="max-h-60 overflow-y-auto p-2 space-y-1 text-xs"></div>
    </div>
  </div>

  <!-- 2. Zen / Odak Modu Tam Ekran Katmanı (F Tuşu) -->
  <div id="zenOverlay" class="fixed inset-0 bg-gray-950 z-50 hidden flex flex-col items-center justify-center p-6 text-center">
    <button onclick="toggleZenMode()" class="absolute top-6 right-6 text-gray-500 hover:text-gray-300 text-xs border border-gray-800 px-3 py-1.5 rounded">Zen'den Çık (ESC / F)</button>
    <div class="max-w-md w-full space-y-6">
      <span class="text-xs uppercase tracking-widest text-rose-400 font-bold">Zen Odak Oturumu</span>
      <div id="zenTimerDisplay" class="text-7xl font-mono font-bold tracking-widest text-gray-100">25:00</div>
      {% if current_log and current_log.daily_highlight %}
      <div class="p-3 bg-gray-900 border border-amber-600/30 rounded-lg">
        <span class="text-[10px] text-amber-400 font-bold uppercase block">Şu Anki Tek Görevin:</span>
        <p class="text-sm font-semibold text-amber-200 mt-1">{{ current_log.daily_highlight }}</p>
      </div>
      {% endif %}
      <div class="flex justify-center gap-3">
        <button onclick="startTimer()" class="bg-rose-600 px-6 py-2 rounded text-sm font-semibold">Başlat</button>
        <button onclick="pauseTimer()" class="bg-gray-800 px-6 py-2 rounded text-sm font-semibold">Duraklat</button>
      </div>
    </div>
  </div>

  <!-- JAVASCRIPT MOTORU -->
  <script>
    // Canlı Saat
    setInterval(function() {
      var d = new Date();
      document.getElementById('liveClock').innerText = d.toLocaleTimeString('tr-TR');
    }, 1000);

    // FullCalendar Kurulumu (Sadece takvim sekmesindeyse)
    document.addEventListener('DOMContentLoaded', function() {
      var calendarEl = document.getElementById('calendar');
      if (calendarEl) {
        var calendar = new FullCalendar.Calendar(calendarEl, {
          initialView: 'dayGridMonth',
          locale: 'tr',
          height: 540,
          events: '/api/events',
          slotMinTime: '06:00:00',
          slotMaxTime: '24:00:00',
          headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
          }
        });
        calendar.render();
      }

      // Markdown Render
      document.querySelectorAll('.markdown-body').forEach(function(el) {
        var raw = el.getAttribute('data-raw');
        if(raw) el.innerHTML = marked.parse(raw);
      });

      // Scratchpad Yükle
      var saved = localStorage.getItem('user_scratchpad');
      var sp = document.getElementById('scratchpad');
      if (sp && saved) sp.value = saved;

      // Tarayıcı Bildirim İzni İste
      if ("Notification" in window && Notification.permission !== "granted") {
        Notification.requestPermission();
      }

      // Panodan Görsel Yapıştırma Desteği
      var noteArea = document.getElementById('noteContentInput');
      if (noteArea) {
        noteArea.addEventListener('paste', function(e) {
          var items = (e.clipboardData || e.originalEvent.clipboardData).items;
          for (var index in items) {
            var item = items[index];
            if (item.kind === 'file' && item.type.includes('image')) {
              var blob = item.getAsFile();
              var reader = new FileReader();
              reader.onload = function(event) {
                noteArea.value += "\\n![Eklenen Görsel](" + event.target.result + ")\\n";
              };
              reader.readAsDataURL(blob);
            }
          }
        });
      }
    });

    // Scratchpad Kayıt
    function saveScratchpad() {
      var sp = document.getElementById('scratchpad');
      if (!sp) return;
      localStorage.setItem('user_scratchpad', sp.value);
      var st = document.getElementById('scratchStatus');
      if(st) {
        st.innerText = 'Kaydediliyor...';
        setTimeout(function(){ st.innerText = 'Kaydedildi'; }, 500);
      }
    }

    // Sayaç & Pomodoro
    let timerMode = 'pomodoro', timerInterval = null, timerSeconds = 25 * 60, isBreak = false;
    function setTimerMode(mode) {
      pauseTimer();
      timerMode = mode;
      var pBtn = document.getElementById('btnPomo'), sBtn = document.getElementById('btnStop'), cfg = document.getElementById('pomoConfig');
      if (pBtn && sBtn) {
        pBtn.className = mode === 'pomodoro' ? 'px-2 py-0.5 rounded bg-rose-600 text-white font-semibold' : 'px-2 py-0.5 rounded bg-gray-800 text-gray-400';
        sBtn.className = mode === 'stopwatch' ? 'px-2 py-0.5 rounded bg-rose-600 text-white font-semibold' : 'px-2 py-0.5 rounded bg-gray-800 text-gray-400';
      }
      if(cfg) cfg.style.display = mode === 'pomodoro' ? 'flex' : 'none';
      resetTimer();
    }
    function updateTimerDisplay() {
      let m = Math.floor(timerSeconds / 60), s = timerSeconds % 60;
      let str = (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
      var td = document.getElementById('timerDisplay');
      var zd = document.getElementById('zenTimerDisplay');
      if(td) td.innerText = str;
      if(zd) zd.innerText = str;
    }
    function startTimer() {
      if (timerInterval) return;
      timerInterval = setInterval(function() {
        if (timerMode === 'pomodoro') {
          if (timerSeconds > 0) { timerSeconds--; updateTimerDisplay(); }
          else {
            clearInterval(timerInterval); timerInterval = null;
            isBreak = !isBreak;
            var w = parseInt(document.getElementById('customWork').value) || 25;
            var b = parseInt(document.getElementById('customBreak').value) || 5;
            timerSeconds = isBreak ? b * 60 : w * 60;
            if (Notification.permission === "granted") {
              new Notification(isBreak ? "Mola Vakti! ☕" : "Odaklanma Vakti! 🎯");
            }
            updateTimerDisplay();
          }
        } else { timerSeconds++; updateTimerDisplay(); }
      }, 1000);
    }
    function pauseTimer() { clearInterval(timerInterval); timerInterval = null; }
    function resetTimer() {
      pauseTimer();
      if (timerMode === 'pomodoro') {
        isBreak = false;
        var cw = document.getElementById('customWork');
        var w = cw ? (parseInt(cw.value) || 25) : 25;
        timerSeconds = w * 60;
      } else timerSeconds = 0;
      updateTimerDisplay();
    }

    // Web Audio API Yağmur Sesi Synth (Ek dosya indirmez, sıfır gecikme)
    let audioCtx = null, noiseNode = null;
    function toggleAmbientNoise() {
      var btn = document.getElementById('btnAmbient');
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let bufferSize = audioCtx.sampleRate * 2;
        let buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        let output = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) { output[i] = Math.random() * 2 - 1; }
        
        let whiteNoise = audioCtx.createBufferSource();
        whiteNoise.buffer = buffer;
        whiteNoise.loop = true;
        
        let filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 800; // Yağmur uğultusu filtresi
        
        let gain = audioCtx.createGain();
        gain.gain.value = 0.15;
        
        whiteNoise.connect(filter);
        filter.connect(gain);
        gain.connect(audioCtx.destination);
        whiteNoise.start(0);
        noiseNode = whiteNoise;
        if(btn) btn.innerText = 'Sesi Kapat 🔇';
      } else {
        audioCtx.close();
        audioCtx = null;
        if(btn) btn.innerText = 'Sesi Başlat 🔊';
      }
    }

    // Zen Modu
    function toggleZenMode() {
      var zen = document.getElementById('zenOverlay');
      zen.classList.toggle('hidden');
    }

    // Konfeti Kutlaması
    function celebrate() {
      confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
    }

    // Command Palette & Doğal Dil İşleme
    window.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); toggleCmdPalette(); }
      if (e.key === 'Escape') { closeCmdPalette(); var z = document.getElementById('zenOverlay'); if(!z.classList.contains('hidden')) z.classList.add('hidden'); }
      if (e.key.toLowerCase() === 'f' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        toggleZenMode();
      }
    });

    function toggleCmdPalette() {
      var m = document.getElementById('cmdPalette');
      m.classList.toggle('hidden');
      if(!m.classList.contains('hidden')) {
        var inp = document.getElementById('cmdInput');
        inp.focus();
        handleCmdInput();
      }
    }
    function closeCmdPalette() { document.getElementById('cmdPalette').classList.add('hidden'); }

    // Akıllı Doğal Dil Ayrıştırma (NLP)
    function parseNaturalLanguage(text) {
      let lower = text.toLowerCase();
      let priority = "normal";
      if (lower.includes('!kritik') || lower.includes('!acil')) { priority = "high"; lower = lower.replace('!kritik','').replace('!acil',''); }
      
      let targetDate = new Date();
      if (lower.includes('yarın') || lower.includes('yarin')) {
        targetDate.setDate(targetDate.getDate() + 1);
        lower = lower.replace('yarın','').replace('yarin','');
      }

      let timeMatch = lower.match(/([0-1]?[0-9]|2[0-3]):[0-5][0-9]/);
      let timeStr = timeMatch ? timeMatch[0] : null;
      if (timeStr) lower = lower.replace(timeStr, '');

      let title = lower.replace('görev:', '').replace('gorev:', '').trim();
      let dateStr = targetDate.toISOString().split('T')[0];
      return { title: title, date: dateStr, time: timeStr, priority: priority };
    }

    function handleCmdInput() {
      var val = document.getElementById('cmdInput').value.trim();
      var hint = document.getElementById('cmdStatusText');
      if (!val) {
        hint.innerHTML = 'Örnek: <span class="text-cyan-300">görev: yarın 14:00 toplantı !kritik</span> veya <span class="text-amber-300">not: Başlık | Detay</span>';
        return;
      }
      if (val.toLowerCase().startsWith('görev:') || val.toLowerCase().startsWith('gorev:')) {
        var p = parseNaturalLanguage(val);
        hint.innerHTML = '📅 <b class="text-cyan-300">' + p.title + '</b> (' + p.date + (p.time ? ' ' + p.time : '') + ') [' + p.priority + '] olarak kaydedilecek.';
      } else if (val.toLowerCase().startsWith('not:')) {
        hint.innerHTML = '📝 Not kaydedilecek. (Enter ↵)';
      } else {
        hint.innerHTML = '🔍 Not ve görevlerde aranıyor: "' + val + '"';
      }
    }

    async function handleCmdKeyDown(e) {
      if (e.key === 'Enter') {
        var val = document.getElementById('cmdInput').value.trim();
        if (!val) return;
        if (val.toLowerCase().startsWith('görev:') || val.toLowerCase().startsWith('gorev:')) {
          var p = parseNaturalLanguage(val);
          await fetch('/api/quick-task-json', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: p.title, task_date: p.date, start_time: p.time, priority: p.priority})
          });
          window.location.reload();
        } else if (val.toLowerCase().startsWith('not:')) {
          var payload = val.substring(4).split('|');
          await fetch('/api/quick-note-json', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: payload[0].trim(), content: payload.length > 1 ? payload[1].trim() : '', category: '#quick'})
          });
          window.location.reload();
        }
      }
    }

    // Birim Dönüştürücüler
    function convertTorque(from) {
      if (from === 'nm') {
        var v = parseFloat(document.getElementById('valNm').value) || 0;
        document.getElementById('valLbft').value = (v * 0.737562).toFixed(2);
      } else {
        var v = parseFloat(document.getElementById('valLbft').value) || 0;
        document.getElementById('valNm').value = (v / 0.737562).toFixed(2);
      }
    }
    function convertPressure(from) {
      if (from === 'bar') {
        var v = parseFloat(document.getElementById('valBar').value) || 0;
        document.getElementById('valPsi').value = (v * 14.5038).toFixed(2);
      } else {
        var v = parseFloat(document.getElementById('valPsi').value) || 0;
        document.getElementById('valBar').value = (v / 14.5038).toFixed(2);
      }
    }
    function convertTemp(from) {
      if (from === 'c') {
        var v = parseFloat(document.getElementById('valC').value) || 0;
        document.getElementById('valF').value = (v * 9/5 + 32).toFixed(1);
      } else {
        var v = parseFloat(document.getElementById('valF').value) || 0;
        document.getElementById('valC').value = ((v - 32) * 5/9).toFixed(1);
      }
    }

    function filterNotes() {
      var query = document.getElementById('noteSearch').value.toLowerCase();
      document.querySelectorAll('.note-card').forEach(function(card) {
        card.style.display = card.getAttribute('data-search').includes(query) ? 'flex' : 'none';
      });
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
def index(request: Request, tab: str = "dashboard"):
    from jinja2 import Template
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.task_date.desc(), Task.start_time.asc()).all()
        notes = db.query(Note).order_by(Note.id.desc()).all()
        habits = db.query(Habit).all()
        inventory = db.query(InventoryItem).all()
        
        raw_projects = db.query(Project).all()
        projects = []
        for p in raw_projects:
            total = len(p.items)
            done = sum(1 for it in p.items if it.is_done)
            progress = int((done / total) * 100) if total > 0 else 0
            projects.append({"id": p.id, "name": p.name, "progress": progress, "items": p.items})

        today_dt = date.today()
        current_log = db.query(DailyLog).filter(DailyLog.log_date == today_dt).first()
        today_tasks = [t for t in tasks if t.task_date == today_dt]
        
        # Kanban Sütunları
        kanban_todo = [t for t in tasks if t.status == "todo" and not t.is_completed]
        kanban_in_progress = [t for t in tasks if t.status == "in_progress" and not t.is_completed]
        kanban_done = [t for t in tasks if t.status == "done" or t.is_completed]

        streak, heatmap_days = calculate_streak_and_heatmap(db)
    finally:
        db.close()

    app_url = str(request.base_url).rstrip('/')
    t = Template(HTML_LAYOUT)
    return t.render(
        current_tab=tab,
        tasks=tasks,
        today_tasks=today_tasks,
        notes=notes,
        habits=habits,
        projects=projects,
        inventory=inventory,
        kanban_todo=kanban_todo,
        kanban_in_progress=kanban_in_progress,
        kanban_done=kanban_done,
        current_log=current_log,
        today=today_dt.isoformat(),
        today_date=today_dt,
        streak=streak,
        heatmap_days=heatmap_days,
        app_url=app_url
    )

# --- Görev & Kanban Rotaları ---
@app.post("/task/add")
def add_task(
    title: str = Form(...),
    description: str = Form(""),
    task_date: str = Form(None),
    start_time: str = Form(None),
    end_time: str = Form(None),
    priority: str = Form("normal"),
    tab: str = Form("calendar")
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
            priority=priority,
            status="todo"
        )
        db.add(new_task)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

@app.get("/task/toggle/{task_id}")
def toggle_task(task_id: int, tab: str = "calendar"):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.is_completed = not task.is_completed
            task.status = "done" if task.is_completed else "todo"
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

@app.get("/task/status/{task_id}/{status_code}")
def change_task_status(task_id: int, status_code: str):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status_code
            task.is_completed = (status_code == "done")
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=projects", status_code=303)

@app.get("/task/delete/{task_id}")
def delete_task(task_id: int, tab: str = "calendar"):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            db.delete(task)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

# --- Günün Odağı (Highlight) & Günlük Log ---
@app.post("/highlight/set")
def set_highlight(highlight: str = Form(...)):
    db = SessionLocal()
    try:
        today_dt = date.today()
        log = db.query(DailyLog).filter(DailyLog.log_date == today_dt).first()
        if log:
            log.daily_highlight = highlight
            log.highlight_done = False
        else:
            log = DailyLog(log_date=today_dt, daily_highlight=highlight, highlight_done=False)
            db.add(log)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=dashboard", status_code=303)

@app.get("/highlight/toggle")
def toggle_highlight():
    db = SessionLocal()
    try:
        today_dt = date.today()
        log = db.query(DailyLog).filter(DailyLog.log_date == today_dt).first()
        if log:
            log.highlight_done = not log.highlight_done
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=dashboard", status_code=303)

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
    return RedirectResponse(url="/?tab=dashboard", status_code=303)

# --- Rutinler (Habits) ---
@app.post("/habit/add")
def add_habit(name: str = Form(...), tab: str = "dashboard"):
    db = SessionLocal()
    try:
        h = Habit(name=name)
        db.add(h)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

@app.get("/habit/toggle/{habit_id}")
def toggle_habit(habit_id: int, tab: str = "dashboard"):
    db = SessionLocal()
    try:
        h = db.query(Habit).filter(Habit.id == habit_id).first()
        if h:
            today_dt = date.today()
            h.last_done_date = None if h.last_done_date == today_dt else today_dt
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

@app.get("/habit/delete/{habit_id}")
def delete_habit(habit_id: int, tab: str = "dashboard"):
    db = SessionLocal()
    try:
        h = db.query(Habit).filter(Habit.id == habit_id).first()
        if h:
            db.delete(h)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

# --- Notlar ---
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
    return RedirectResponse(url="/?tab=notes", status_code=303)

@app.get("/note/delete/{note_id}")
def delete_note(note_id: int, tab: str = "notes"):
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            db.delete(note)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

# --- Projeler & Şablonlar ---
@app.post("/project/add")
def add_project(name: str = Form(...)):
    db = SessionLocal()
    try:
        new_proj = Project(name=name)
        db.add(new_proj)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=projects", status_code=303)

@app.get("/project/template/{template_type}")
def add_project_template(template_type: str):
    db = SessionLocal()
    try:
        if template_type == "tech":
            proj = Project(name="Otomasyon & Bot Geliştirme")
            db.add(proj)
            db.flush()
            for step in ["Gereksinimler & API Analizi", "Veritabanı Şeması Tasarımı", "Temel Kodlama & Testler", "Render Deploy & Canlıya Alma"]:
                db.add(ProjectItem(project_id=proj.id, title=step))
        elif template_type == "3dprint":
            proj = Project(name="3D Parça İmalatı")
            db.add(proj)
            db.flush()
            for step in ["CAD Modelleme & Tolerans Kontrolü", "Slicer Dilimleme Ayarları", "Baskı & Kalibrasyon Testi", "Zımpara & Montaj"]:
                db.add(ProjectItem(project_id=proj.id, title=step))
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=projects", status_code=303)

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
    return RedirectResponse(url="/?tab=projects", status_code=303)

@app.post("/project-item/add")
def add_project_item(project_id: int = Form(...), title: str = Form(...)):
    db = SessionLocal()
    try:
        it = ProjectItem(project_id=project_id, title=title)
        db.add(it)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=projects", status_code=303)

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
    return RedirectResponse(url="/?tab=projects", status_code=303)

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
    return RedirectResponse(url="/?tab=projects", status_code=303)

# --- Envanter ---
@app.post("/inventory/add")
def add_inventory(name: str = Form(...), category: str = Form("Genel"), quantity: float = Form(1.0), unit: str = Form("adet")):
    db = SessionLocal()
    try:
        it = InventoryItem(name=name, category=category, quantity=quantity, unit=unit)
        db.add(it)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=tools", status_code=303)

@app.get("/inventory/delete/{item_id}")
def delete_inventory(item_id: int):
    db = SessionLocal()
    try:
        it = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if it:
            db.delete(it)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?tab=tools", status_code=303)

# --- JSON Uçları (Command Palette) ---
@app.post("/api/quick-note-json")
async def quick_note_json(request: Request):
    body = await request.json()
    db = SessionLocal()
    try:
        new_note = Note(title=body.get("title", "Hızlı Not"), category=body.get("category", "#quick"), content=body.get("content", ""), created_at=date.today())
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
            start_time=body.get("start_time"),
            priority=body.get("priority", "normal"),
            status="todo"
        )
        db.add(new_task)
        db.commit()
    finally:
        db.close()
    return JSONResponse({"status": "ok"})

# --- FullCalendar API ---
@app.get("/api/events")
def get_events():
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        events = []
        for t in tasks:
            color = "#059669" if t.is_completed else ("#e11d48" if t.priority == "high" else ("#0284c7" if t.priority == "normal" else "#64748b"))
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

# --- iCal / Google Takvim Feed API'si ---
@app.get("/api/calendar.ics")
def calendar_ics_feed():
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Kisisel Command Center//TR",
            "CALSCALE:GREGORIAN"
        ]
        for t in tasks:
            d_str = t.task_date.strftime("%Y%m%d")
            if t.start_time:
                s_time = t.start_time.replace(":", "") + "00"
                e_time = t.end_time.replace(":", "") + "00" if t.end_time else s_time
                dtstart = f"DTSTART:{d_str}T{s_time}"
                dtend = f"DTEND:{d_str}T{e_time}"
            else:
                dtstart = f"DTSTART;VALUE=DATE:{d_str}"
                dtend = f"DTEND;VALUE=DATE:{d_str}"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:task-{t.id}@commandcenter",
                dtstart,
                dtend,
                f"SUMMARY:{t.title}",
                f"DESCRIPTION:{t.description or ''}",
                "STATUS:" + ("COMPLETED" if t.is_completed else "CONFIRMED"),
                "END:VEVENT"
            ])
        lines.append("END:VCALENDAR")
        ics_data = "\r\n".join(lines)
    finally:
        db.close()
    return Response(content=ics_data, media_type="text/calendar")

# --- Yedekleme (Backup) ---
@app.get("/api/backup")
def export_backup():
    db = SessionLocal()
    try:
        data = {
            "tasks": [{"title": t.title, "desc": t.description, "date": str(t.task_date), "start": t.start_time, "end": t.end_time, "prio": t.priority, "done": t.is_completed} for t in db.query(Task).all()],
            "notes": [{"title": n.title, "category": n.category, "content": n.content, "date": str(n.created_at)} for n in db.query(Note).all()],
            "habits": [{"name": h.name, "last_done": str(h.last_done_date)} for h in db.query(Habit).all()],
            "inventory": [{"name": i.name, "category": i.category, "qty": i.quantity, "unit": i.unit} for i in db.query(InventoryItem).all()],
            "projects": [{"name": p.name, "items": [{"title": it.title, "done": it.is_done} for it in p.items]} for p in db.query(Project).all()]
        }
    finally:
        db.close()
    return Response(content=json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json")
