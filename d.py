# -*- coding: utf-8 -*-
"""
بوت Facebook لمراقبة الردود (muxe ai)
- كيجاوب على أي سؤال (ماشي غير الدراسة). إلا سولوه شكون هو كيقول: أنا muxe ai
- النص: DeepSeek (Groq/Gemini احتياطي)
- الصور: Google Lens كيقرا النص من الصورة، ومن بعد الـ AI كيجاوب على الأسئلة
- "jawb 3lih" (ولا 1 / 2 بوحدها) فـ رد على تعليق = كيجاوب على التعليق اللي رد عليه
- كيحدث الصفحة وكيقرا غير الردود (Reply by...)
"""
import base64
import sys
import glob
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ==========================================================
# الإعدادات
# ==========================================================
# كل المفاتيح والإعدادات اللي كتبدل كاينين فـ ملف fb_bot_config.json (بجانب هاد الملف).
# هكا ملي كيجيك كود جديد ما خاصك تبدل والو، غير خلي fb_bot_config.json كيف ما هو.
# كل الإعدادات دابا مدمجة هنا (بلا ملف fb_bot_config.json)
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CFG = {
    "GROQ_API_KEY": "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",
    "IMAGE_API_URL": "https://baraa-image-ai.lovable.app/api/public/generate?key=bai_live_026369b1fb4545bf60c313c15925afb088e2f7dc1c203215",
    "IMAGE_API_KEY": "bai_live_5e66cdc4653d2c4c57a7a757eb5efc7d35819ec2c431b7e4",
    "MY_NAME": "Momo Chi",
    "POST_URL": "https://www.facebook.com/share/p/1FY4Zz46UK/",
    "GEMINI_API_KEY": "",   # حط هنا مفتاح Gemini باش خدمو الرد بـ 2
    "GEMINI_MODEL": "gemini-flash-latest",
    "FB_EMAIL": "",   # اختياري
    "FB_PASS": "",    # اختياري
}


def cfg(name, default=""):
    """الأولوية: الملف ثم env ثم القيمة الافتراضية."""
    return str(CFG.get(name) or os.environ.get(name) or default).strip()


GROQ_API_KEY = cfg("GROQ_API_KEY")
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Gemini (للردود اللي كتبدا بـ 2). المفتاح فـ CFG (أول الملف)
GEMINI_API_KEY = cfg("GEMINI_API_KEY")
GEMINI_MODEL = cfg("GEMINI_MODEL", "gemini-flash-latest")

# DeepSeek (الأساسي). Groq كيبقى احتياطي إلا كان GROQ_API_KEY موجود فـ CFG (أول الملف)
DEEPSEEK_URL = cfg("DEEPSEEK_URL", "https://deep-seek.ai/api/chat")
DEEPSEEK_MODEL = cfg("DEEPSEEK_MODEL", "deepseek/deepseek-v4-flash")
DEEPSEEK_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "ar,en-US;q=0.8,q=0.9,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://deep-seek.ai",
    "Referer": "https://deep-seek.ai/ar/chat",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

# توليد الصور (نفس API ديال بوت تيليجرام) - المفاتيح فـ CFG (أول الملف)
IMAGE_API_URL = cfg("IMAGE_API_URL")
IMAGE_API_KEY = cfg("IMAGE_API_KEY")



_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(_BASE_DIR, "facebook_cookies.json")        # الكوكيز اللي كتحط نتا (مرة وحدة)
COOKIES_SAVED = os.path.join(_BASE_DIR, "facebook_cookies_saved.json")  # نسخة كيحفظها البوت وحدو
FB_EMAIL = cfg("FB_EMAIL")      # اختياري: تسجيل دخول بالإيميل/الباسورد إلا الكوكيز طاحو
FB_PASS = cfg("FB_PASS")
MY_NAME = cfg("MY_NAME", "Momo Chi")
POST_URL = cfg("POST_URL", "https://www.facebook.com/share/p/1FY4Zz46UK/")

REFRESH_INTERVAL = float(cfg("REFRESH_INTERVAL", "5") or 5)   # المراقب (بلا حساب) كيدير refresh كل 5 ثواني
HEDGE_SECONDS = float(cfg("HEDGE_SECONDS", "4") or 4)   # إلا المحرك ما جاوبش فـ 6 ثواني كنبداو الاحتياطي بالتوازي

# مراقب بلا حساب: متصفح Incognito كيشوف عدد الردود فـ الصفحة العامة.
# الحساب كيدير refresh وقراءة غير ملي كيتبدل العدد.
WATCH_ENABLED = cfg("WATCH_ENABLED", "1") != "0"
# 1 = كشف الردود الجداد من المتصفح الرئيسي (الحساب) مباشرة: أسرع. 0 = بالمراقب (Incognito) القديم
FAST_DETECT = cfg("FAST_DETECT", "0") == "1"
WATCH_HEADLESS = cfg("WATCH_HEADLESS", "1") != "0"
HEARTBEAT_SECONDS = int(cfg("HEARTBEAT_SECONDS", "0") or 0)   # 0 = مطفي (الحساب ما كيدير والو بلا رد جديد)
MAX_ATTEMPTS = 3
CONTEXT_MESSAGES = 6
HEADLESS = False            # Google كيحظر headless بزاف، خليه False
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
LENS_COOLDOWN = 900         # إلا تبلوكا Lens، تسنى 15 دقيقة
LENS_DEBUG_SHOT = "lens_debug.png"

SYSTEM_PROMPT = (
    "أنت muxe ai، مساعد ذكي كيجاوب على أي سؤال كيتطرح عليك فـ أي موضوع بلا استثناء: "
    "الدراسة والفروض والامتحانات، الثقافة العامة، الدين، الرياضة، التقنية والبرمجة، الصحة، النصائح، الدردشة وكل شي. "
    "ما تقول أبدا أن السؤال ماشي ديال الدراسة وما ترفضش تجاوب بسبب الموضوع: جاوب مباشرة وبمعلومات صحيحة وواضحة. "
    "إلا ما كنتيش متأكد من معلومة قابلة للتغيير (أرقام، ترتيب، أخبار) جاوب بأحسن معلومة عندك وقول أنها ممكن تتبدل. "
    "إلا سولوك شكون نتا، شنو سميتك، شكون صاوبك، شنو الموديل ولا شنو الشركة ديالك: جاوب غير بأنك muxe ai. "
    "ما تقولش أبدا أنك DeepSeek ولا ChatGPT ولا Gemini ولا Claude ولا OpenAI ولا Google ولا أي موديل أو شركة أخرى، "
    "وما تذكرش شنو الموديل اللي خدام وراءك. "
    "جاوب بنفس اللغة اللي كيهضر بها الشخص (الدارجة، العربية، الفرنسية، الإنجليزية). "
    "إلا كان نص الامتحان بالفرنسية جاوب بالفرنسية. "
    "إلا كان فـ الرسالة نص مستخرج من تصويرة جاوب على كل الأسئلة والتمارين اللي فيه. "
    "جاوب بشكل كامل ومنظم، وجاوب على كل الأسئلة بلا ما تقطع الجواب. "
    "إلا كان الرد على تحية ولا سؤال بسيط جاوب فـ سطر ولا سطرين بسرعة. "
    "التنسيق: كل جواب فـ سطر جديد. إلا كانو بزاف ديال الأسئلة ابدأ كل جواب بـ رقم السؤال (1- ثم 2- ثم 3-...)، "
    "أما إلا كان سؤال واحد ولا تحية ولا سؤال بسيط جاوب مباشرة بلا رقم. "
    "ما تكتبش سميت الشخص ولا رقم الاختيار (1 ولا 2) فـ بداية الجواب. "
    "وخلي سطر فارغ بين كل سؤال والسؤال اللي موراه. إلا كان السؤال فيه فقرات صغيرة استعمل شرطة - فـ بداية كل سطر. "
    "ممنوع الجداول وممنوع علامة | وممنوع ماركداون (** و # و ```)، وبلا إيموجي. "
    "إلا كان فـ السؤال جدول، كتب كل عنصر فـ سطر بحالو (مثلا: 1: عمود كهربائي)."
)

# "View 129 replies" / "223 comments" / "عرض 129 رد" ...
SIG_RE = re.compile(
    r"(\d[\d.,]*)\s*([KkMm])?\s+(comments?|replies|reply|commentaires?|réponses?|réponse|تعليقات|تعليق|ردود|رد)(?![\w\u0600-\u06FF])",
    re.I)
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/122.0.0.0 Mobile Safari/537.36")

Msg = namedtuple("Msg", "idx name text label img_url")

# الردود فقط (Reply by ...)
REPLY_LABEL_RE = re.compile(r"^(?:Reply by|Réponse de|Reponse de|رد من|رد بواسطة)\s+(.+?)(?:\s+(?:to|à|إلى|على)\s.*)?$", re.I)
PARENT_RE = re.compile(r"(?:to|à|إلى|على)\s+(.+?)(?:'s|’s)?\s+(?:comment|commentaire|تعليق)", re.I)
AGO_RE = re.compile(r"\s+(?:\d+\s?\w+|an?\s+\w+|just now|about\s+.+?)\s+ago$|\s+il y a\s.*$|\s+منذ\s.*$", re.I)
TIME_RE = re.compile(r"^\d+\s?(s|m|min|h|d|j|w|y|sem|ث|د|س|ي|أ)$", re.I)
NOISE = {
    "like", "reply", "share", "see translation", "just now", "author", "admin", "edited",
    "top fan", "member", "j'aime", "j’aime", "répondre", "partager", "voir la traduction",
    "à l'instant", "à l’instant", "auteur", "modifié", "membre",
    "أعجبني", "رد", "مشاركة", "ترجمة", "الآن", "الآن فقط", "تم التعديل", "عضو", "مشرف",
}
STUDY_KEYWORDS = [
    "حل", "شرح", "تمرين", "فرض", "امتحان", "سؤال", "رياضيات", "فيزياء", "كيمياء", "علوم",
    "عربية", "فرنسية", "انجليزية", "فلسفة", "اجتماعيات", "تاريخ", "جغرافيا",
    "exercice", "devoir", "examen", "math", "physique", "chimie", "svt", "français", "anglais",
    "help", "aide", "question", "résoudre"
]

LENS_BLOCK_MARKERS = [
    "unusual traffic", "not a robot", "captcha", "our systems have detected",
    "trafic inhabituel", "inhabituel", "حركة مرور غير معتادة",
]

# علامات صفحة الرفع/AI Mode (يعني Lens ما عطاش النتائج)
UPLOAD_PAGE_MARKERS = [
    "drag an image here", "remove file attachment", "search any image with google lens",
    "glisser une image", "اسحب صورة",
]

LENS_NOISE = {
    "search", "all", "text", "translate", "products", "homework", "visual matches", "about this image",
    "find image source", "results", "copy text", "select all text", "listen", "sign in", "settings",
    "images", "videos", "news", "shopping", "more", "tools", "feedback", "privacy", "terms",
    "gmail", "ai mode", "skip to main content", "accessibility help", "accessibility feedback", "about this page", "short videos", "forums", "web",
    "recherche", "tout", "texte", "traduire", "produits", "devoirs", "copier le texte", "se connecter",
    "بحث", "الكل", "النص", "نص", "ترجمة", "منتجات", "الواجبات المنزلية", "نسخ النص", "تسجيل الدخول",
    "الصور", "فيديو", "أخبار", "المزيد", "ملاحظات",
}

