(async function () {
  var MY_NAME = 'Mostafa Hachmi';
  var ANCHOR_TEXT = 'بدأ';
  var SEND_WORDS = ['send', 'post', 'submit', 'ارسال', 'إرسال', 'نشر', 'envoyer', 'publier'];
  var REPLY_WORDS = ['Reply', 'رد', 'Répondre'];
  var SORT_WORDS = ['most relevant', 'le plus pertinent', 'الأكثر ملاءمة', 'الأكثر صلة'];
  var NEWEST_WORDS = ['newest', 'plus récents', 'الأحدث'];
  var OK_WORDS = ['ok', 'حسنا', 'موافق'];

  var log = function (m) { AndroidBridgeJS.logToChat(m); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function lines(el) {
    return (el.innerText || '').split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function firstLine(el) {
    return ((el.innerText || '').split('\n')[0] || '').trim().toLowerCase();
  }

  function hintOf(el) {
    return ((el.getAttribute('aria-label') || '') + ' ' +
            (el.getAttribute('placeholder') || '') + ' ' +
            (el.getAttribute('data-placeholder') || '')).toLowerCase();
  }

  function editors() {
    var list = document.querySelectorAll('div[contenteditable="true"], div[role="textbox"], textarea');
    var out = [];
    for (var i = 0; i < list.length; i++) {
      if (visible(list[i])) out.push(list[i]);
    }
    return out;
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

  function pressEnter(ed) {
    var k = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
    ed.dispatchEvent(new KeyboardEvent('keydown', k));
    ed.dispatchEvent(new KeyboardEvent('keypress', k));
    ed.dispatchEvent(new KeyboardEvent('keyup', k));
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

  function isRepliesView() {
    var head = lines(document.body).slice(0, 8).map(function (s) { return s.toLowerCase(); });
    if (head.indexOf('replies') !== -1 || head.indexOf('الردود') !== -1) return true;
    var els = document.querySelectorAll('div, span, h1, h2, h3');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!visible(el)) continue;
      var t = (el.innerText || '').trim().toLowerCase();
      if ((t === 'replies' || t === 'الردود') && el.getBoundingClientRect().top < 300) return true;
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
      if (d < bestD) {
        bestD = d;
        best = n;
      }
    }
    return best;
  }

  // الخانة الجديدة اللي ظهرت بعد Reply، ولا الأقرب تحت "بدأ"
  function pickEditor(before, anchor) {
    var now = editors();
    var fresh = now.filter(function (e) { return before.indexOf(e) === -1; });
    var pool = fresh.length ? fresh : now;
    if (!pool.length) return null;

    for (var i = 0; i < pool.length; i++) {
      if (/repl|رد/.test(hintOf(pool[i]))) return pool[i];
    }

    var ar = anchor.getBoundingClientRect();
    var best = null, bestTop = 1e9;
    for (var j = 0; j < pool.length; j++) {
      var top = pool[j].getBoundingClientRect().top;
      if (top >= ar.top && top < bestTop) {
        bestTop = top;
        best = pool[j];
      }
    }
    return best || pool[pool.length - 1];
  }

  function typeText(ed, text) {
    ed.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    var ok = document.execCommand('insertText', false, text);
    if (!ok || !(ed.textContent || '').trim()) {
      ed.textContent = text;
      try {
        ed.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
      } catch (e) {
        ed.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
  }

  function clickableOf(el) {
    if (el.tagName && el.tagName.toLowerCase() === 'svg') {
      return el.closest('[role="button"], button, a, div[tabindex]') || el.parentElement;
    }
    return el;
  }

  // كل العناصر القابلة للضغط قرب الخانة
  function sendCandidates(ed) {
    var out = [];
    var p = ed.parentElement;
    for (var lvl = 0; lvl < 6 && p; lvl++) {
      var nodes = p.querySelectorAll('button, [role="button"], input[type="submit"], a, div[tabindex], svg, [aria-label]');
      for (var i = 0; i < nodes.length; i++) {
        var c = clickableOf(nodes[i]);
        if (!c || !visible(c) || c === ed || c.contains(ed) || ed.contains(c)) continue;
        if (out.indexOf(c) === -1) out.push(c);
      }
      p = p.parentElement;
    }
    return out;
  }

  // بالاسم (aria-label/value/data-sigil)، والنص القصير فقط
  function nameOf(el) {
    var attrs = ((el.getAttribute('aria-label') || '') + ' ' +
                 (el.getAttribute('data-sigil') || '') + ' ' +
                 (el.getAttribute('value') || '')).trim().toLowerCase();
    var txt = (el.innerText || '').trim().toLowerCase();
    return txt.length <= 20 ? (attrs + ' ' + txt).trim() : attrs;
  }

  function findSendBtn(ed) {
    var cands = sendCandidates(ed);

    for (var i = 0; i < cands.length; i++) {
      var nm = nameOf(cands[i]);
      for (var w = 0; w < SEND_WORDS.length; w++) {
        if (nm.indexOf(SEND_WORDS[w]) !== -1) return cands[i];
      }
    }

    // بالموقع: أقرب زر فنفس الصف
    var er = ed.getBoundingClientRect();
    var best = null, bestGap = 1e9;
    for (var j = 0; j < cands.length; j++) {
      var r = cands[j].getBoundingClientRect();
      if (!(r.top < er.bottom && r.bottom > er.top)) continue;
      var gap = r.left > er.right ? r.left - er.right : (r.right < er.left ? er.left - r.right : 0);
      if (gap < bestGap && gap < 150) {
        bestGap = gap;
        best = cands[j];
      }
    }
    return best;
  }

  // ---------- رفع الصورة ----------
  function dataUrlToFile(d) {
    var parts = d.split(',');
    var mime = ((parts[0].match(/data:(.*?);/) || [])[1]) || 'image/jpeg';
    var bin = atob(parts[1]);
    var arr = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new File([arr], 'photo.' + (mime.split('/')[1] || 'jpg'), { type: mime });
  }

  function okInput(q) {
    return !q.accept || q.accept.indexOf('image') !== -1 || q.accept.indexOf('*') !== -1;
  }

  // input[type=file] الأقرب لخانة الرد
  function findFileInput(ed) {
    var p = ed;
    for (var l = 0; l < 10 && p; l++, p = p.parentElement) {
      var q = p.querySelectorAll('input[type="file"]');
      for (var i = 0; i < q.length; i++) if (okInput(q[i])) return q[i];
    }
    var all = document.querySelectorAll('input[type="file"]');
    for (var j = 0; j < all.length; j++) if (okInput(all[j])) return all[j];
    return null;
  }

  // زر الصورة (الأيقونة) حدا خانة الرد
  function findPhotoBtn(ed) {
    var cands = sendCandidates(ed);
    for (var i = 0; i < cands.length; i++) {
      if (/photo|image|picture|صورة|صور/.test(nameOf(cands[i]))) return cands[i];
    }
    var er = ed.getBoundingClientRect();
    var best = null, bestRight = -1e9, k;
    // 1) من المرشحين: اللي على يسار الخانة فنفس الصف
    for (k = 0; k < cands.length; k++) {
      var r1 = cands[k].getBoundingClientRect();
      if (!(r1.top < er.bottom && r1.bottom > er.top)) continue;
      if (r1.right > er.left + 10) continue;
      if (r1.right > bestRight) { bestRight = r1.right; best = cands[k]; }
    }
    if (best) return best;
    // 2) أي عنصر صغير على يسار الخانة (الأيقونة ممكن ما تكونش button)
    var nodes = document.querySelectorAll('div, label, a, button, span, i, [role="button"]');
    for (k = 0; k < nodes.length; k++) {
      var n = nodes[k];
      var r2 = n.getBoundingClientRect();
      if (r2.width < 20 || r2.width > 100 || r2.height < 20 || r2.height > 100) continue;
      if (!(r2.top < er.bottom && r2.bottom > er.top)) continue;
      if (r2.right > er.left + 10) continue;
      if (r2.right > bestRight) { bestRight = r2.right; best = n; }
    }
    return best;
  }

  // 1) نضغطو على أيقونة الصورة: Java كيعطي الصورة أوتوماتيكيا للمعرض
  // 2) إلا ما خداتش: نحقنو الملف مباشرة فـ input[type=file]
  async function attachImage(ed, d) {
    var pb = findPhotoBtn(ed);
    if (pb) {
      tap(pb);
      await sleep(2200);
      try { if (AndroidBridgeJS.imageChosen()) { log('🖼️ الصورة تحددات عبر المعرض'); return true; } } catch (e) {}
    }
    var input = findFileInput(ed);
    if (!input) return false;
    var file = dataUrlToFile(d);
    var dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    log('🖼️ الصورة تحقنات فـ input');
    return true;
  }

  // أسفل خانة كتابة فالصفحة
  function bottomEditor() {
    var all = editors(), ed = null;
    for (var q = 0; q < all.length; q++) {
      if (!ed || all[q].getBoundingClientRect().top > ed.getBoundingClientRect().top) ed = all[q];
    }
    return ed;
  }

  async function main() {
    if (typeof imageData === 'undefined' || !imageData) {
      log('❌ ما كاينة حتى تصويرة');
      return;
    }

    var ed = null;

    if (isRepliesView()) {
      // حنا داخل Replies ديال "بدأ": الخانة ديال الرد ديجا كاينة تحت، بلا ما نخرجو ولا نضغطو Reply
      var all = editors();
      for (var q = 0; q < all.length; q++) {
        if (!ed || all[q].getBoundingClientRect().top > ed.getBoundingClientRect().top) ed = all[q];
      }
      if (!ed) {
        log('❌ ما لقيتش خانة الرد فصفحة Replies');
        return;
      }
      log('✏️ كنكتب الرد داخل Replies');
    } else {
      // 1) تعليق "بدأ"، وإلا نرتب Newest ونعاود نلقاه
      var anchor = await waitFor(findAnchor, 7000); // نستنى حتى تظهر التعليقات قبل ما نضغطو Most relevant
      if (!anchor) {
        log('🔃 ما لقيتش "بدأ"، كنرتب التعليقات Newest...');
        var sorted = await sortNewest();
        if (!sorted) log('⚠️ ما قدرتش نرتب التعليقات');
        anchor = findAnchor();
        if (!anchor) {
          log('❌ ما لقيتش تعليق "بدأ" حتى بعد الترتيب');
          return;
        }
      }
      anchor.scrollIntoView({ block: 'center' });
      await sleep(800);
      anchor = findAnchor() || anchor;

      // 2) زر Reply تحت "بدأ"
      var replyBtn = findReplyBtn(anchor.getBoundingClientRect());
      if (!replyBtn) {
        log('❌ ما لقيتش Reply تحت "بدأ"');
        return;
      }

      var before = editors();
      tap(replyBtn);
      await sleep(2500);

      // 3) خانة الرد
      ed = pickEditor(before, anchor);
      if (!ed) {
        log('❌ ما ظهرتش خانة الرد');
        return;
      }
    }

    // 4) رفع الصورة (قبل النص، حيت فيسبوك كيعاود يرسم الخانة)
    var attached = await attachImage(ed, imageData);
    if (!attached) {
      log('❌ ما قدرتش نرفع الصورة (ما لقيتش زر/خانة الصور)');
      return;
    }
    log('🖼️ كنسناو صفحة Preview...');

    // 4b) فيسبوك كيحل صفحة Preview فيها زر Upload photo: كنضغطو عليه
    var UPLOAD_WORDS = ['upload photo', 'upload', 'téléverser la photo', 'télécharger la photo', 'تحميل الصورة', 'رفع الصورة', 'تحميل'];
    var up = await waitFor(function () { return findWithText(UPLOAD_WORDS, true) || findWithText(UPLOAD_WORDS, false); }, 8000);
    if (up) {
      tap(up);
      log('⬆️ ضغطت Upload photo');
      await sleep(3500);
    } else {
      log('⚠️ ما لقيتش Upload photo (يمكن الصورة تحملات مباشرة)');
      await sleep(1500);
    }

    // رجعنا لصفحة "Your comment": الخانة تحت
    ed = await waitFor(bottomEditor, 6000);
    if (!ed) {
      log('❌ ما ظهرتش خانة التعليق من بعد الصورة');
      return;
    }

    // 5) نص مع الصورة (اختياري)
    if (typeof captionText === 'string' && captionText) {
      typeText(ed, captionText);
      await sleep(800);
    }

    // 6) الإرسال
    var btn = findSendBtn(ed);
    if (btn) {
      tap(btn);
      log('📤 ضغطت زر الإرسال');
    } else {
      // السهم الأزرق فأقصى اليمين، فنفس صف الخانة
      var er = ed.getBoundingClientRect();
      tapAt(window.innerWidth - 28, er.top + er.height / 2);
      log('⚠️ زر الإرسال ما تلقاش بالاسم، ضغطت فأقصى اليمين');
    }
    await sleep(3500);
    log('✅ تم إرسال الصورة تحت "بدأ"');
  }

  try {
    await main();
  } catch (e) {
    log('❌ خطأ فـ replyInThread: ' + (e && e.message ? e.message : e));
  }
  window.__botTyping = false;
  try { AndroidBridgeJS.replyFinished(); } catch (e) {}
})();