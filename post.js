(async function () {
  var log = function (m) { AndroidBridgeJS.logToChat(m); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function visible(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function pressEl(el) {
    try {
      el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, pointerType: 'touch', isPrimary: true }));
    } catch (e) {}
    ['touchstart', 'mousedown', 'touchend', 'mouseup'].forEach(function (t) {
      try {
        var ev = t.indexOf('touch') === 0
          ? new Event(t, { bubbles: true, cancelable: true })
          : new MouseEvent(t, { bubbles: true, cancelable: true, view: window });
        el.dispatchEvent(ev);
      } catch (e) {}
    });
    el.click();
  }

  // خانة التعليق الرئيسية تحت المنشور (ماشي خانة الرد على تعليق)
  function findComposer() {
    var eds = document.querySelectorAll('div[contenteditable="true"], div[role="textbox"], textarea');
    var fallback = null;
    for (var i = 0; i < eds.length; i++) {
      var e = eds[i];
      if (!visible(e)) continue;
      var hint = ((e.getAttribute('aria-label') || '') + ' ' +
                  (e.getAttribute('placeholder') || '') + ' ' +
                  (e.getAttribute('data-placeholder') || '')).toLowerCase();
      if (/comment|تعليق|commentaire/.test(hint)) return e;
      fallback = e;
    }
    return fallback;
  }

  function typeText(ed, text) {
    ed.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    var ok = document.execCommand('insertText', false, text);
    if (!ok || !(ed.textContent || '').trim()) {
      ed.textContent = text;
      ed.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  var SEND_WORDS = ['send', 'post', 'submit', 'ارسال', 'إرسال', 'نشر', 'envoyer', 'publier'];

  function labelOf(el) {
    return ((el.getAttribute('aria-label') || '') + ' ' +
            (el.getAttribute('data-sigil') || '') + ' ' +
            (el.getAttribute('value') || '') + ' ' +
            (el.innerText || '')).trim().toLowerCase();
  }

  function clickableOf(el) {
    if (el.tagName && el.tagName.toLowerCase() === 'svg') {
      return el.closest('[role="button"], button, a, div[tabindex]') || el.parentElement;
    }
    return el;
  }

  function findSendBtn(ed) {
    var er = ed.getBoundingClientRect();
    var ecy = er.top + er.height / 2;
    var nodes = document.querySelectorAll('button, [role="button"], input[type="submit"], a, div[tabindex], svg, [aria-label]');

    // بالاسم
    for (var i = nodes.length - 1; i >= 0; i--) {
      var c = clickableOf(nodes[i]);
      if (!c || !visible(c) || c === ed || c.contains(ed) || ed.contains(c)) continue;
      var lab = labelOf(c);
      for (var w = 0; w < SEND_WORDS.length; w++) {
        if (lab.indexOf(SEND_WORDS[w]) !== -1) return c;
      }
    }

    // بالموقع: أقصى زر على اليمين في نفس صف الصندوق
    var best = null, bestRight = -1;
    for (var j = 0; j < nodes.length; j++) {
      var b = clickableOf(nodes[j]);
      if (!b || !visible(b) || b === ed || b.contains(ed) || ed.contains(b)) continue;
      var br = b.getBoundingClientRect();
      var cy = br.top + br.height / 2;
      var onRight = br.left > er.left + er.width / 2;
      if (Math.abs(cy - ecy) < Math.max(60, er.height) && onRight && br.right > bestRight) {
        best = b;
        bestRight = br.right;
      }
    }
    return best;
  }

  log('⏳ كنكتب التعليق على المنشور...');
  var ed = findComposer();
  if (!ed) { log('❌ ما لقيت خانة التعليق فالصفحة'); return; }

  ed.scrollIntoView({ block: 'center' });
  ed.focus();
  typeText(ed, replyText);
  await sleep(1200);

  var btn = findSendBtn(ed);
  if (btn) {
    pressEl(btn);
    log('✅ تم إرسال التعليق، كنتسناو الرد...');
  } else {
    var k = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
    ed.dispatchEvent(new KeyboardEvent('keydown', k));
    ed.dispatchEvent(new KeyboardEvent('keyup', k));
    log('⚠️ زر الإرسال ما تلقاش، جربت Enter');
  }

  await sleep(2500);
  var left = (ed.textContent || '').trim();
  if (left && left.indexOf(replyText.slice(0, 10)) !== -1) {
    log('❌ التعليق مازال فالصندوق ولم يُرسل');
  }
})();