JS_READ = r"""
const root = arguments[0] || document;
const out = [];
root.querySelectorAll("div[role='article']").forEach((a, i) => {
  const parts = [];
  a.querySelectorAll("div[dir='auto']").forEach(e => {
    const t = (e.innerText || '').trim();
    if (t) parts.push(t);
  });
  const imgs = [];
  a.querySelectorAll("img").forEach(img => {
    if (img.src && img.width > 80 && img.height > 80) imgs.push(img.src);
  });
  out.push({i: i, label: a.getAttribute('aria-label') || '', parts: parts, imgs: imgs});
});
return out;
"""


JS_SCROLL_DOWN = r"""
window.scrollTo(0, document.body.scrollHeight);
const d = document.querySelector("div[role='dialog']");
if (d) { d.querySelectorAll('div').forEach(x => { if (x.scrollHeight > x.clientHeight + 50) x.scrollTop = x.scrollHeight; }); }
"""

JS_FIND_LINK = r"""
const url = arguments[0];
for (const i of document.querySelectorAll("img")) {
  if (i.src === url) { const a = i.closest("a"); return a ? a.href : null; }
}
return null;
"""

JS_BIGGEST_IMG = r"""
let best = null, area = 0;
document.querySelectorAll("img").forEach(i => {
  const a = i.naturalWidth * i.naturalHeight;
  if (a > area && i.naturalWidth > 300 && (i.src || '').startsWith('http')) { area = a; best = i; }
});
return best;
"""

JS_FIND_IMG = r"""
const url = arguments[0];
for (const i of document.querySelectorAll("img")) { if (i.src === url) return i; }
return null;
"""


JS_CLICK_TEXT = r"""
const texts = arguments[0].map(t => t.toLowerCase());
const els = document.querySelectorAll("button,[role='button'],[role='tab'],[role='link'],a,div[tabindex],span");
for (const e of els) {
  const t = (e.innerText || '').trim().toLowerCase();
  const first = t.split('\n')[0].trim();
  const al = (e.getAttribute('aria-label') || '').trim().toLowerCase();
  if ((t && t.length < 40 && texts.includes(t)) || (first && first.length < 40 && texts.includes(first)) || (al && texts.includes(al))) {
    e.click(); return t || al;
  }
}
return null;
"""

JS_SHOW_FILE_INPUT = r"""
const inp = arguments[0];
inp.style.display = 'block'; inp.style.visibility = 'visible';
inp.style.opacity = 1; inp.style.width = '100px'; inp.style.height = '30px';
"""


JS_COMPOSER_FILE = r"""
let e = arguments[0];
for (let i = 0; i < 12 && e; i++) {
  const f = e.querySelector("input[type='file']");
  if (f) return f;
  e = e.parentElement;
}
return null;
"""

JS_COMPOSER_PREVIEW = r"""
let e = arguments[0];
for (let i = 0; i < 12 && e; i++) {
  if (e.querySelector("img[src^='blob:']")) return true;
  e = e.parentElement;
}
return false;
"""





JS_EXPAND_ALL = r"""
const root = arguments[0] || document;
const want = arguments[1] || 0;
const deadline = Date.now() + arguments[2];
const done = arguments[3];
const re = /^(view|see|voir|afficher|عرض|مشاهدة)\s.{0,40}(repl|répon|رد)/i;
const rre = /^(Reply by|R[ée]ponse de|رد من|رد بواسطة)/i;
const replyCount = () => {
  let n = 0;
  root.querySelectorAll("div[role='article']").forEach(a => {
    if (rre.test(a.getAttribute('aria-label') || '')) n++;
  });
  return n;
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  let clicks = 0, idle = 0;
  while (Date.now() < deadline) {
    if (want && replyCount() >= want) break;
    let n = 0;
    root.querySelectorAll("[role='button']").forEach(b => {
      const t = (b.innerText || '').trim();
      if (t.length < 60 && re.test(t)) { b.click(); n++; }
    });
    if (!n) {
      idle++;
      if (idle >= 3) break;
      await sleep(200);
      continue;
    }
    idle = 0;
    clicks += n;
    await sleep(300);
  }
  done(clicks);
})();
"""

POOL = ThreadPoolExecutor(max_workers=8)


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    out = line
    if os.environ.get("STY") or os.environ.get("TERM", "").startswith("screen"):
        # screen كيخربق الإيموجي وعلامات الاتجاه مع العربية: كنحيدوهم غير من الشاشة (الملف كيبقى كامل)
        out = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\uFE0E\uFE0F\u200B-\u200F\u202A-\u202E\u2066-\u2069]",
                     "", line)
    print(out, flush=True)
    try:        # نسخة فـ ملف UTF-8 (screen كيخربق الحروف العربية، وهكا تقدر تقراها مزيان بـ: tail -f bot.log)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_me(name):
    return MY_NAME.lower() in (name or "").lower()


def sig_total(sig):
    """مجموع الأرقام فـ البصمة (باش نعرفو شحال تزادو ردود)."""
    total = 0
    for x in sig or ():
        d = re.match(r"\d[\d.,]*", x)
        if d and not re.search(r"[KM]", x):
            total += int(re.sub(r"\D", "", d.group(0)) or 0)
    return total


def bmp_only(text):
    return re.sub(r"[^\u0000-\uFFFF]", "", text)


_NUM_RE = r"^\s*[0-9٠-٩]{1,2}\s*(?:[-–)]|\.(?![0-9٠-٩]))\s*"


def strip_choice(text):
    """كيحيد رقم الاختيار (1 ولا 2) من بداية رسالة التلميذ باش الـ AI ما يعاودوش."""
    t = (text or "").strip()
    m = re.match(r"^[12١٢]\s+(.+)$", t, flags=re.S)
    if not m:
        return t
    rest = m.group(1).strip()
    if re.match(r"^[0-9٠-٩+\-*/×÷=^.,:%)]", rest):    # مثلا "2 + 3": الرقم جزء من السؤال
        return t
    return rest


def clean_answer(text, name=""):
    """كيحيد سمية التلميذ من بداية الجواب، ورقم '1-' ولا '2-' إلا كان هو الوحيد (جواب واحد)."""
    orig = (text or "").strip()
    t = orig
    names = {n for n in ((name or "").strip(), (name or "").strip().split(" ")[0]) if n}
    for _ in range(2):
        for n in sorted(names, key=len, reverse=True):
            t = re.sub(r"^\s*@?" + re.escape(n) + r"\s*[:：,،\-–]*\s*", "", t, flags=re.I)
    lines = t.split("\n")
    nums = [i for i, l in enumerate(lines) if re.match(_NUM_RE, l)]
    if len(nums) == 1:
        lines[nums[0]] = re.sub(_NUM_RE, "", lines[nums[0]])
    t = "\n".join(lines).strip()
    return t or orig


def is_study_question(text):
    text_lower = (text or "").lower()
    if not text_lower:
        return False
    return any(k in text_lower for k in STUDY_KEYWORDS)


# ==========================================================
# الهوية (muxe ai) + أمر "jawb 3lih" + تنظيف الجواب
# ==========================================================
COMMENT_LABEL_RE = re.compile(r"^(?:Comment by|Commentaire de|تعليق من|تعليق بواسطة)\s+(.+?)$", re.I)
BOT_NAME = "muxe ai"


def norm_txt(text):
    """تطبيع النص (حروف عربية + علامات) باش المقارنة تكون سهلة."""
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        t = t.replace(a, b)
    t = re.sub(r"[^\w\s']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_ID_PATTERNS = [
    # دارجة / عربية
    r"\bشكون (?:نتا|نتي|انت|انتا|انتي|هاد البوت|هاذ البوت|هاد الذكاء)\b",
    r"\bمن (?:انت|انتي|هذا البوت)\b",
    r"\b(?:شنو|اش|ايش|شناهو|ما|ماهو|ما هو|ما هي) (?:هي )?(?:سميتك|اسمك|اسم البوت)\b",
    r"\bشكون (?:صاوبك|صنعك|دارك|برمجك|طورك|خدمك|صممك)\b",
    r"\bمن (?:صنعك|برمجك|طورك|انشاك|صممك|صاحب البوت)\b",
    r"\b(?:هل |واش )?(?:انت|نتا|نتي|انتا) (?:chat ?gpt|gpt|deep ?seek|gemini|claude|openai|ديب سيك|جيميني|شات جي بي تي|كلود|ذكاء اصطناعي|بوت|روبوت)\b",
    # دارجة بالحروف اللاتينية
    r"\b(?:chkoun|chkon|chkoune|shkoun|shkon|achkoun|chkun|shkun) (?:nta|nti|enta|inta|ntaa)\b",
    r"\b(?:chkoun|chkon|shkoun|shkon) (?:sawb|saweb|sawab|dar|barmaj|tawer)\w*\b",
    r"\b(?:chno|chnou|shno|chnu|achno|ach) (?:smitek|smitk|smytk|ismk|ismek|smitak)\b",
    r"\b(?:smitek|smitk|smytk)\b",
    # English
    r"\bwho are you\b",
    r"\bwhat are you\b",
    r"\bwhat(?:'s| is) your name\b",
    r"\bwho (?:made|created|built|developed|trained|owns|programmed) you\b",
    r"\b(?:what|which) (?:model|ai|llm|company) (?:are you|is this|made you)\b",
    r"\b(?:are you|r u) (?:chat ?gpt|gpt|deep ?seek|gemini|claude|openai|an ai|a bot|ai|a robot)\b",
    # Français
    r"\bqui es tu\b",
    r"\btu es qui\b",
    r"\bqui etes vous\b",
    r"\bqui êtes vous\b",
    r"\bcomment (?:tu t'appelles|tu t appelles|t'appelles tu|t appelles tu|vous appelez vous)\b",
    r"\bquel est (?:ton|votre) nom\b",
    r"\bqui t'a (?:cree|créé|fait|developpe|développé|programme|programmé)\b",
    r"\b(?:es tu|tu es|t'es) (?:chat ?gpt|gpt|deep ?seek|gemini|claude|openai|une ia|un robot|un bot)\b",
]
_ID_RE = re.compile("|".join(f"(?:{p})" for p in _ID_PATTERNS), re.I)


def is_identity_q(text):
    """واش الرسالة القصيرة هادي سؤال 'شكون نتا / شنو سميتك / شكون صاوبك'؟"""
    t = norm_txt(strip_choice(text))
    if not t or len(t.split()) > 10:
        return False
    return bool(_ID_RE.search(t))


def identity_answer(text):
    t = text or ""
    low = t.lower()
    if re.search(r"[\u0600-\u06FF]", t):
        return f"أنا {BOT_NAME}، مساعد ذكي كنجاوب على أي سؤال."
    if re.search(r"\b(qui|tu|vous|quel|comment|es-tu|êtes|t'a|t'es)\b", low):
        return f"Je suis {BOT_NAME}, un assistant intelligent qui répond à toutes vos questions."
    if re.search(r"\b(who|what|which|you|your|name|are)\b", low):
        return f"I'm {BOT_NAME}, a smart assistant that answers any question."
    return f"أنا {BOT_NAME}، مساعد ذكي كنجاوب على أي سؤال."


# أمر "jawb 3lih": الشخص كيطلب من البوت يجاوب على التعليق اللي رد عليه
_CMD_RE = re.compile(
    r"^(?:(?:a?jaw?[aeo]?b|jaou?b|jwb|جاوب(?:ني|و|ه|ها|لو|ليه|لها)?|اجب|اجيب)"
    r"(?:\s*(?:3lih|3liha|3lihom|3lyh|3lya|3la|3leh|3laih|alih|aleh|lih|liha|lo|lu|him|her|it|this|them|lui|moi"
    r"|عليه|عليها|عليهم|ليه|ليها|لو|له|هادا|هاد|هادي))?"
    r"|answer (?:him|her|it|this|them)|solve (?:it|this)|r[ée]ponds?(?: lui)?|رد (?:عليه|عليها|عليهم)|رد)"
    r"(?:\s+(?:please|plz|pls|svp|afak|3afak|عافاك|عفاك|بسرعه|دابا|daba|now))*$", re.I)


