
// كيوصل لمنشور "بدأ محادثة" بالضغط خطوة خطوة:
// ☰ (القائمة) ← Groups ← Chat ← منشور "بدأ محادثة" ← صفحة التعليقات (فين كيخدم watch.js)
// Java كيناديها كل ~1.2 ثانية: window.__navStep() كترجع 'wait' | 'done' | 'fail:<الشاشة>'
(function () {
  var N = window.__nav = window.__nav || { tapAt: 0, tries: {} };

  // ---- كلمات (إنجليزي / عربي / فرنسي) ----
  var GROUPS_WORDS = ['Groups', 'المجموعات', 'Groupes'];
  var GROUPS_PAGE = ['Your groups', 'Create a group', 'Most visited', 'مجموعاتك', 'إنشاء مجموعة', 'Vos groupes', 'Créer un groupe'];
  var MENU_PAGE = ['Settings & privacy', 'Settings and privacy', 'الإعدادات والخصوصية', 'Paramètres et confidentialité'];
  var GROUP_NAME = ['Chat'];            // اسم المجموعة
  var POST_RE = /بدأ\s*محاد/;           // نص المنشور (مرن: محادثة / محادتة)
  var PROFILE_NAME = 'Mostafa Hachmi';  // الحساب لي كنختارو فصفحة "اختيار الحساب"
  var CHOOSER_RE = /Use another profile|Create new account|استخدام ملف شخصي آخر|إنشاء حساب جديد|Utiliser un autre profil|Créer un nouveau compte/i;
  var MENU_LABELS = ['Menu', 'Main menu', 'القائمة', 'القائمة الرئيسية', 'Menu principal'];

  function clean(s) {
    return String(s || '').replace(/[\uE000-\uF8FF\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF\uFE0F]/g, '').replace(/\s+/g, ' ').trim();
  }
  function visible(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
  }
  function pageText() { return clean(document.body ? document.body.innerText : ''); }
  function hasAny(words) {
    var t = pageText();
    for (var i = 0; i < words.length; i++) if (t.indexOf(words[i]) !== -1) return true;
    return false;
  }

  // أصغر عنصر ظاهر نصو كيطابق (exact = مطابقة تامة، وإلا كيحتوي)
  function findText(words, exact, minTop) {
    var els = document.querySelectorAll('div, span, a, b, h1, h2, h3');
    var best = null, bestArea = 1e12;
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var t = clean(el.innerText || el.textContent);
      if (!t || t.length > 60) continue;
      var ok = false;
      if (words instanceof RegExp) {
        ok = words.test(t);
      } else {
        for (var j = 0; j < words.length; j++) {
          if (exact ? t === words[j] : t.indexOf(words[j]) !== -1) { ok = true; break; }
        }
      }
      if (!ok) continue;
      var r = el.getBoundingClientRect();
      if (minTop && r.top < minTop) continue;
      var area = r.width * r.height;
      if (area < bestArea) { bestArea = area; best = el; }
    }
    return best;
  }

  // زر ☰: aria-label، وإلا أقصى زر صغير فاليمين فوق
  function findMenuBtn() {
    for (var i = 0; i < MENU_LABELS.length; i++) {
      var l = document.querySelectorAll('[aria-label="' + MENU_LABELS[i] + '"]');
      for (var j = 0; j < l.length; j++) if (visible(l[j])) return l[j];
    }
    var c = document.querySelectorAll('[role="button"], [role="link"], a, button, div[tabindex]');
    var best = null, bestLeft = -1;
    for (var k = 0; k < c.length; k++) {
      var r = c[k].getBoundingClientRect();
      if (r.width < 20 || r.height < 20 || r.width > 60 || r.height > 60) continue;
      if (r.top < 0 || r.top > 120) continue;
      if (r.left < window.innerWidth * 0.75) continue;
      if (r.left > bestLeft) { bestLeft = r.left; best = c[k]; }
    }
    return best;
  }

  function tapEl(el) {
    var r = el.getBoundingClientRect();
    if (r.top < 90 || r.bottom > window.innerHeight - 20) {
      try { el.scrollIntoView({ block: 'center' }); } catch (e) {}
      r = el.getBoundingClientRect();
    }
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    try { AndroidBridgeJS.nativeTap(x, y); } catch (e) {}
  }

  // كل شاشة عندها 4 محاولات ضغط كحد أقصى
  function act(screen, el) {
    if (!el) return 'wait';
    N.tries[screen] = (N.tries[screen] || 0) + 1;
    if (N.tries[screen] > 4) return 'fail:' + screen;
    tapEl(el);
    N.tapAt = Date.now();
    N.tapScreen = screen;
    return 'wait';
  }

  // فين حنا؟
  function detect() {
    var url = location.href;
    if (CHOOSER_RE.test(pageText())) return 'login'; // صفحة اختيار الحساب (Use another profile ...)
    if (/\/posts\/|story_fbid|permalink/.test(url)) return 'post';
    if (/\/groups\/[^\/?#]+/.test(url) && !/\/groups\/(feed|discover|joins|create|\?|$)/.test(url)) return 'group';
    if (findText(POST_RE, false, 100)) return 'group';
    if (hasAny(GROUPS_PAGE)) return 'groups';
    if (hasAny(MENU_PAGE)) return 'menu';
    var p = location.pathname;
    if (p === '/' || /^\/home\.php/.test(p)) return 'home';
    return 'other';
  }

  // رقم التعليقات (278): أقرب رقم لوسط الشاشة تحت المنشور
  function findCommentCount(post) {
    var els = document.querySelectorAll('div, span, a, button, [role="button"]');
    var best = null, bestD = 1e9, pt = post.getBoundingClientRect().top, mid = window.innerWidth / 2;
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var t = clean(el.innerText || el.textContent);
      if (!/^\d+[KkMm]?$/.test(t)) continue;
      var r = el.getBoundingClientRect();
      if (r.top < pt || r.top > pt + 400) continue;
      var d = Math.abs(r.left + r.width / 2 - mid);
      if (d < bestD) { bestD = d; best = el; }
    }
    return best;
  }

  // نافذة "You're out of data..." (inwi): ضغط على CONTINUE
  function dismissDataPopup() {
    var txt = pageText();
    if (!/out of data|can still use Facebook|inwi/i.test(txt)) return false;
    var els = document.querySelectorAll('div, span, a, button, [role="button"]');
    var best = null, bestA = 1e12;
    for (var i = 0; i < els.length; i++) {
      if (!visible(els[i])) continue;
      var t = clean(els[i].innerText || els[i].textContent);
      if (!/^(continue|continuer|متابعة)$/i.test(t)) continue;
      var r = els[i].getBoundingClientRect();
      if (r.width * r.height < bestA) { bestA = r.width * r.height; best = els[i]; }
    }
    if (!best) return false;
    tapEl(best);
    return true;
  }

  window.__navStep = function () {
    try {
      if (dismissDataPopup()) return 'wait';
      var sc = detect();
      if (sc === 'post') return 'done';

      // كنستناو غير ملي نضغطو ولا زالت نفس الشاشة (بلا وقت ثابت)
      if (N.tapScreen && sc === N.tapScreen && Date.now() - N.tapAt < 1800) return 'wait';
      N.tapScreen = null;

      if (sc === 'group') {
        var post = findText(POST_RE, false, 100);
        if (!post) { try { window.scrollBy(0, 350); } catch (e) {} return 'wait'; }
        var n = N.tries.group || 0;
        if (n === 1) {                       // المحاولة 2: رقم التعليقات
          var cnt = findCommentCount(post);
          if (cnt) return act('group', cnt);
        } else if (n === 2) {                // المحاولة 3: خانة "Comment as ..."
          var ci = null, cs = document.querySelectorAll('[aria-label*="omment"], [aria-label*="تعليق"], input, textarea');
          for (var i = 0; i < cs.length; i++) {
            if (visible(cs[i]) && cs[i].getBoundingClientRect().top > post.getBoundingClientRect().top) { ci = cs[i]; break; }
          }
          if (ci) return act('group', ci);
        }
        return act('group', post);
      }
      if (sc === 'login') return act('login', findText([PROFILE_NAME], true, 100));
      if (sc === 'groups') return act('groups', findText(GROUP_NAME, true, 120));
      if (sc === 'menu') return act('menu', findText(GROUPS_WORDS, true, 100));
      if (sc === 'home') return act('home', findMenuBtn());
      return 'wait';
    } catch (e) {
      return 'wait';
    }
  };
})();
