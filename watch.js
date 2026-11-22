
(function () {
  if (window.__fbWatcherStarted) return;
  window.__fbWatcherStarted = true;

  var MY_NAME = 'Mostafa Hachmi';
  // الحسابات اللي كيصيفطو التعليقات (البوت): أي واحد فيهم كنعتبروه "ديالنا"
  var OWN_NAMES = ['Mostafa Hachmi', 'Tirbo Mustafa'];
  function isOwn(author) {
    for (var i = 0; i < OWN_NAMES.length; i++) if (String(author).indexOf(OWN_NAMES[i]) === 0) return true;
    return false;
  }
  // كيحيد المنشن (اسم حسابنا) من بداية رد الكاتب
  function stripOwn(body) {
    for (var i = 0; i < OWN_NAMES.length; i++) {
      if (body.indexOf(OWN_NAMES[i]) === 0 && body.slice(OWN_NAMES[i].length).trim()) return body.slice(OWN_NAMES[i].length).trim();
    }
    return body;
  }
  var ANCHOR_TEXT = 'بدأ';
  var UI = /^(auteur|membre|author|member|see translation|like|reply|most relevant|newest|replies|just now|إعجاب|رد|\d+\s*(h|d|m|w|min|hr)|view previous replies.*)$/i;
  var SEE_MORE = /^(…|\.\.\.)?\s*(see more|عرض المزيد|voir plus|المزيد)$/i;
  var SORT_WORDS = ['most relevant', 'le plus pertinent', 'الأكثر ملاءمة', 'الأكثر صلة'];
  var NEWEST_WORDS = ['newest', 'plus récents', 'الأحدث'];
  var OK_WORDS = ['ok', 'حسنا', 'موافق'];
  var SORT_COOLDOWN = 30000;

  var seen = {};
  var missTicks = 0;
  var anchorMiss = 0;
  var REPLY_WORDS = ['Reply', 'رد', 'Répondre'];
  var ticking = false;

  function norm(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }
  function sameText(body, sent) {
    var b = norm(body);
    if (!b || !sent) return false;
    return b === sent || b.indexOf(sent) !== -1 || sent.indexOf(b) !== -1;
  }

  // كينزل لآخر الصفحة وآخر لائحة قابلة للتمرير (باش نشوفو آخر تعليق)
  function scrollBottom() {
    try { window.scrollTo(0, document.documentElement.scrollHeight || document.body.scrollHeight); } catch (e) {}
    var a = document.querySelectorAll('*');
    for (var i = 0; i < a.length; i++) {
      var e = a[i];
      if (e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 100) {
        var oy = '';
        try { oy = getComputedStyle(e).overflowY; } catch (x) {}
        if (oy === 'auto' || oy === 'scroll') e.scrollTop = e.scrollHeight;
      }
    }
  }
  var baselineDone = false;
  var sorting = false;
  var lastSort = 0;

  var log = function (m) { AndroidBridgeJS.logToChat(m); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function visible(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function lines(el) {
    return (el.innerText || '').split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function firstLine(el) {
    return ((el.innerText || '').split('\n')[0] || '').trim().toLowerCase();
  }

  function hash(s) {
    var x = 5381;
    for (var i = 0; i < s.length; i++) x = ((x << 5) + x + s.charCodeAt(i)) | 0;
    return 'k' + (x >>> 0).toString(36);
  }

  function fire(el, type, x, y) {
    var o = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
    try {
      if (type.indexOf('pointer') === 0 && window.PointerEvent) {
        el.dispatchEvent(new PointerEvent(type, Object.assign({ pointerType: 'touch', isPrimary: true }, o)));
      } else if (type.indexOf('touch') === 0) {
        el.dispatchEvent(new Event(type, { bubbles: true, cancelable: true }));
      } else {
        el.dispatchEvent(new MouseEvent(type, o));
      }
    } catch (e) {}
  }

  // ضغطة على العنصر اللي ظاهر فعلا فهاد الإحداثيات
  function tapAt(x, y) {
    try {
      if (window.AndroidBridgeJS && typeof AndroidBridgeJS.nativeTap !== 'undefined') {
        AndroidBridgeJS.nativeTap(x, y);
        return;
      }
    } catch (e) {}
    var target = document.elementFromPoint(x, y);
    if (!target) return;
    ['pointerdown', 'touchstart', 'mousedown', 'pointerup', 'touchend', 'mouseup', 'click'].forEach(function (t) {
      fire(target, t, x, y);
    });
  }

  // ضغطة حقيقية بالإصبع (من Java) لأن فيسبوك كيتجاهل الأحداث المصطنعة
  function tap(el) {
    var r = el.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) {
      try { el.scrollIntoView({ block: 'center' }); } catch (e) {}
      r = el.getBoundingClientRect();
    }
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    try {
      if (window.AndroidBridgeJS && typeof AndroidBridgeJS.nativeTap !== 'undefined') {
        AndroidBridgeJS.nativeTap(x, y);
        return;
      }
    } catch (e) {}
    var target = document.elementFromPoint(x, y) || el;
    ['pointerdown', 'touchstart', 'mousedown', 'pointerup', 'touchend', 'mouseup', 'click'].forEach(function (t) {
      fire(target, t, x, y);
    });
  }

  // أصغر عنصر ظاهر أول سطر ديالو كيطابق كلمة
  function findWithText(words, exact) {
    var bestE = null, areaE = 1e12, bestP = null, areaP = 1e12;
    var els = document.querySelectorAll('div, span, button, a, label, [role="button"], [role="radio"], [role="menuitem"]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var t = firstLine(el);
      if (!t || t.length > 40) continue;
      var isExact = false, isPart = false;
      for (var w = 0; w < words.length; w++) {
        if (t === words[w]) isExact = true;
        else if (!exact && t.indexOf(words[w]) !== -1) isPart = true;
      }
      if (!isExact && !isPart) continue;
      var r = el.getBoundingClientRect();
      var area = r.width * r.height;
      if (isExact && area < areaE) { areaE = area; bestE = el; }
      if (area < areaP) { areaP = area; bestP = el; }
    }
    return bestE || bestP; // الأفضلية للنص المطابق تماما
  }

  // كيستنى حتى يظهر العنصر، ولا يسالي بعد ms
  function waitFor(fn, ms) {
    var end = Date.now() + ms;
    return new Promise(function (resolve) {
      (function poll() {
        var r = fn();
        if (r) return resolve(r);
        if (Date.now() > end) return resolve(null);
        setTimeout(poll, 300);
      })();
    });
  }

  // الصف الكامل ديال الخيار (ماشي غير النص الصغير)
  function rowOf(el) {
    var first = firstLine(el);
    var cur = el;
    for (var i = 0; i < 6 && cur.parentElement; i++) {
      var p = cur.parentElement;
      if (!visible(p) || firstLine(p) !== first) break;
      if (p.getBoundingClientRect().height > 200) break;
      cur = p;
    }
    return cur;
  }

  function findAny(words) { return findWithText(words, true) || findWithText(words, false); }

  // Most relevant -> Newest -> OK (مع تحقق بعد كل خطوة)
  async function sortNewest() {
    for (var attempt = 0; attempt < 3; attempt++) {
      var sheetOpen = !!findWithText(OK_WORDS, true);

      if (!sheetOpen) {
        // التعليقات مرتبة ديجا Newest؟
        if (!findWithText(SORT_WORDS, true) && findWithText(NEWEST_WORDS, true)) return true;

        var btn = await waitFor(function () { return findWithText(SORT_WORDS, true) || findWithText(SORT_WORDS, false); }, 4000);
        if (!btn) { log('⚠️ ما لقيت زر Most relevant'); return false; }
        tap(rowOf(btn));
        await sleep(1500);
      }

      var opt = await waitFor(function () { return findWithText(OK_WORDS, true) ? findAny(NEWEST_WORDS) : null; }, 5000);
      if (!opt) { log('⚠️ القائمة ما ظهرتش (محاولة ' + (attempt + 1) + ')'); continue; }
      var row = rowOf(opt);
      tap(row);                       // ضغطة على الصف
      await sleep(500);
      var rr = row.getBoundingClientRect();
      tapAt(window.innerWidth - 24, rr.top + rr.height / 2); // ضغطة على الدائرة (radio) فاليمين
      await sleep(700);

      for (var k = 0; k < 3; k++) {
        var ok = await waitFor(function () { return findWithText(OK_WORDS, true); }, 2500);
        if (!ok) break; // القائمة تسدات
        tap(rowOf(ok));
        await sleep(1500);
      }
      await sleep(1500);

      if (!findWithText(SORT_WORDS, true) && findWithText(NEWEST_WORDS, true)) return true;
      log('⚠️ الترتيب ما تبدلش، كنعاود (' + (attempt + 1) + ')');
    }
    return false;
  }

  // تعليق "بدأ" ديال صاحب المنشور
  function findAnchor() {
    var old = document.querySelector('[data-bot-anchor="1"]');
    if (old && visible(old)) return old;

    var best = null, bestLen = 1e9;
    var els = document.querySelectorAll('div');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var L = lines(el);
      if (L.length < 2 || L.length > 6) continue;
      if (L[0].indexOf(MY_NAME) !== 0) continue;
      if (L.indexOf(ANCHOR_TEXT) === -1) continue;
      if (el.innerText.length < bestLen) {
        best = el;
        bestLen = el.innerText.length;
      }
    }
    if (best) best.setAttribute('data-bot-anchor', '1');
    return best;
  }

  // كيحيد رموز الأيقونات (Private Use) والرموز الخفية: فيسبوك كيستعملها فأزرار مثل GIF و@ والإيموجي
  function clean(s) {
    return s.replace(/[\uE000-\uF8FF\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF\uFE0F]/g, '').trim();
  }

  function parse(el) {
    var raw = (el.innerText || '');
    if (raw.length > 6000) return null;
    var L = raw.split('\n').map(function (s) { return clean(s.trim()); }).filter(Boolean);
    if (L.length < 2 || L.length > 80) return null;
    var author = L[0];
    // الأسطر الأصلية (بما فيها الفراغات بين الفقرات) باش الرد يبقى بنفس التنسيق
    var R = raw.split('\n').map(function (s) { return clean(s.trim()); });
    var ai = R.indexOf(author);
    if (UI.test(author) || /^view previous/i.test(author)) return null;
    if (!/[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF\u0590-\u06FF\u0750-\u077F]/.test(author)) return null; // الاسم خاصو يحتوي على حروف (كيحيد أيقونات الكتابة)
    var bodyLines = R.slice(ai + 1).filter(function (l) { return !UI.test(l); });
    var body = bodyLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
    if (!body) return null;
    return { author: author, body: body, key: hash(author + '|' + body) };
  }

  // واش سطر الاسم (author) فعلا بولد/رابط؟ كيفرق بين فقاعة التعليق الحقيقية وغلاف النص الداخلي
  function authorIsBold(el, author) {
    try {
      var all = el.querySelectorAll('*');
      for (var i = 0; i < all.length && i < 400; i++) {
        var n = all[i];
        if (n.children.length > 1) continue;
        var t = clean((n.innerText || n.textContent || '').trim());
        if (t !== author) continue;
        var w = parseInt(getComputedStyle(n).fontWeight, 10) || 400;
        if (w >= 600 || n.tagName === 'A' || n.getAttribute('role') === 'link') return true;
        var p = n.parentElement;
        if (p && (p.tagName === 'A' || p.getAttribute('role') === 'link' || (parseInt(getComputedStyle(p).fontWeight, 10) || 400) >= 600)) return true;
      }
    } catch (e) {}
    return false;
  }

  // كل التعليقات المرئية، ونحتفظ بالأعمق فقط
  function candidates() {
    var els = document.querySelectorAll('div');
    var list = [];
    for (var i = 0; i < els.length; i++) {
      if (!visible(els[i])) continue;
      var c = parse(els[i]);
      if (c) list.push({ el: els[i], c: c, strong: authorIsBold(els[i], c.author) });
    }
    return list.filter(function (a) {
      for (var j = 0; j < list.length; j++) {
        var b = list[j];
        if (b === a) continue;
        // a غلاف ديال b: كنحيدو a إلا كان b "قوي" (فقاعة حقيقية) ولا a ضعيف
        if (a.el.contains(b.el) && (b.strong || !a.strong)) return false;
        // a ضعيف (غلاف نص داخلي) وداخل فقاعة قوية: كنحيدوه
        if (!a.strong && b.strong && b.el.contains(a.el)) return false;
      }
      return true;
    });
  }

  // واش حنا داخل صفحة "Replies" ديال تعليق "بدأ"
  function isRepliesView() {
    var head = lines(document.body).slice(0, 8).map(function (s) { return s.toLowerCase(); });
    if (head.indexOf('replies') !== -1 || head.indexOf('الردود') !== -1) return true;
    var els = document.querySelectorAll('div, span, h1, h2, h3');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var t = (el.innerText || '').trim().toLowerCase();
      if (t !== 'replies' && t !== 'الردود') continue;
      if (el.getBoundingClientRect().top < 300) return true;
    }
    return false;
  }

  // كنقراو آخر تعليق فالثريد: إلا كان ديال الكاتب وجديد، كنصيفطوه لشات AI
  // كيضغط على "See more" فالتعليقات الطويلة باش نقراو الرد كامل
  async function expandSeeMore() {
    for (var round = 0; round < 3; round++) {
      var els = document.querySelectorAll('div, span, a, [role="button"]');
      var best = null, bestTop = -1;
      for (var i = 0; i < els.length; i++) {
        if (!visible(els[i])) continue;
        var t = clean((els[i].innerText || els[i].textContent || '').trim());
        if (!t || t.length > 20 || !SEE_MORE.test(t)) continue;
        var r = els[i].getBoundingClientRect();
        if (r.bottom < 0 || r.top > window.innerHeight) continue;
        if (r.top > bestTop) { bestTop = r.top; best = r; }
      }
      if (!best) return;
      tapAt(best.left + best.width / 2, best.top + best.height / 2);
      await sleep(900);
    }
  }

  // مفتاح خفيف للمقارنة: الكاتب + أول 40 حرف (بلا "See more") باش التوسيع ما يبدلش المفتاح
  function looseKey(c) {
    return c.author + '|' + norm(c.body).replace(/(…|\.\.\.)?\s*(see more|عرض المزيد|voir plus)$/i, '').slice(0, 40);
  }

  // لائحة تعليقات الثريد مرتبة من فوق لتحت
  function buildThread(anchor) {
    var aLeft = anchor ? anchor.getBoundingClientRect().left : -1e9;
    var list = candidates();
    var thread = [];

    for (var i = 0; i < list.length; i++) {
      var it = list[i];
      if (anchor) {
        if (!(anchor.compareDocumentPosition(it.el) & 4)) continue;
        if (anchor.contains(it.el)) continue;
        if (it.el.getBoundingClientRect().left <= aLeft + 30) break;
      }
      if (it.c.author.indexOf(MY_NAME) === 0 && it.c.body === ANCHOR_TEXT) continue; // تعليق "بدأ" نفسو
      it.top = it.el.getBoundingClientRect().top + window.scrollY;
      thread.push(it);
    }
    thread.sort(function (a, b) { return a.top - b.top; });
    return thread;
  }

  // كيتناده (من Java) قبل ما نصيفطو رسالة: كيحفظ آخر تعليق وعدد التعليقات دابا
  window.__botMarkBase = function () {
    try {
      var anchor = isRepliesView() ? null : findAnchor();
      var th = buildThread(anchor);
      window.__botBaseKey = th.length ? looseKey(th[th.length - 1].c) : '';
      window.__botBaseCount = th.length;
      try { sessionStorage.setItem('__botBase', JSON.stringify({ k: window.__botBaseKey, n: window.__botBaseCount })); } catch (e) {}
    } catch (e) {}
  };
  // بعد reload للصفحة نرجعو الحالة المحفوظة
  if (typeof window.__botBaseKey !== 'string') {
    try {
      var sb = JSON.parse(sessionStorage.getItem('__botBase') || 'null');
      if (sb && typeof sb.k === 'string') { window.__botBaseKey = sb.k; window.__botBaseCount = sb.n || 0; }
    } catch (e) {}
  }

  function scanThread(anchor, firstRun) {
    var thread = buildThread(anchor);
    if (!thread.length) return;

    // ---- وضع انتظار الرد: كناخدو آخر تعليق، إلا ماشي ديالنا (البوت) => هو رد الكاتب ----
    var sent = window.__botSent ? norm(window.__botSent) : '';
    if (sent) {
      // كل رسالة جديدة كنبداو من الصفر
      if (window.__botStateFor !== window.__botSendId) {
        window.__botStateFor = window.__botSendId;
        window.__botBase = null;
        window.__botSeenOwn = false;
      }

      var lastItem = thread[thread.length - 1];
      var lastC = lastItem.c;
      var lastIsOwn = isOwn(lastC.author);

      if (lastIsOwn) { window.__botSeenOwn = true; return; } // آخر تعليق ديالنا: نسناو

      var kk = hash(lastC.author + '|' + lastC.body);
      var ownCount = 0, hasOwnMatch = false;
      for (var j3 = 0; j3 < thread.length - 1; j3++) {
        if (isOwn(thread[j3].c.author)) {
          ownCount++;
          if (sameText(thread[j3].c.body, sent)) hasOwnMatch = true;
        }
      }

      if (typeof window.__botBaseKey === 'string') {
        // عندنا صورة ديال الثريد قبل الإرسال: الرد جديد إلا آخر تعليق تبدل ولا زادو تعليقين (تعليقنا + الرد)
        var isNew = looseKey(lastC) !== window.__botBaseKey || thread.length >= (window.__botBaseCount || 0) + 2;
        if (!isNew) return;
      } else if (!hasOwnMatch && !window.__botSeenOwn) {
        // (احتياط) تعليقنا مازال ما ظهرش: آخر تعليق هو القديم، ما نصيفطوهش
        if (window.__botBase === null || window.__botBase === undefined) { window.__botBase = kk; return; }
        if (window.__botBase === kk) return;
      }

      // آخر تعليق ماشي ديالنا وجديد => رد الكاتب
      var k2 = hash(lastC.author + '|' + lastC.body + '|' + ownCount);
      if (seen[k2]) return;
      seen[k2] = true;
      window.__botSent = '';
      window.__botWaiting = false;
      var shown2 = stripOwn(lastC.body);
      AndroidBridgeJS.onFbReply(k2, lastC.author, shown2);
      return;
    }

    // آخر تعليق فالثريد (ممكن يكون مكرر: نسخة فصفحة Replies ونسخة فصفحة البوست، نفس المفتاح)
    var last = thread[thread.length - 1].c;
    if (isOwn(last.author)) return; // تعليق ديالنا

    // المفتاح كيتبدل كل ما كتصيفط تعليق جديد، باش الردود المتشابهة ما تتحسبش مكررة
    var own = {};
    var n = 0;
    for (var j = 0; j < thread.length; j++) {
      var c = thread[j].c;
      if (isOwn(c.author) && !own[c.body]) { own[c.body] = 1; n++; }
    }
    var key = hash(last.author + '|' + last.body + '|' + n);
    if (seen[key]) return;
    seen[key] = true;

    var waiting = !!window.__botWaiting;
    if (firstRun && !waiting) return; // أول قراءة بلا انتظار: غير نسجل الموجود

    window.__botWaiting = false;
    var shown = last.body;
    shown = stripOwn(shown);
    AndroidBridgeJS.onFbReply(key, last.author, shown);
  }

  async function tick() {
    if (ticking) return;
    if (window.__botTyping && Date.now() - (window.__botTypingAt || 0) < 60000) return; // السكريبت ديال الرد كيخدم
    if (window.__botPulling && Date.now() - (window.__botPullingAt || 0) < 15000) return; // السحب (refresh) جاري
    ticking = true;
    try {
      // داخل Replies: ما كنحتاجو لا anchor لا ترتيب، كنقراو مباشرة
      if (isRepliesView()) {
        if (window.__botSent) { scrollBottom(); await sleep(800); }
        await expandSeeMore();
        scanThread(null, !baselineDone);
        baselineDone = true;
        return;
      }

      var anchor = findAnchor();

      if (!anchor) {
        anchorMiss++;
        // ما لقاش "بدأ" بزاف (3 فحوصات متتالية): نرتب Newest (مرة كل 30 ثانية)، وماشي وقت كنسناو الرد
        if (anchorMiss >= 3 && !window.__botSent && !sorting && Date.now() - lastSort > SORT_COOLDOWN) {
          sorting = true;
          try { AndroidBridgeJS.setBusy(true); } catch (e) {}
          lastSort = Date.now();
          log('🔃 ما لقيتش "بدأ"، كنرتب التعليقات Newest...');
          sortNewest().then(function (ok) {
            sorting = false;
            try { AndroidBridgeJS.setBusy(false); } catch (e) {}
            log(ok ? '✅ تم الترتيب Newest' : '❌ ما قدرتش نرتب التعليقات');
          });
        }
        return;
      }

      anchorMiss = 0;
      if (window.__botSent) { scrollBottom(); await sleep(800); }
      await expandSeeMore();
      scanThread(anchor, !baselineDone);
      baselineDone = true;
    } finally {
      ticking = false;
    }
  }

  // زر Reply: الأقرب تحت تعليق "بدأ"
  function findReplyBtn(anchorRect) {
    var best = null, bestD = 1e9;
    var nodes = document.querySelectorAll('div, span, a, button, [role="button"]');
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var t = (n.innerText || '').trim();
      if (REPLY_WORDS.indexOf(t) === -1) continue;
      if (!visible(n)) continue;
      var d = n.getBoundingClientRect().top - anchorRect.bottom;
      if (d < -20 || d > 200) continue;
      if (d < bestD) { bestD = d; best = n; }
    }
    return best;
  }

  // Java كيستعملهم: واش حنا فـ Replies؟ ونرجعو لـ Replies إلا خرجنا للمنشور
  // Java كيناديها بعد كل refresh: كينزل لآخر الصفحة ويشوف واش كاين تعليق جديد (مرتين)
  window.__botScanNow = async function () {
    window.__botPulling = false;
    for (var w = 0; w < 40 && ticking; w++) await sleep(200); // نستناو الفحص الجاري يسالي
    await tick();
    await sleep(1500);
    for (var w2 = 0; w2 < 40 && ticking; w2++) await sleep(200);
    await tick();
  };

  window.__botIsReplies = function () { return isRepliesView(); };
  window.__botOpenReplies = function () {
    try {
      if (isRepliesView()) return 'R';
      var anchor = findAnchor();
      if (!anchor) return 'noanchor';
      anchor.scrollIntoView({ block: 'center' });
      setTimeout(function () {
        var a = findAnchor() || anchor;
        var b = findReplyBtn(a.getBoundingClientRect());
        if (b) tap(b);
      }, 700);
      return 'ok';
    } catch (e) { return 'err'; }
  };

  // نافذة "You're out of data..." (inwi): كنضغطو CONTINUE أوتوماتيك
  function dismissDataPopup() {
    try {
      var txt = (document.body && document.body.innerText) || '';
      if (!/out of data|can still use Facebook|inwi/i.test(txt)) return;
      var els = document.querySelectorAll('div, span, a, button, [role="button"]');
      var best = null, bestA = 1e12;
      for (var i = 0; i < els.length; i++) {
        var t = (els[i].innerText || els[i].textContent || '').replace(/\s+/g, ' ').trim();
        if (!/^(continue|continuer|متابعة)$/i.test(t)) continue;
        var r = els[i].getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0 || r.bottom < 0 || r.top > window.innerHeight) continue;
        if (r.width * r.height < bestA) { bestA = r.width * r.height; best = r; }
      }
      if (best) tapAt(best.left + best.width / 2, best.top + best.height / 2);
    } catch (e) {}
  }
  if (!window.__botPopupTimer) window.__botPopupTimer = setInterval(dismissDataPopup, 1500);
  dismissDataPopup();

  // بعد 6 ثوانٍ نسجل الموجود، ومن بعدها نراقب كل 4 ثوانٍ
  // إلا كنسناو الرد (مثلا بعد reload) نبداو بسرعة
  setTimeout(function () {
    tick();
    setInterval(tick, 3000);
  }, window.__botWaiting ? 2500 : 6000);
})();