def is_answer_cmd(text):
    t = norm_txt(strip_choice(text))
    return bool(t) and bool(_CMD_RE.match(t))


def is_bare_choice(text):
    """رد فيه غير '1' ولا '2' = جاوب على التعليق اللي رديت عليه."""
    return bool(re.fullmatch(r"\s*[12١٢]\s*[.!؟?]*\s*", text or ""))


def parent_name(label):
    pm = PARENT_RE.search(label or "")
    return pm.group(1).strip() if pm else ""


# حماية: ما يتنسبش البوت لأي موديل/شركة أخرى (غير فـ الجمل اللي كيهضر فيها على راسو)
_MODEL_NAMES = (r"(?:Deep\s*Seek|ديب\s*سيك|Chat\s*GPT|شات\s*جي\s*بي\s*تي|GPT[-\s]?[\w.\-]*|Open\s*AI|أوبن\s*إيه?\s*آي|"
                r"Gemini|جيميني|Groq|Claude|كلود|Anthropic|Llama|Mistral|Qwen|Google|جوجل|قوقل|غوغل)")
_SELF_MARK = (r"(?:أنا|انا|je suis|i am|i['’]m|i was|my name is|mon nom est|اسمي|سميتي|طورتني|صنعتني|دربتني|برمجتني|"
              r"تم تطويري|تم تدريبي|تم إنشائي)")
_SELF_RE = re.compile(
    r"(?i)(" + _SELF_MARK + r"(?:[\s,،:\-]+[^\s,،.:\-]+){0,10}?[\s,،:\-]+)" + _MODEL_NAMES + r"(?![A-Za-z])")


def sanitize_identity(text):
    out = text or ""
    for _ in range(2):
        out = _SELF_RE.sub(lambda m: m.group(1) + BOT_NAME, out)
    return out


def parse_thread(raw, include_comments=False):
    thread = []
    for item in raw:
        label = (item.get("label") or "").strip()
        m = REPLY_LABEL_RE.match(label)
        if not m and include_comments:
            m = COMMENT_LABEL_RE.match(label)
        if not m:
            continue
        name = m.group(1).strip()
        name = AGO_RE.sub("", name).strip()
        parts = []
        for t in item.get("parts", []):
            t = re.sub(r"\s+", " ", t).strip()
            if (not t or t.lower() in NOISE or TIME_RE.match(t) or t == name or t in parts):
                continue
            parts.append(t)
        parts = [p for p in parts if not any(p != q and p in q for q in parts)]
        text = " ".join(parts).strip()
        pm = PARENT_RE.search(label)
        if pm and text:
            parent = pm.group(1).strip()
            stripped = re.sub(r"^\s*" + re.escape(parent) + r"\s*", "", text).strip()
            text = stripped or text

        imgs = item.get("imgs") or []
        img_url = imgs[0] if imgs else None
        thread.append(Msg(item.get("i", len(thread)), name, text, label, img_url))
    return thread


# ==========================================================
# الذكاء الاصطناعي - Groq (نص فقط)
# ==========================================================
class Groq:
    def __init__(self, key):
        self.key = key
        self.good = None

    def _headers(self):
        return {"Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
                "User-Agent": "Mozilla/5.0"}

    def _call(self, model, messages):
        body = {"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 3500}
        data = json.dumps(body).encode("utf-8")
        for attempt in range(3):
            req = urllib.request.Request(GROQ_URL, data=data, method="POST", headers=self._headers())
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    res = json.loads(r.read().decode("utf-8"))
                content = (res["choices"][0]["message"].get("content") or "").strip()
                return (content or None), (None if content else "other")
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "ignore")[:200]
                if e.code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                log(f"❌ Groq [{model}] HTTP {e.code}: {msg}")
                if e.code in (401, 403):
                    return None, "auth"
                if e.code in (400, 404) and "model" in msg.lower():
                    return None, "model"
                return None, "other"
            except Exception as e:
                log(f"❌ Groq [{model}] {e}")
                return None, "net"
        return None, "other"

    @staticmethod
    def clean(text):
        """كيحيد الماركداون والجداول، وكيحافظ على الأسطر."""
        text = re.sub(r"```[a-zA-Z]*", "", text)
        text = re.sub(r"[*`#]+", "", text)
        lines = []
        for l in text.replace("\r", "").split("\n"):
            if re.fullmatch(r"[\s|:\-]+", l) and "|" in l:   # |---|---|
                continue
            if "|" in l:
                cells = [c.strip() for c in l.strip().strip("|").split("|") if c.strip()]
                l = " - ".join(cells)
            l = re.sub(r"[ \t]+", " ", l).strip()
            lines.append(l)
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = bmp_only(text).strip()
        return text[:7500]

    def ask(self, messages):
        order = [self.good] if self.good else GROQ_MODELS
        for model in order:
            answer, err = self._call(model, messages)
            if answer:
                self.good = model
                return self.clean(answer) or None
            if err != "model":
                return None
        return None


# ==========================================================
# DeepSeek (SSE streaming) + احتياطي Groq
# ==========================================================
class DeepSeek:
    @staticmethod
    def _flatten(messages):
        """السيرفر كيقبل غير user/assistant (role=system كيعطي 422): كندمجو البرومبت فـ أول رسالة user."""
        sys_txt = "\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [dict(m) for m in messages if m["role"] != "system"]
        if sys_txt and rest:
            first = next((m for m in rest if m["role"] == "user"), None)
            if first:
                first["content"] = sys_txt + "\n\n" + first["content"]
        return rest

    def _call(self, messages):
        """كيرجع (الجواب, الخطأ). الخطأ = (status, message) إلا السيرفر رجع event: error."""
        body = json.dumps({"model": DEEPSEEK_MODEL, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(DEEPSEEK_URL, data=body, method="POST", headers=DEEPSEEK_HEADERS)
        reply, raw_all, err = "", "", None
        dbg = []
        with urllib.request.urlopen(req, timeout=60) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if line and len(dbg) < 3:
                    dbg.append(line[:150])
                if not line.startswith("data:"):
                    raw_all += line
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    j = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(j, dict) and j.get("error"):
                    e = j["error"]
                    msg = e.get("error") or e.get("message") if isinstance(e, dict) else e
                    err = (j.get("status") or 0, str(msg)[:200])
                    break                      # الخطأ ماشي جواب، ما كاين ما نتسناو
                delta = (j.get("choices") or [{}])[0].get("delta") or {}
                reply += delta.get("content") or ""
        if not reply and raw_all and not err:        # جواب JSON عادي (ماشي stream)
            try:
                j = json.loads(raw_all)
                reply = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            except Exception:
                pass
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S).strip()
        self.last_raw = " | ".join(dbg)
        return reply, err

    down_until = 0

    def _pause(self, seconds, why):
        self.down_until = time.time() + seconds
        log(f"⛔ DeepSeek {why} -> كنوقفوه {seconds // 60} دقيقة، الاحتياطي كيجاوب بلاصتو")

    def ask(self, messages):
        if time.time() < self.down_until:
            return None                      # موقوف: كنمشيو للاحتياطي فورا بلا تسنى
        flat = self._flatten(messages)
        for attempt in range(2):
            try:
                reply, err = self._call(flat)
                if reply:
                    return Groq.clean(reply) or None
                if err:
                    status, msg = err
                    if status == 429 or "limit" in msg.lower():
                        self._pause(1800, f"وصل الحد ديال اليوم ({msg[:70]})")
                        return None
                    log(f"❌ DeepSeek {status}: {msg[:120]}")
                else:
                    log(f"⚠️ DeepSeek رجع جواب خاوي ({attempt + 1}/2) {getattr(self, 'last_raw', '')[:200]}")
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "ignore")[:120]
                log(f"❌ DeepSeek HTTP {e.code}: {txt}")
                if e.code == 429:
                    self._pause(1800, "429")
                    return None
            except urllib.error.URLError as e:
                self._pause(120, f"ما بانش (DNS/شبكة): {str(e.reason)[:60]}")
                return None
            except Exception as e:
                log(f"❌ DeepSeek {str(e)[:120]}")
            time.sleep(1)
        return None


