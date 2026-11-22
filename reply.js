(async function () {
  var log = function (m) { AndroidBridgeJS.logToChat(m); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function pressEl(el) {
    var list = [
      ['pointer', 'pointerdown'], ['touch', 'touchstart'], ['mouse', 'mousedown'],
      ['pointer', 'pointerup'],   ['touch', 'touchend'],   ['mouse', 'mouseup']
    ];
    for (var i = 0; i < list.length; i++) {
      try {
        var ev;
        if (list[i][0] === 'pointer' && typeof PointerEvent !== 'undefined') {
          ev = new PointerEvent(list[i][1], { bubbles: true, cancelable: true, view: window, pointerType: 'touch', isPrimary: true });
        } else if (list[i][0] === 'touch') {
          ev = new Event(list[i][1], { bubbles: true, cancelable: true });
        } else {
          ev = new MouseEvent(list[i][1], { bubbles: true, cancelable: true, view: window });
        }
        el.dispatchEvent(ev);
      } catch (e) {}
    }
    el.click();
  }

  function findReplyBtn() {
    var all = document.querySelectorAll('*');
    for (var i = all.length - 1; i >= 0; i--) {
      var el = all[i];
      var t = (el.innerText || el.textContent || '').trim();
      if ((t === 'Reply' || t === 'رد') && visible(el)) return el;
    }
    return null;
  }

  function findEditor() {
    var eds = document.querySelectorAll('div[contenteditable="true"], div[role="textbox"], textarea');
    for (var i = eds.length - 1; i >= 0; i--) {
      if (visible(eds[i])) return eds[i];
    }
    return null;
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

  function findSendBtn(editor) {
    var er = editor.getBoundingClientRect();
    var ecx = er.left + er.width / 2;
    var ecy = er.top + er.height / 2;

    var nodes = document.querySelectorAll('button, [role="button"], input[type="submit"], a, div[tabindex], svg, [aria-label]');

    // 1) بالاسم
    for (var i = nodes.length - 1; i >= 0; i--) {
      var c = clickableOf(nodes[i]);
      if (!c || !visible(c) || c === editor || c.contains(editor) || editor.contains(c)) continue;
      var lab = labelOf(c);
      for (var w = 0; w < SEND_WORDS.length; w++) {
        if (lab.indexOf(SEND_WORDS[w]) !== -1) return { el: c, how: 'label:' + SEND_WORDS[w] };
      }
    }

    // 2) بالموقع: أقصى زر على اليمين في نفس صف الصندوق
    var best = null, bestRight = -1;
    for (var j = 0; j < nodes.length; j++) {
      var b = clickableOf(nodes[j]);
      if (!b || !visible(b) || b === editor || b.contains(editor) || editor.contains(b)) continue;
      var br = b.getBoundingClientRect();
      var cx = br.left + br.width / 2;
      var cy = br.top + br.height / 2;
      var sameRow = Math.abs(cy - ecy) < Math.max(60, er.height);
      var onRight = cx > ecx;
      if (sameRow && onRight && br.right > bestRight) {
        best = b;
        bestRight = br.right;
      }
    }
    if (best) return { el: best, how: 'position' };

    return null;
  }

  function debugCandidates(editor) {
    var er = editor.getBoundingClientRect();
    var nodes = document.querySelectorAll('button, [role="button"], div[tabindex], a');
    var out = [];
    for (var i = 0; i < nodes.length && out.length < 8; i++) {
      var n = nodes[i];
      if (!visible(n)) continue;
      var r = n.getBoundingClientRect();
      if (Math.abs(r.top - er.top) > 200) continue;
      var lab = labelOf(n).slice(0, 30) || '(بدون نص)';
      out.push(lab + ' x=' + Math.round(r.left) + ' y=' + Math.round(r.top));
    }
    return out.join(' | ');
  }

  // ---- 1) الضغط على Reply ----
  log('⏳ البحث عن زر Reply...');
  var replyBtn = findReplyBtn();
  if (!replyBtn) { log('❌ لم يتم العثور على زر Reply'); return; }
  pressEl(replyBtn);
  log('✅ تم الضغط على Reply');

  // ---- 2) كتابة النص ----
  await sleep(3000);
  var editor = findEditor();
  if (!editor) { log('❌ لم يتم العثور على صندوق الكتابة'); return; }
  typeText(editor, replyText);
  log('✅ تم كتابة النص فـ الصندوق');

  // ---- 3) الإرسال ----
  await sleep(1500);
  var found = findSendBtn(editor);
  if (found) {
    pressEl(found.el);
    log('✅ تم الضغط على زر الإرسال (' + found.how + ')');
  } else {
    log('⚠️ لم يُعثر على زر الإرسال، أجرب Enter');
    var k = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
    editor.dispatchEvent(new KeyboardEvent('keydown', k));
    editor.dispatchEvent(new KeyboardEvent('keypress', k));
    editor.dispatchEvent(new KeyboardEvent('keyup', k));
  }

  // ---- 4) التحقق ----
  await sleep(2500);
  var stillThere = (editor.textContent || '').trim();
  if (!stillThere || stillThere.indexOf(replyText.slice(0, 15)) === -1) {
    log('🎉 تم الإرسال بنجاح');
  } else {
    log('❌ النص مازال في الصندوق. الأزرار القريبة: ' + debugCandidates(editor));
  }
})();