class GeminiWeb:
    """Gemini عبر واجهة gemini.google.com (بلا API key، بلا كوكيز) - نفس طريقة السكريبت اللي صيفطتي."""
    URL = "https://gemini.google.com"
    STREAM = URL + "/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
    BUILD = "boq_assistant-bard-web-server_20240519.16_p0"
    EXT = '[1,null,null,null,"35609594dbe934d8"]'          # gemini-3.5-flash
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/123.0 Safari/537.36")

    def __init__(self):
        import http.cookiejar
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.token, self.sid, self.bl, self.t_refresh = "", None, None, 0

    def _headers(self):
        return {"Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Origin": self.URL,
                "Referer": self.URL + "/", "User-Agent": self.UA, "X-Same-Domain": "1",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}

    def refresh(self):
        req = urllib.request.Request(self.URL, headers=self._headers())
        with self.opener.open(req, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
        t = re.search(r'"SNlM0e":"(.*?)"', html)
        sid = re.search(r'"FdrFJe":"([\d-]+)"', html)
        b = re.search(r'"cfb2h":"(.*?)"', html)
        self.token = t.group(1) if t else ""
        self.sid = sid.group(1) if sid else None
        self.bl = b.group(1) if b else self.BUILD
        self.t_refresh = time.time()
        return bool(self.token or self.sid or b)

    @staticmethod
    def _prompt(messages):
        sys_txt = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = []
        for m in messages:
            if m["role"] == "system":
                continue
            convo.append(("المساعد: " if m["role"] == "assistant" else "") + m["content"])
        out = (sys_txt + "\n\n" if sys_txt else "") + "\n".join(convo)
        return out[:30000]

    def ask(self, messages):
        if not self.bl or time.time() - self.t_refresh > 1800:
            self.refresh()
        req_data = [[self._prompt(messages), 0, None, [], None, None, 0], ["en"],
                    [None, None, None, None, None, []], None, None, None, [], 0, [], [], 1, 0]
        post = urllib.parse.urlencode({"at": self.token,
                                       "f.req": json.dumps([None, json.dumps(req_data)])}).encode()
        params = {"bl": self.bl or self.BUILD, "hl": "en", "_reqid": random.randint(10000, 99999), "rt": "c"}
        if self.sid:
            params["f.sid"] = self.sid
        headers = self._headers()
        headers["x-goog-ext-525001261-jspb"] = self.EXT
        req = urllib.request.Request(self.STREAM + "?" + urllib.parse.urlencode(params),
                                     data=post, method="POST", headers=headers)
        current = ""
        with self.opener.open(req, timeout=90) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line:
                    continue
                try:
                    outer = json.loads(line)
                    if not isinstance(outer, list) or not outer or len(outer[0]) < 3:
                        continue
                    text = json.loads(outer[0][2])[4][0][1][0]
                    if text and text.startswith(current):
                        current = text
                except (ValueError, TypeError, IndexError, KeyError):
                    continue
        if not current:
            self.bl = None          # باش يتجدد التوكن فـ المرة الجاية
        return current.strip()


class Gemini:
    @staticmethod
    def _convert(messages):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "model" if m["role"] == "assistant" else "user"
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"][0]["text"] += "\n" + m["content"]
            else:
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
        while contents and contents[0]["role"] == "model":
            contents.pop(0)
        return system, contents

    _bad_models = set()

    _web = None

    def _ask_web(self, messages):
        if Gemini._web is None:
            Gemini._web = GeminiWeb()
        for attempt in range(2):
            try:
                text = Gemini._web.ask(messages)
                if text:
                    return Groq.clean(text) or None
                log(f"⚠️ Gemini (ويب) جواب خاوي ({attempt + 1}/2)")
            except Exception as e:
                log(f"❌ Gemini (ويب) {str(e)[:120]}")
                Gemini._web.bl = None
            time.sleep(1)
        return None

    def ask(self, messages):
        if not GEMINI_API_KEY:
            return self._ask_web(messages)
        system, contents = self._convert(messages)
        if not contents:
            return None
        body = {"contents": contents,
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8000}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = json.dumps(body).encode("utf-8")
        # الموديل المضبوط أولا، ومن بعد موديلات احتياطية إلا ما خدمش / تبلوكا / سالات الحصة
        models = [GEMINI_MODEL] + [m for m in ("gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash",
                                               "gemini-flash-lite-latest") if m != GEMINI_MODEL]
        models = [m for m in models if m not in Gemini._bad_models] or [GEMINI_MODEL]
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                req = urllib.request.Request(url, data=data, method="POST", headers={
                    "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY})
                try:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        res = json.loads(r.read().decode("utf-8"))
                    parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                    if text:
                        return Groq.clean(text) or None
                    log(f"⚠️ Gemini [{model}] جواب خاوي: {str(res.get('promptFeedback') or res)[:120]}")
                    break
                except urllib.error.HTTPError as e:
                    msg = e.read().decode("utf-8", "ignore")[:150]
                    if e.code in (500, 502, 503) and attempt < 1:
                        time.sleep(2)
                        continue
                    log(f"❌ Gemini [{model}] HTTP {e.code}: {msg}")
                    if e.code in (400, 404) and "model" in msg.lower():
                        Gemini._bad_models.add(model)
                    if e.code in (401, 403):
                        return None          # المفتاح ما صالحش، العاود ما غادي ينفع
                    break                    # 429 وغيرها: نجرب الموديل الموالي
                except Exception as e:
                    log(f"❌ Gemini [{model}] {str(e)[:120]}")
                    break
        return None


class AI:
    """كيبدا بالمحرك المطلوب، وإلا فشل كيجرب الباقي (اللي مفتاحهم موجود)."""
    def __init__(self):
        self.ds = DeepSeek()
        self.gem = Gemini()
        self.groq = Groq(GROQ_API_KEY) if GROQ_API_KEY and GROQ_API_KEY.isascii() else None

    def _run(self, name, messages):
        try:
            if name == "deepseek":
                return self.ds.ask(messages)
            if name == "gemini":
                return self.gem.ask(messages)
            return self.groq.ask(messages) if self.groq else None
        except Exception as e:
            log(f"❌ {name}: {str(e)[:100]}")
            return None

    def ask(self, messages, engine="deepseek"):
        """كيبدا بالمحرك المطلوب؛ إلا فشل ولا تأخر (HEDGE_SECONDS) كيبدا الموالي بالتوازي، والأول اللي كيجاوب كيربح."""
        order = [engine] + [e for e in ("deepseek", "groq", "gemini") if e != engine]
        futs, nxt = {}, 0

        def start_next():
            nonlocal nxt
            while nxt < len(order):
                name = order[nxt]
                nxt += 1
                if name == "groq" and not self.groq:
                    continue
                futs[name] = POOL.submit(self._run, name, messages)
                return time.time()
            return None

        last_start = start_next()
        while futs or last_start is not None:
            for name, f in list(futs.items()):
                if f.done():
                    del futs[name]
                    ans = f.result()
                    if ans:
                        if name != engine:
                            log(f"↩️ {engine} فشل/تأخر -> جاوب {name} (احتياطي)")
                        return ans
                    if not futs and nxt < len(order):
                        last_start = start_next() or last_start
            if not futs and nxt >= len(order):
                return None
            if futs and nxt < len(order) and last_start and time.time() - last_start > HEDGE_SECONDS:
                last_start = start_next() or last_start
            time.sleep(0.05)
        return None


# ==========================================================
# Google Lens عبر Selenium
#   الطريقة 1: uploadbyurl (كتعطي Google رابط الصورة)
#   الطريقة 2: رفع الملف من Google Images (imghp)
# ==========================================================
class LensBlocked(Exception):
    pass


class GoogleLens:
    def __init__(self, driver):
        self.d = driver
        self.cooldown_until = 0

    @property
    def cooling(self):
        return time.time() < self.cooldown_until

    @staticmethod
    def wait(fn, timeout=10, poll=0.4):
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = fn()
                if r:
                    return r
            except Exception:
                pass
            time.sleep(poll)
        return None

    def _click_text(self, texts):
        try:
            return self.d.execute_script(JS_CLICK_TEXT, texts)
        except Exception:
            return None

    def _body_text(self):
        try:
            return self.d.find_element(By.TAG_NAME, "body").text
        except Exception:
            return ""

    def _check_blocked(self):
        low = self._body_text().lower()
        if any(m in low for m in LENS_BLOCK_MARKERS):
            raise LensBlocked("Google حظر الـ session (unusual traffic / captcha)")

    def _accept_consent(self):
        if "consent." in self.d.current_url:
            self._click_text(["accept all", "tout accepter", "قبول الكل", "i agree", "j'accepte"])
            time.sleep(2)

    def _on_upload_page(self):
        low = self._body_text().lower()
        return any(m in low for m in UPLOAD_PAGE_MARKERS)

    def _results_ready(self, timeout):
        """كيتسنى حتى تبان صفحة النتائج (ماشي صفحة الرفع)."""
        def ok():
            url = self.d.current_url
            if "google." not in url:
                return False
            if "/search" not in url and "vsrid" not in url:
                return False
            return not self._on_upload_page()
        done = self.wait(ok, timeout, 0.8)
        if done:
            time.sleep(1.5)
        return bool(done)

    def _find_file_input(self, timeout=8):
        return self.wait(
            lambda: (self.d.find_elements(By.CSS_SELECTOR, "input[type='file']") or [None])[0],
            timeout)

    def _debug(self):
        try:
            self.d.save_screenshot(LENS_DEBUG_SHOT)
            with open("lens_debug.txt", "w", encoding="utf-8") as f:
                f.write(self.d.current_url + "\n\n" + self._body_text()[:4000])
            log(f"🐞 debug: {LENS_DEBUG_SHOT} + lens_debug.txt")
        except Exception:
            pass

    # ---- الطريقة 1: رابط الصورة ----
    def _try_url(self, img_url):
        if not img_url or not img_url.startswith("http"):
            return False
        log("🔗 Lens بالرابط (uploadbyurl)...")
        self.d.get("https://lens.google.com/uploadbyurl?hl=en&url=" + urllib.parse.quote(img_url, safe=""))
        time.sleep(4)
        self._accept_consent()
        self._check_blocked()
        return self._results_ready(30)

    # ---- الطريقة 2: رفع الملف من Google Images ----
    def _try_upload(self, file_path):
        log("⬆️ Lens بالرفع (Google Images)...")
        self.d.get("https://www.google.com/imghp?hl=en")
        time.sleep(2)
        self._accept_consent()
        self._check_blocked()
        inp = self._find_file_input(2)
        if not inp:
            for sel in ("[aria-label='Search by image']", "div[aria-label='Search by image']",
                        "[aria-label*='by image' i]", "[aria-label*='Lens' i]"):
                try:
                    els = self.d.find_elements(By.CSS_SELECTOR, sel)
                    if els:
                        self.d.execute_script("arguments[0].click();", els[0])
                        break
                except Exception:
                    pass
            time.sleep(1.5)
            self._click_text(["upload a file", "upload an image", "importer un fichier"])
            inp = self._find_file_input(6)
        if not inp:
            log("⚠️ ما لقيتش input ديال الرفع")
            return False
        self.d.execute_script(JS_SHOW_FILE_INPUT, inp)
        inp.send_keys(file_path)
        log("⬆️ تحملات الصورة، كنتسنى النتائج...")
        return self._results_ready(40)

    @staticmethod
    def overview_answer(text):
        """كياخد فقرات جواب AI Overview فقط: كيحيد المصادر والروابط وأسماء المواقع والأسئلة المقترحة."""
        lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
        hard_end = ("ai responses may", "learn more", "are you trying")
        soft_end = ("sources", "visual matches", "search results", "exact matches", "related",
                    "people also", "about this image", "feedback", "ask a follow", "show less", "ai mode")
        sites = ("instagram", "pinterest", "deezer", "genius", "youtube", "spotify", "tiktok",
                 "facebook", "wikipedia", "reddit", "google", "twitter", "x.com")
        noise = ("show more", "show less", "read more", "feedback", "ai overview", "select text")
        for i, l in enumerate(lines):
            if "ai overview" in l.lower():
                out, total = [], 0
                for n in lines[i + 1:i + 60]:
                    low = n.lower()
                    if any(m in low for m in hard_end) or low.startswith(soft_end):
                        break
                    if any(low.startswith(x) for x in noise):
                        continue
                    if re.search(r"\b[\w-]+\.(com|org|net|fr|dz|ma|co|io|uk)\b", low):
                        continue
                    if any(s in low for s in sites) and len(n.split()) <= 5:
                        continue
                    words = n.split()
                    if len(words) <= 6 and not re.search(r"[.:!،,]$", n):
                        continue            # عنوان قصير بلا علامة جملة = غالبا عنوان مصدر
                    if re.search(r"[?؟]$", n):
                        continue            # سؤال مقترح، ماشي جزء من الجواب
                    out.append(n)
                    total += len(n)
                    if total > 900:
                        break
                if out:
                    return "\n".join(out)
        return None

    @staticmethod
    def _clean(text):
        out, seen = [], set()
        for l in text.split("\n"):
            l = l.strip()
            low = l.lower()
            if len(l) < 2 or low in LENS_NOISE or l in seen:
                continue
            if any(m in low for m in UPLOAD_PAGE_MARKERS):
                continue
            seen.add(l)
            out.append(l)
        return "\n".join(out)

    def _page_text(self):
        chunks = [self._body_text()]
        try:
            for fr in self.d.find_elements(By.TAG_NAME, "iframe")[:6]:
                try:
                    self.d.switch_to.frame(fr)
                    chunks.append(self._body_text())
                except Exception:
                    pass
                finally:
                    self.d.switch_to.default_content()
        except Exception:
            pass
        return "\n".join(chunks)

    def _expand_overview(self):
        """كيضغط Show more ديال AI Overview، بلا ما يدخل فالروابط (باش ما يتحولش لموقع آخر)."""
        labels = ["show more", "show all", "read more", "عرض المزيد", "إظهار المزيد",
                  "afficher plus", "voir plus"]
        js = """
        const texts = arguments[0];
        for (const e of document.querySelectorAll("button,[role='button'],span,div[tabindex]")) {
          if (e.closest('a')) continue;
          const t = (e.innerText || '').trim().toLowerCase();
          if (t && t.length < 40 && texts.includes(t)) { e.click(); return t; }
        }
        return null;
        """
        for _ in range(3):
            before = self.d.current_url
            try:
                hit = self.d.execute_script(js, labels)
            except Exception:
                hit = None
            if not hit:
                break
            time.sleep(1)
            if "google." not in (self.d.current_url or ""):
                log("↩️ الضغط فتح صفحة أخرى، كنرجع لـ Google")
                self.d.get(before)
                time.sleep(2)
                break
            log("📂 وسعت الجواب (Show more)")

    def _extract(self):
        """كيرجع النص ديال Lens: نص التصويرة (تاب Text) + صفحة النتائج (AI Overview) باش الـ AI يجاوب بيهم."""
        self._expand_overview()
        first = self._clean(self._page_text())
        ocr = ""
        try:
            if self._click_text(["text", "texte", "نص", "النص"]):
                log("🔤 ضغطت على تاب Text")
                time.sleep(2)
                self._click_text(["select all text", "tout sélectionner"])
                time.sleep(0.5)
                self._check_blocked()
                ocr = self._clean(self._page_text())
        except LensBlocked:
            raise
        except Exception as e:
            log(f"⚠️ تاب Text: {str(e)[:80]}")
        if ocr and ocr != first:
            return (ocr + "\n\n" + first).strip()
        return first

    def read_image(self, file_path, img_url=None):
        """كيرجع النص اللي قرا Google Lens من الصورة، ولا None."""
        if self.cooling:
            log("⏸ Lens فـ cooldown (تبلوكا قبل شوية)")
            return None

        original = self.d.current_window_handle
        opened_tab = False
        try:
            self.d.switch_to.new_window("tab")
            opened_tab = True

            for method in ("upload", "url"):
                try:
                    ok = self._try_url(img_url) if method == "url" else self._try_upload(file_path)
                except LensBlocked:
                    raise
                except Exception as e:
                    log(f"⚠️ Lens [{method}] {str(e)[:100]}")
                    ok = False
                if not ok:
                    log(f"⚠️ Lens [{method}] ما وصلش لصفحة النتائج")
                    continue
                log(f"🌐 الصفحة: {self.d.current_url[:90]}")
                result = self._extract()
                log(f"📖 Lens [{method}] لقا {len(result)} حرف: {result[:100].replace(chr(10), ' ')}...")
                if len(result) > 20:
                    return result
                self._debug()

            self._debug()
            return None

        except LensBlocked as e:
            log(f"🚫 {e}. كنوقفو Lens {LENS_COOLDOWN // 60} دقيقة")
            self.cooldown_until = time.time() + LENS_COOLDOWN
            self._debug()
            return None
        except Exception as e:
            log(f"❌ فشل Google Lens: {str(e)[:150]}")
            self._debug()
            return None
        finally:
            try:
                if opened_tab:
                    self.d.close()
                self.d.switch_to.window(original)
            except Exception:
                pass


# ==========================================================
# توليد الصور
# ==========================================================
def _http(req, timeout=90):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (r.headers.get("Content-Type") or "").lower(), r.read()


def _extract_image(ctype, data):
    """كيرجع bytes ديال الصورة من جواب الـ API (صورة مباشرة / JSON فيه رابط ولا base64)."""
    if ctype.startswith("image/"):
        return data
    res = json.loads(data.decode("utf-8", "ignore"))
    if isinstance(res, dict) and isinstance(res.get("data"), dict):
        res = res["data"]
    val = None
    for k in ("image_url", "imageUrl", "url", "image", "image_base64", "b64_json"):
        if isinstance(res, dict) and res.get(k):
            val = res[k]
            break
    if not val:
        raise ValueError(f"ما لقيتش الصورة فـ الجواب: {str(res)[:120]}")
    if val.startswith("http"):
        req = urllib.request.Request(val, headers={"User-Agent": "Mozilla/5.0"})
        return _http(req, 60)[1]
    if val.startswith("data:"):
        val = val.split(",", 1)[1]
    return base64.b64decode(val)


def generate_image(prompt):
    """كيولد صورة من الوصف وكيحفظها فـ ملف مؤقت، ولا كيرجع None."""
    if not IMAGE_API_URL or not IMAGE_API_KEY:
        log("❌ IMAGE_API_URL / IMAGE_API_KEY ماشي مضبوطين فـ CFG (أول الملف)")
        return None
    base = re.sub(r"[&?]prompt=$", "", IMAGE_API_URL)
    headers = {"Authorization": f"Bearer {IMAGE_API_KEY}", "Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0"}
    body = json.dumps({"prompt": prompt, "quality": "high"}).encode("utf-8")
    sep = "&" if "?" in base else "?"
    q = base + sep + "prompt=" + urllib.parse.quote(prompt)
    plain = {"User-Agent": "Mozilla/5.0"}
    tries = [
        urllib.request.Request(base, data=body, method="POST", headers=headers),
        urllib.request.Request(q, method="GET", headers=headers),
        urllib.request.Request(q, method="GET", headers=plain),          # المفتاح اللي فـ الرابط بوحدو
        urllib.request.Request(base, data=body, method="POST",
                               headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "x-api-key": IMAGE_API_KEY}),
    ]
    for rnd in range(3):
        wait_s = 0
        for req in tries:
            try:
                ctype, data = _http(req, 120)
                img = _extract_image(ctype, data)
                if len(img) < 1000:
                    raise ValueError("الصورة صغيرة بزاف")
                path = os.path.abspath(f"temp_gen_{int(time.time() * 1000)}.png")
                with open(path, "wb") as f:
                    f.write(img)
                return path
            except urllib.error.HTTPError as e:
                body_txt = e.read().decode("utf-8", "ignore")
                log(f"⚠️ توليد الصورة [{req.get_method()}] HTTP {e.code}: {body_txt[:120]}")
                if e.code in (401, 403):
                    return None              # المفتاح ما صالحش
                if e.code == 429 or "429" in body_txt or e.code in (500, 502, 503, 504):
                    ra = e.headers.get("Retry-After") if e.headers else None
                    try:
                        wait_s = max(wait_s, min(float(ra), 20))
                    except (TypeError, ValueError):
                        wait_s = max(wait_s, 4 * (rnd + 1))
            except Exception as e:
                log(f"⚠️ توليد الصورة [{req.get_method()}] {str(e)[:150]}")
        if rnd < 2 and wait_s:
            log(f"⏳ الخدمة مشغولة (429)، كنعاود من بعد {wait_s:.0f}s ({rnd + 2}/3)")
            time.sleep(wait_s)
        elif not wait_s:
            break
    return None


# ==========================================================
# البوت
# ==========================================================
class Bot:
    def __init__(self):
        self.d = None
        self.w = None
        self.sig = None
        self.ai = AI()
        self.lens = None
        self.attempts = {}
        self.done_stable = set()
        self.empty_polls = 0

    def start_browser(self):
        opts = Options()
        opts.page_load_strategy = "eager"
        if HEADLESS:
            opts.add_argument("--headless=new")
        for a in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1400,900",
                  "--disable-blink-features=AutomationControlled", "--lang=ar", "--disable-extensions"):
            opts.add_argument(a)
        opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
        for lk in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                os.remove(os.path.join(PROFILE_DIR, lk))
            except OSError:
                pass
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()
        self.d = webdriver.Chrome(service=service, options=opts)
        self.d.set_page_load_timeout(60)
        try:
            self.d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                                   {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
        except Exception:
            pass
        self.lens = GoogleLens(self.d)
        log("✅ المتصفح اشتغل")

    def quit_browser(self):
        for attr in ("d", "w"):
            try:
                drv = getattr(self, attr, None)
                if drv:
                    drv.quit()
            except Exception:
                pass
            setattr(self, attr, None)
        tmp = getattr(self, "w_tmp", None)
        if tmp:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
            self.w_tmp = None

    # ---------- المراقب بلا حساب (Incognito) ----------
    def start_watcher(self):
        """كيشغل متصفح Incognito بلا حساب. إلا Chrome تسد فجأة كيعاود حتى 3 مرات ببروفايل مؤقت جديد."""
        import shutil
        import tempfile
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver_path = ChromeDriverManager().install()
        except Exception:
            driver_path = None
        last_err = None
        for attempt in range(3):
            tmp = tempfile.mkdtemp(prefix="fbwatch_")
            opts = Options()
            opts.page_load_strategy = "eager"
            if WATCH_HEADLESS:
                opts.add_argument("--headless=new")
            for a in ("--incognito", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-extensions", "--window-size=480,900", "--lang=en",
                      "--no-first-run", "--no-default-browser-check", f"--user-data-dir={tmp}"):
                opts.add_argument(a)
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("mobileEmulation", {
                "deviceMetrics": {"width": 412, "height": 915, "pixelRatio": 2.6},
                "userAgent": MOBILE_UA})
            try:
                service = Service(driver_path) if driver_path else Service()
                self.w = webdriver.Chrome(service=service, options=opts)   # بروفايل مؤقت خاوي = بلا حساب
                self.w_tmp = tmp
                self.w.set_page_load_timeout(40)
                log("🕵️ المراقب (Incognito بلا حساب) اشتغل")
                return
            except Exception as e:
                last_err = e
                shutil.rmtree(tmp, ignore_errors=True)
                log(f"⚠️ المراقب ما بدا (محاولة {attempt + 1}/3): {str(e).splitlines()[0][:100]}")
                time.sleep(3)
        raise last_err

    @staticmethod
    def _sig_from_text(text):
        """بصمة الصفحة: الأرقام اللي كتبان قبل أول 'Reply' (عدد التعليقات/المشاركات...).
        كتخدم حتى ملي كيتبدل شكل الصفحة بلا حساب. احتياط: 'N replies'."""
        head = []
        for l in (x.strip() for x in text.split("\n")):
            if l.lower() in ("reply", "répondre", "رد"):
                break
            if re.fullmatch(r"\d[\d.,]*\s?[KkMm]?", l):
                head.append(l.replace(" ", "").upper())
                if len(head) >= 3:
                    break
        if head:
            return tuple(head)
        found = sorted({f"{m.group(1)}{(m.group(2) or '').upper()} {m.group(3).lower()}"
                        for m in SIG_RE.finditer(text)})
        return tuple(found) or None

    def _watch_debug(self):
        """كيصور الشاشة ويحفظ نص الصفحة ملي المراقب ما كيقراش العدد (مرة كل دقيقة)."""
        now = time.time()
        if now - getattr(self, "_wd_last", 0) < 60:
            return
        self._wd_last = now
        try:
            url = self.w.current_url
            text = self.w.find_element(By.TAG_NAME, "body").text
            self.w.save_screenshot("watch_debug.png")
            with open("watch_debug.txt", "w", encoding="utf-8") as f:
                f.write(f"URL: {url}\nTITLE: {self.w.title}\n\n{text[:6000]}")
            log(f"🐞 المراقب ما لقاش العدد. URL: {url[:100]}")
            log(f"🐞 عنوان الصفحة: {self.w.title[:60]}")
            short = re.sub(r"\s+", " ", text)[:300]
            log(f"🐞 نص الصفحة: {short}")
            log("🐞 تحفظو: watch_debug.png و watch_debug.txt (فـ نفس فولدر البوت)")
        except Exception as e:
            log(f"🐞 debug فشل: {str(e)[:80]}")

    def watch_signature(self):
        """كيدير refresh فـ المتصفح بلا حساب وكيرجع بصمة عدد الردود/التعليقات، ولا None."""
        try:
            if self.w is None:
                self.start_watcher()
            cur = self.w.current_url or ""
            hard = getattr(self, "_watch_hard", False)
            if hard or "facebook.com" not in cur or "login" in cur or "checkpoint" in cur:
                self.w.get(POST_URL)       # رجوع كامل للمنشور (ماشي refresh لصفحة login)
            else:
                self.w.refresh()
            time.sleep(0.3)
            end = time.time() + 14
            sig = None
            while True:
                text = self.w.find_element(By.TAG_NAME, "body").text
                sig = self._sig_from_text(text)
                if sig or time.time() > end:
                    break
                time.sleep(0.3)
            self._watch_hard = not sig
            if not sig:
                self._watch_debug()
            return sig
        except Exception as e:
            log(f"⚠️ المراقب: {str(e)[:100]}")
            try:
                if self.w:
                    self.w.quit()
            except Exception:
                pass
            self.w = None          # غادي يتعاود يتفتح فـ الدورة الجاية
            return None

    def wait(self, fn, timeout=15, poll=0.4):
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = fn()
                if r:
                    return r
            except Exception:
                pass
            time.sleep(poll)
        return None

    def close_popups(self):
        try:
            for b in self.d.find_elements(By.XPATH, "//*[@role='button' and (normalize-space()='Not Now' or normalize-space()='Pas maintenant' or normalize-space()='ليس الآن')]"):
                if b.is_displayed():
                    self.d.execute_script("arguments[0].click();", b)
        except Exception:
            pass

    def session_ok(self):
        try:
            names = {c["name"] for c in self.d.get_cookies()}
            return "c_user" in names and "xs" in names
        except Exception:
            return False

    @staticmethod
    def _clean_cookie(c):
        out = {k: c[k] for k in ("name", "value", "domain", "path", "secure", "httpOnly") if k in c}
        exp = c.get("expiry", c.get("expirationDate"))
        if exp:
            if isinstance(exp, str) and "/" in exp:
                from datetime import datetime
                dt = datetime.strptime(exp, "%d/%m/%Y %H:%M:%S")
                out["expiry"] = int(dt.timestamp())
            else:
                try:
                    out["expiry"] = int(float(exp))
                except (TypeError, ValueError):
                    pass            # مثلا 'forever' -> كوكي ديال الجلسة بلا expiry
        ss = str(c.get("sameSite", "")).lower()
        mapped = {"strict": "Strict", "lax": "Lax", "none": "None", "no_restriction": "None"}.get(ss)
        if mapped:
            out["sameSite"] = mapped
        return out

    def _logged_in(self):
        try:
            return self.session_ok() and not any(x in self.d.current_url for x in ("/login", "checkpoint"))
        except Exception:
            return False

    def save_session(self):
        """كيحفظ الكوكيز الحاليين (البروفايل ديال Chrome كيحفظ الجلسة بوحدو، وهادي نسخة احتياطية)."""
        try:
            with open(COOKIES_SAVED, "w", encoding="utf-8") as f:
                json.dump(self.d.get_cookies(), f, ensure_ascii=False)
        except Exception as e:
            log(f"⚠️ ما قدرتش نحفظ الكوكيز: {str(e)[:80]}")

    def _add_cookies_file(self, path):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
        except Exception as e:
            log(f"⚠️ ملف الكوكيز {os.path.basename(path)} خايب: {str(e)[:80]}")
            return False
        if isinstance(cookies, dict):
            cookies = cookies.get("cookies", [])
        for c in cookies:
            try:
                self.d.add_cookie(self._clean_cookie(c))
            except Exception as e:
                log(f"⚠️ كوكي مرفوض {c.get('name')}: {str(e)[:80]}")
        self.d.get("https://www.facebook.com/")
        time.sleep(3)
        return self._logged_in()

    def _login_password(self):
        if not (FB_EMAIL and FB_PASS):
            return False
        try:
            self.d.get("https://www.facebook.com/login")
            time.sleep(2)
            self.d.find_element(By.NAME, "email").send_keys(FB_EMAIL)
            box = self.d.find_element(By.NAME, "pass")
            box.send_keys(FB_PASS)
            box.send_keys(Keys.ENTER)
            time.sleep(7)
            return self._logged_in()
        except Exception as e:
            log(f"⚠️ تسجيل الدخول بالإيميل فشل: {str(e)[:100]}")
            return False

    def load_cookies(self):
        """
        1) إلا الجلسة محفوظة فـ chrome_profile كنكملو بلا كوكيز (مرة وحدة تكفي).
        2) وإلا كنحطو الكوكيز من facebook_cookies.json، ومن بعد كنحفظو الجلسة.
        3) وإلا النسخة المحفوظة، وإلا الإيميل/الباسورد (FB_EMAIL / FB_PASS فـ CFG).
        """
        self.d.get("https://www.facebook.com/")
        time.sleep(3)
        if self._logged_in():
            log("✅ الجلسة محفوظة فـ البروفايل (بلا كوكيز)")
            self.save_session()
            return True
        for path in (COOKIES_FILE, COOKIES_SAVED):
            if self._add_cookies_file(path):
                log(f"✅ دخلت بالكوكيز ({os.path.basename(path)}) وتحفظات الجلسة")
                self.save_session()
                return True
        if self._login_password():
            log("✅ دخلت بالإيميل/الباسورد وتحفظات الجلسة")
            self.save_session()
            return True
        log(f"❌ ما لقيت حتى جلسة صالحة. الكوكيز المتوقعين فـ: {COOKIES_FILE}")
        return False

    def recover_session(self, why):
        """إلا الجلسة طاحت: كيعاود الدخول (البروفايل ثم الكوكيز ثم الإيميل/الباسورد) وكيرجع للمنشور."""
        if time.time() < getattr(self, "relogin_after", 0):
            return False
        log(f"🔐 {why} -> كنحاول نرجع الجلسة")
        try:
            self.d.save_screenshot(os.path.join(_BASE_DIR, "session_debug.png"))
        except Exception:
            pass
        try:
            if self.load_cookies() and self.go_to_post():
                self.empty_polls = 0
                log("✅ رجعات الجلسة")
                return True
        except Exception as e:
            log(f"⚠️ recover: {str(e)[:100]}")
        self.relogin_after = time.time() + 300
        log(f"❌ ما قدرتش نرجع الجلسة. جدد facebook_cookies.json (تصويرة: session_debug.png). غادي نعاود من بعد 5 دقايق")
        return False

    def root(self):
        dialogs = self.d.find_elements(By.XPATH, "//div[@role='dialog'][.//div[@role='article']]")
        return dialogs[-1] if dialogs else None

    def expand_replies(self, want=None):
        """كيوسع الردود داخل المتصفح بمكالمة وحدة (أسرع بزاف من الحلقة فـ بايثون)، بحد أقصى 15 ثانية."""
        root = self.root()
        try:
            self.d.set_script_timeout(30)
            return self.d.execute_async_script(JS_EXPAND_ALL, root, want or 0, 15000) or 0
        except Exception as e:
            log(f"⚠️ توسيع الردود: {str(e)[:80]}")
            return 0

    def go_to_post(self):
        log(f"🌐 كنفتح المنشور: {POST_URL}")
        self.d.get(POST_URL)
        time.sleep(5)
        self.close_popups()
        self.wait(lambda: self.d.find_elements(By.XPATH, "//div[@role='article']"), 20)
        self.expand_replies()
        self.d.execute_script(JS_SCROLL_DOWN)
        time.sleep(3)
        return True

    def read_thread(self):
        raw = self.d.execute_script(JS_READ, self.root())
        return parse_thread(raw)

    @staticmethod
    def _download(url, path):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        if len(data) < 2000:
            raise ValueError("الصورة صغيرة بزاف")
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def _enhance(path):
        """كيكبر الصورة وكيحسن التباين والوضوح باش Lens يقراها (خاص Pillow)."""
        try:
            from PIL import Image, ImageFilter, ImageOps
            img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            w, h = img.size
            big = max(w, h)
            if big < 2200:
                f = min(2.5, 2200 / big)
                img = img.resize((int(w * f), int(h * f)), Image.LANCZOS)
            img = ImageOps.autocontrast(img, cutoff=1)
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
            out = os.path.splitext(path)[0] + "_hd.jpg"
            img.save(out, "JPEG", quality=92)
            if out != path:
                try:
                    os.remove(path)
                except OSError:
                    pass
            log(f"✨ تحسنات الصورة: {img.size[0]}x{img.size[1]}")
            return out
        except Exception as e:
            log(f"⚠️ ما تحسنتش الصورة (pip install pillow): {str(e)[:60]}")
            return path

    def fetch_full_image(self, img_url):
        """كيفتح صفحة الصورة فـ تاب جديد وكيجيب أكبر نسخة (ماشي الصورة الصغيرة ديال التعليق)."""
        link = self.d.execute_script(JS_FIND_LINK, img_url)
        if not link:
            return None
        original = self.d.current_window_handle
        opened = False
        try:
            self.d.switch_to.new_window("tab")
            opened = True
            self.d.get(link)
            time.sleep(3)
            el = self.wait(lambda: self.d.execute_script(JS_BIGGEST_IMG), 12)
            if not el:
                return None
            src = el.get_attribute("src")
            w, h = self.d.execute_script("return [arguments[0].naturalWidth, arguments[0].naturalHeight];", el)
            log(f"🔍 نسخة كبيرة: {w}x{h}")
            stamp = int(time.time() * 1000)
            path = os.path.abspath(f"temp_lens_{stamp}.jpg")
            try:
                self._download(src, path)
                return path
            except Exception as e:
                log(f"⚠️ تحميل النسخة الكبيرة فشل ({str(e)[:50]}) -> screenshot")
            path = os.path.abspath(f"temp_lens_{stamp}.png")
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.5)
            el.screenshot(path)
            return path
        except Exception as e:
            log(f"⚠️ فتح الصورة الكبيرة فشل: {str(e)[:100]}")
            return None
        finally:
            try:
                if opened:
                    self.d.close()
                self.d.switch_to.window(original)
            except Exception:
                pass

    def save_image_file(self, img_url):
        """كيحفظ أحسن نسخة ديال الصورة فـ ملف مؤقت ويحسنها."""
        path = self.fetch_full_image(img_url)
        if path:
            return self._enhance(path)

        # احتياط: الصورة الصغيرة ديال التعليق
        stamp = int(time.time() * 1000)
        path = os.path.abspath(f"temp_lens_{stamp}.jpg")
        try:
            self._download(img_url, path)
            return self._enhance(path)
        except Exception as e:
            log(f"⚠️ تحميل مباشر فشل ({str(e)[:60]}) -> screenshot")
        try:
            el = self.d.execute_script(JS_FIND_IMG, img_url)
            if el is None:
                return None
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.5)
            path = os.path.abspath(f"temp_lens_{stamp}.png")
            el.screenshot(path)
            return self._enhance(path)
        except Exception as e:
            log(f"⚠️ screenshot فشل: {str(e)[:100]}")
            return None

    def _newline(self, box=None):
        """سطر جديد فـ مربع الرد (Shift+Enter) بطلب وحد بدل ثلاثة."""
        try:
            if box is not None:
                box.send_keys(Keys.SHIFT, Keys.ENTER)
                return
        except Exception:
            pass
        ActionChains(self.d).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()

    def _fill_box(self, box, lines):
        """كتابة سريعة (insertText بحال لصق)، وإلا ما خدماتش كيرجع لـ send_keys."""
        want = sum(len(l) for l in lines)
        try:
            before = len(box.text or "")
            for n, line in enumerate(lines):
                if line:
                    self.d.execute_script(
                        "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
                        box, line)
                if n < len(lines) - 1:
                    self._newline(box)
            if want == 0 or len(box.text or "") - before >= min(want, 10):
                return
            log("⚠️ الكتابة السريعة ما خدماتش، كنكتب بـ send_keys")
        except Exception:
            pass
        for n, line in enumerate(lines):
            if line:
                box.send_keys(line)
            if n < len(lines) - 1:
                self._newline(box)

    def _clear_box(self, box):
        """كيمسح المربع كامل بما فيه تاغ اسم صاحب التعليق (chip) اللي ما كيبانش فـ .text."""
        try:
            for _ in range(4):
                left = self.d.execute_script("return (arguments[0].textContent || '').trim();", box)
                if not left:
                    return
                self.d.execute_script("arguments[0].focus();", box)
                try:
                    box.send_keys(Keys.CONTROL, "a")
                    box.send_keys(Keys.BACKSPACE)
                except Exception:
                    self.d.execute_script("document.execCommand('selectAll', false, null);"
                                          "document.execCommand('delete', false, null);")
                time.sleep(0.2)
        except Exception:
            pass

    def _attach_image(self, box, image_path):
        """كيرفع صورة لمربع الرد (input[type=file]) وكيتسنى المعاينة."""
        inp = self.d.execute_script(JS_COMPOSER_FILE, box)
        if not inp:
            log("⚠️ ما لقيتش input ديال الصورة فـ مربع الرد")
            return False
        self.d.execute_script(JS_SHOW_FILE_INPUT, inp)
        inp.send_keys(image_path)
        log("📎 تحملات الصورة فـ مربع الرد، كنتسنى المعاينة...")
        if not self.wait(lambda: self.d.execute_script(JS_COMPOSER_PREVIEW, box), 25):
            log("⚠️ المعاينة ما بانتش، كنكمل على كل حال")
        time.sleep(2)
        return True

    def open_reply_box(self, msg):
        """كيفتح مربع الرد ديال هاد التعليق وكيرجع (article, box) ولا None."""
        root = self.root()
        arts = (root.find_elements(By.XPATH, ".//div[@role='article']") if root
                else self.d.find_elements(By.XPATH, "//div[@role='article']"))
        art = None
        if msg.idx < len(arts) and (arts[msg.idx].get_attribute("aria-label") or "").strip() == msg.label:
            art = arts[msg.idx]
        else:
            same = [a for a in arts if (a.get_attribute("aria-label") or "").strip() == msg.label]
            art = same[-1] if same else None
        if art is None:
            return None

        reply_xpath = ".//*[@role='button' and (normalize-space(.)='Reply' or normalize-space(.)='Répondre' or normalize-space(.)='رد')]"
        btn = next((b for b in art.find_elements(By.XPATH, reply_xpath) if b.is_displayed()), None)
        if btn is None:
            return None
        try:
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn)
        except Exception:
            btn = next((b for b in art.find_elements(By.XPATH, reply_xpath) if b.is_displayed()), None)
            if btn is None:
                return None
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn)

        box = self.wait(lambda: self.d.execute_script(
            "const e=document.activeElement; return (e && e.isContentEditable) ? e : null;"), 6, 0.1)
        if not box:
            boxes = [b for b in art.find_elements(By.XPATH, "./following::div[@contenteditable='true'][1]") if b.is_displayed()]
            box = boxes[0] if boxes else None
            if box:
                self.d.execute_script("arguments[0].focus();", box)
        if not box:
            return None
        return art, box

    def post_reply(self, msg, text, image_path=None, prepared=None):
        try:
            pair = prepared
            if pair:
                try:
                    pair[1].is_enabled()
                except Exception:
                    pair = None          # الصفحة تبدلات، كنعاودو نفتحو المربع
            if not pair:
                pair = self.open_reply_box(msg)
            if not pair:
                log("⚠️ ما لقيتش مربع الرد ديال هاد التعليق")
                return False
            art, box = pair
            self._clear_box(box)

            if image_path:
                if not self._attach_image(box, image_path):
                    return False
                try:
                    box.send_keys("")
                except Exception:      # العنصر تبدل بعد الرفع
                    box = self.d.execute_script(
                        "const e=document.activeElement; return (e && e.isContentEditable) ? e : null;")
                    if not box:
                        boxes = [b for b in art.find_elements(By.XPATH, "./following::div[@contenteditable='true'][1]") if b.is_displayed()]
                        box = boxes[0] if boxes else None
                    if not box:
                        return False

            lines = bmp_only(text or "").split("\n")
            self._fill_box(box, lines)
            time.sleep(0.1)
            box.send_keys(Keys.ENTER)
            self.posted = getattr(self, "posted", 0) + 1
            return True
        except Exception as e:
            log(f"❌ خطأ فـ النشر: {str(e)[:120]}")
            return False

    def build_messages(self, thread):
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in thread[-CONTEXT_MESSAGES:]:
            if not m.text:
                continue
            if is_me(m.name):
                msgs.append({"role": "assistant", "content": m.text})
            else:
                msgs.append({"role": "user", "content": f"{m.name}: {strip_choice(m.text)}"})
        return msgs

    def with_ids(self, thread):
        """id = السمية + النص + الصورة + رقم التكرار."""
        run, out = {}, []
        for pos, m in enumerate(thread):
            k = f"{m.name}|{m.text}|{(m.img_url or '').split('?')[0][-40:]}"
            run[k] = run.get(k, 0) + 1
            out.append((f"{k}|{run[k]}", pos, m))
        return out

    def read_context(self):
        """كيقرا الردود + التعليقات الرئيسية (للسياق فقط، باش نلقاو التعليق اللي كيتجاوب عليه)."""
        raw = self.d.execute_script(JS_READ, self.root())
        return parse_thread(raw, include_comments=True)

    def find_target(self, msg):
        """التعليق اللي رد عليه صاحب 'jawb 3lih': أولا تعليق صاحب الأب، وإلا آخر تعليق قبله."""
        parent = parent_name(msg.label)
        try:
            before = [m for m in self.read_context() if m.idx < msg.idx]
        except Exception as e:
            log(f"⚠️ قراءة السياق فشلات: {str(e)[:80]}")
            before = []

        def usable(m):
            if is_me(m.name):
                return False
            if m.img_url:
                return True
            t = (m.text or "").strip()
            return bool(t) and not is_answer_cmd(t) and not is_bare_choice(t)

        if parent and not is_me(parent):
            for m in reversed(before):
                if m.name.strip().lower() == parent.strip().lower() and usable(m):
                    return m
        for m in reversed(before):
            if usable(m):
                return m
        return None

    def answer_image(self, i, n, msg, src, extra, engine):
        """تصويرة (src.img_url): Google Lens كيقرا النص منها، ومن بعد الـ AI كيجاوب (ماشي غير نتيجة البحث)."""
        if self.lens.cooling:
            return
        self.attempts[i] = n + 1
        log("🖼️ صورة -> Google Lens (قراءة النص) ثم AI كيجاوب")
        try:
            prepared = self.open_reply_box(msg)     # نحضرو مربع الرد قبل Lens
        except Exception:
            prepared = None
        path = self.save_image_file(src.img_url)
        if not path:
            log(f"⚠️ ما قدرتش نحمل الصورة ({n + 1}/{MAX_ATTEMPTS})")
            return
        try:
            lens_text = self.lens.read_image(path, src.img_url)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if not lens_text:
            log(f"⚠️ Google Lens ما قراش الصورة ({n + 1}/{MAX_ATTEMPTS})")
            return

        prompt = (
            "هادي تصويرة صيفطها شخص (ممكن تكون امتحان ولا تمرين ولا سؤال). "
            "هادا هو النص اللي استخرجو Google Lens منها (ممكن يكون فيه نصوص زايدة ديال الموقع، تجاهلها):\n"
            "-----\n" + lens_text[:6000] + "\n-----\n"
            + (f"طلب الشخص: {extra}\n" if extra else "")
            + "قرا النص مزيان وجاوب على كل الأسئلة والتمارين اللي فـ التصويرة بشكل كامل ومنظم، "
              "بنفس لغة الأسئلة (إلا كانت بالفرنسية جاوب بالفرنسية). "
              "إلا كانت التصويرة ماشي سؤال، شرح ليه شنو فيها."
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        t_ai = time.time()
        answer = self.ai.ask(messages, engine)
        log(f"⏱ الجواب: {time.time() - t_ai:.1f}s")
        if answer:
            answer = clean_answer(sanitize_identity(answer), msg.name)
        else:
            ov = GoogleLens.overview_answer(lens_text)      # احتياط: جواب Google إلا الـ AI ما جاوبش
            if ov:
                answer = ov
        if not answer:
            log(f"⚠️ ما قدرتش نجاوب على الصورة ({n + 1}/{MAX_ATTEMPTS})")
            if n + 1 >= MAX_ATTEMPTS:
                if self.post_reply(msg, "ما قدرتش نفهم الصورة مزيان، عاود صيفطها أوضح."):
                    self.done_stable.add(i)
            return
        answer = bmp_only(answer)[:6000]
        log(f"🤖 {answer[:120]}")
        if self.post_reply(msg, answer, prepared=prepared):
            self.done_stable.add(i)
            log("✅ تنشر")

    def answer_one(self, i, ctx, msg):
        log(f"📩 {msg.name}: {msg.text} {'[تصويرة]' if msg.img_url else ''}")
        n = self.attempts.get(i, 0)
        if n >= MAX_ATTEMPTS:
            self.done_stable.add(i)
            return

        text_clean = (msg.text or "").strip()
        parts = text_clean.split()
        choice = parts[0] if parts else ""
        engine = "gemini" if choice in ("2", "٢") else "deepseek"
        cmd = (not msg.img_url) and (is_answer_cmd(text_clean) or is_bare_choice(text_clean))

        # ---------- رد فيه صورة ----------
        if msg.img_url:
            extra = strip_choice(text_clean)
            if is_answer_cmd(extra) or is_bare_choice(extra):
                extra = ""
            self.answer_image(i, n, msg, msg, extra, engine)
            return

        # ---------- 3 + وصف = إنشاء صورة ----------
        if choice in ("3", "٣"):
            prompt_img = text_clean.split(None, 1)[1].strip() if len(text_clean.split(None, 1)) > 1 else ""
            self.attempts[i] = n + 1
            if not prompt_img:
                if self.post_reply(msg, "كتب الوصف بعد 3، مثلا: 3 صورة ديال مدينة فـ المستقبل"):
                    self.done_stable.add(i)
                return
            log(f"🎨 كنولد صورة: {prompt_img}")
            img_path = generate_image(prompt_img)
            if not img_path:
                log(f"⚠️ ما تولداتش الصورة ({n + 1}/{MAX_ATTEMPTS})")
                return
            try:
                ok = self.post_reply(msg, "", image_path=img_path)
            finally:
                try:
                    os.remove(img_path)
                except OSError:
                    pass
            if ok:
                self.done_stable.add(i)
                log("✅ الصورة تنشرات")
            else:
                log("⚠️ ما قدرتش ننشر الصورة")
            return

        # ---------- "jawb 3lih" (ولا 1 / 2 بوحدها): جاوب على التعليق اللي رد عليه ----------
        src = msg
        if cmd:
            self.attempts[i] = n + 1
            src = self.find_target(msg)
            if src is None:
                log("⚠️ ما لقيتش التعليق اللي بغا يتجاوب عليه")
                if self.post_reply(msg, "ما لقيتش السؤال اللي بغيتي نجاوب عليه، كتبو هنا ولا صيفط تصويرة."):
                    self.done_stable.add(i)
                return
            log(f"🎯 كنجاوب على تعليق {src.name}: {(src.text or '')[:60]} {'[تصويرة]' if src.img_url else ''}")
            if choice not in ("1", "2", "١", "٢"):
                src_first = (src.text or "").strip().split()[:1]
                if src_first and src_first[0] in ("2", "٢"):
                    engine = "gemini"
            if src.img_url:
                self.answer_image(i, n, msg, src, "", engine)
                return

        question = strip_choice(src.text or "")
        if not re.search(r"\w", question):
            log("⏭ ما فيه نص نجاوب عليه")
            self.done_stable.add(i)
            return

        self.attempts[i] = n + 1

        # ---------- شكون نتا؟ -> muxe ai ----------
        if is_identity_q(question):
            if self.post_reply(msg, identity_answer(question)):
                self.done_stable.add(i)
                log("✅ تنشر (هوية muxe ai)")
            return

        # ---------- أي سؤال -> الـ AI كيجاوب ----------
        ctx_t = ctx if not cmd else [m for m in ctx if m.idx < src.idx] + [src]
        log(f"📚 كنجاوب بـ {'Gemini' if engine == 'gemini' else 'DeepSeek'}")
        t_ai = time.time()
        fut = POOL.submit(self.ai.ask, self.build_messages(ctx_t), engine)
        prepared = None
        try:
            prepared = self.open_reply_box(msg)      # كنحضرو مربع الرد وAI كيجاوب
        except Exception:
            prepared = None
        answer = fut.result()
        log(f"⏱ الجواب: {time.time() - t_ai:.1f}s")
        if not answer:
            log(f"⚠️ ما جاوبش ({n + 1}/{MAX_ATTEMPTS})")
            return
        answer = clean_answer(sanitize_identity(answer), msg.name)
        log(f"🤖 {answer}")

        t_post = time.time()
        if not self.post_reply(msg, answer, prepared=prepared):
            return
        self.done_stable.add(i)
        log(f"✅ تنشر ({time.time() - t_post:.1f}s)")

    def step(self):
        thread = self.read_thread()

        if not thread:
            self.expand_replies()
            self.wait(lambda: self.read_thread(), 8)
            thread = self.read_thread()
        log(f"📊 قريت {len(thread)} رد")
        if not thread:
            self.empty_polls += 1
            return
        self.empty_polls = 0
        items = self.with_ids(thread)
        self.last_len = len(thread)
        self.posted_at_read = getattr(self, "posted", 0)
        last = thread[-1]
        log(f"🔎 آخر رد: {last.name}: {last.text[:60]} {'[صورة]' if last.img_url else ''}")

        # أول قراءة: كل الردود الموجودة كتعتبر قديمة
        if not self.done_stable:
            for i, _, m in items:
                self.done_stable.add(i)
            log(f"👁 بداية المراقبة: {len(thread)} ردود قديمة.")
            return

        for i, _, m in items:
            if is_me(m.name):
                self.done_stable.add(i)

        new = [(i, p, m) for i, p, m in items if i not in self.done_stable]
        if not new:
            return
        log(f"👁 ردود جداد: {len(new)}")
        for i, pos, m in new[:3]:
            self.answer_one(i, thread[:pos + 1], m)

    def has_pending(self):
        """واش كاين ردود باقيين ما تجاوبوش (فشلو ولا ما تحاولوش)."""
        try:
            items = self.with_ids(self.read_thread())
        except Exception:
            return False
        return any(i not in self.done_stable and not is_me(m.name)
                   and self.attempts.get(i, 0) < MAX_ATTEMPTS for i, _, m in items)

    def start(self):
        for f in glob.glob("temp_lens_*") + glob.glob("temp_gen_*"):
            try:
                os.remove(f)
            except OSError:
                pass
        self.start_browser()
        if not self.load_cookies():
            raise SystemExit("❌ الكوكيز ما خدماتش. جدد facebook_cookies.json ولا حط FB_EMAIL / FB_PASS فـ CFG.")
        if not self.go_to_post():
            raise SystemExit("❌ ما قدرتش نوصل للمنشور")
        log("👀 كنراقب الردود (أي سؤال = جواب، 1 = DeepSeek، 2 = Gemini، 3 = إنشاء صورة، jawb 3lih = جاوب على التعليق، تصويرة = Lens + AI)...")

    def has_new(self):
        """واش كاين رد جديد فـ الصفحة اللي مفتوحة دابا (بلا refresh)؟"""
        items = self.with_ids(self.read_thread())
        return any(i not in self.done_stable and not is_me(m.name) for i, _, m in items)

    @staticmethod
    def _delta(new, old):
        """أكبر زيادة فـ الأرقام العادية (ماشي K/M)، و0 إلا ما كاينش زيادة."""
        if not new or not old or len(new) != len(old):
            return 0
        best = 0
        for a, b in zip(new, old):
            if re.search(r"[KkMm]", a) or re.search(r"[KkMm]", b):
                continue
            try:
                best = max(best, int(re.sub(r"\D", "", a)) - int(re.sub(r"\D", "", b)))
            except ValueError:
                continue
        return best

    @staticmethod
    def is_dead_session(e):
        s = str(e).lower()
        return any(x in s for x in ("invalid session id", "no such window", "chrome not reachable",
                                    "session deleted", "target window already closed",
                                    "disconnected", "not connected to devtools", "failed to establish"))

    def restart_main(self, why):
        """يعاود يشغل المتصفح الرئيسي، يدخل بالكوكيز، ويرجع للمنشور."""
        log(f"🔁 المتصفح الرئيسي طاح ({why[:60]}) -> كنعاود نشغلو")
        self.quit_browser()
        time.sleep(3)
        try:
            self.start_browser()
            if not self.load_cookies() or not self.go_to_post():
                log("❌ ما قدرتش نرجع المتصفح، غادي نعاود فـ الدورة الجاية")
                return False
            self.empty_polls = 0
            log("✅ رجع المتصفح الرئيسي")
            return True
        except Exception as e:
            log(f"❌ فشل إعادة التشغيل: {str(e)[:120]}")
            return False

    def cycle(self, live=False, new_count=None):
        """دورة فـ المتصفح اللي فيه الحساب. live=True: كيجرب يقرا بلا refresh أولا."""
        try:
            try:
                if "facebook.com" not in (self.d.current_url or ""):
                    self.go_to_post()          # المتصفح تحرك لصفحة أخرى (Lens...)
            except Exception:
                pass
            if not self.session_ok():
                self.recover_session("الجلسة طاحت")
            if live:
                try:
                    if self.has_new():
                        log("⚡ لقيت الرد بلا refresh")
                        self.step()
                        return
                except Exception:
                    pass
            t0 = time.time()
            self.d.refresh()
            self.wait(lambda: self.d.find_elements(By.XPATH, "//div[@role='article']"), 20)
            t1 = time.time()
            self.close_popups()
            want = None
            if new_count and getattr(self, "last_len", 0):
                want = (self.last_len + (getattr(self, "posted", 0) - getattr(self, "posted_at_read", 0))
                        + new_count)
            self.expand_replies(want)
            self.d.execute_script(JS_SCROLL_DOWN)
            time.sleep(0.3)
            self.expand_replies(want)
            log(f"⏱ تحميل الصفحة {t1 - t0:.1f}s | توسيع الردود {time.time() - t1:.1f}s")
            self.step()
            if self.empty_polls >= 2:
                self.recover_session("قريت 0 رد مرتين")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"⚠️ {str(e)[:150]}")
            if self.is_dead_session(e):
                self.restart_main(str(e))
            else:
                try:
                    self.go_to_post()
                except Exception:
                    pass

    def main_signature(self):
        """كيقرا عدد الردود من المتصفح الرئيسي (الحساب) مباشرة، ولا None."""
        try:
            cur = self.d.current_url or ""
            if "facebook.com" not in cur or "login" in cur or "checkpoint" in cur:
                self.d.get(POST_URL)
                time.sleep(2)
            else:
                self.d.refresh()
            self.wait(lambda: self.d.find_elements(By.XPATH, "//div[@role='article']"), 10, 0.2)
            text = self.d.find_element(By.TAG_NAME, "body").text
            return self._sig_from_text(text)
        except Exception as e:
            log(f"⚠️ قراءة العدد من الحساب: {str(e)[:80]}")
            return None

    def _detect(self):
        """كيرجع بصمة الردود بالطريقة المختارة (FAST_DETECT)."""
        return self.main_signature() if FAST_DETECT else self.watch_signature()

    def run(self):
        self.start()
        self.cycle()      # قراءة أولى: كل الردود الموجودة دابا كتتحسب قديمة

        if not WATCH_ENABLED:
            while True:
                self.cycle()
                time.sleep(REFRESH_INTERVAL)

        try:
            self.start_watcher()
        except Exception as e:
            self.w = None
            log(f"⚠️ المراقب ما قدرش يبدا، غادي نعاود نحاول فـ الحلقة: {str(e).splitlines()[0][:100]}")
        self.sig = self._detect()
        log(f"🕵️ البصمة الأولى (بلا حساب): {self.sig}")
        if self.sig is None:
            log("⚠️ المراقب ما قدرش يقرا العدد دابا، كنعاود نحاول. الحساب ما غاديش يدير refresh.")
        last_cycle = time.time()
        bad = 0

        last_poll = time.time()
        while True:
            left = REFRESH_INTERVAL - (time.time() - last_poll)
            if left > 0:
                time.sleep(left)
            last_poll = time.time()
            sig = self._detect()

            reason, live, new_count = None, False, None
            if sig is None:
                bad += 1
                if bad % 5 == 0:
                    log("🔄 كنعاود نفتح المراقب...")
                    try:
                        if self.w:
                            self.w.quit()
                    except Exception:
                        pass
                    self.w = None
            else:
                bad = 0
                if self.sig is None:
                    self.sig = sig           # أول قراءة ناجحة = غير بصمة مرجعية
                    log(f"🕵️ البصمة المرجعية: {sig}")
                elif sig != self.sig:
                    d = self._delta(sig, self.sig)
                    if d > 0:
                        reason, live = f"تبدل العدد: {self.sig} -> {sig}", True
                        new_count = min(d, 3)
                    else:
                        log(f"📊 تبدل الشكل بلا تعليق جديد، كنحدّث المرجع: {self.sig} -> {sig}")
                        self.sig = sig
            if not reason and HEARTBEAT_SECONDS and time.time() - last_cycle > HEARTBEAT_SECONDS:
                reason = "دورة احتياط (heartbeat)"
            if not reason:
                continue

            log(f"⚡ {reason}")
            t0 = time.time()
            p0 = getattr(self, "posted", 0)
            self.cycle(live=live, new_count=new_count)
            for _ in range(2):
                if not self.has_pending():
                    break
                log("🔁 كاين ردود ما تجاوبوش، كنعاود")
                self.cycle()
            last_cycle = time.time()
            log(f"⏱ الدورة دامت {last_cycle - t0:.1f} ثانية")

            # كنتسناو حتى يبانو الردود ديال البوت فـ العدد، باش ما يتحسبوش كرد جديد
            k = getattr(self, "posted", 0) - p0
            cur = self._detect()
            if k > 0 and sig is not None:
                target = sig_total(sig) + k
                deadline = time.time() + 10     # ما نوقفوش الكشف بزاف
                while cur is not None and sig_total(cur) < target and time.time() < deadline:
                    time.sleep(2)
                    cur = self._detect()
            if cur is not None:
                if k > 0 and sig is not None and sig_total(cur) > sig_total(sig) + k:
                    self.sig = sig           # كاين رد جديد زيادة: الدورة الجاية كتلقاه
                else:
                    self.sig = cur


def single_instance():
    """ما كيسمحش بجوج نسخ من البوت فنفس الوقت (كيتصادمو على نفس حساب فيسبوك وبروفايل Chrome)."""
    import fcntl
    lock = open(os.path.join(_BASE_DIR, "fb_bot.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("❌ البوت شاغل ديجا فنسخة أخرى. وقف النسخة الأخرى (systemctl stop fbbot أو pkill -f fb_bot.py) وعاود.")
        sys.exit(1)
    return lock


if __name__ == "__main__":
    _lock = single_instance()
    bot = Bot()
    try:
        bot.run()
    except KeyboardInterrupt:
        log("⏹️ توقف")
    finally:
        bot.quit_browser()
