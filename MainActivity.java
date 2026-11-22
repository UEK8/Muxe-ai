

package com.my.newproject4;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.util.Base64;
import java.io.File;
import java.io.FileOutputStream;
import android.webkit.WebChromeClient;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.ArrayDeque;
import java.util.concurrent.ConcurrentHashMap;

public class MainActivity extends Activity {

    static final String FB_UA = "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36";

    // بيكسل شفاف 1x1: كيتعوض بيه الصور باش ما تبانش أيقونة مكسورة
    static final byte[] PIXEL = android.util.Base64.decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
            android.util.Base64.DEFAULT);

    // ---- إعدادات زيارة صفحة الكاتب ----
    static final String AUTHOR_NAME = "Mostafa Hachmi";
    static final int MAX_PROFILE_VISITS = 1;
    static final long PROFILE_DWELL_MS = 1500;
    static final long PROFILE_COOLDOWN_MS = 60000;
    static final long BACK_CHECK_MS = 2000;
    static final int AUTHOR_SEARCH_TRIES = 10;
    static final long AUTHOR_SEARCH_DELAY_MS = 1000;

    // ---- إعدادات انتظار الرد ----
    static final long REFRESH_INTERVAL_MS = 3000;   // المدة بين كل refresh والتاني
    static final long REFRESH_WAIT_MS = 1500;        // نستنى الدائرة تدور وتتحمل التعليقات قبل القراءة
    static final int MAX_REFRESH_TRIES = Integer.MAX_VALUE; // بلا حد: كيبقى كيعمل refresh حتى يجي رد جديد

    // ---- إعدادات السحب (مطابقة لسحب الإصبع الحقيقي) ----
    static final float PULL_START_Y = 40f;           // كيبدا من أعلى الصفحة
    static final float PULL_END_Y = 700f;
    static final float REPLIES_PULL_START_Y = 260f;  // داخل Replies: السحب كيبدا من وسط اللائحة
    static final float REPLIES_PULL_END_Y = 1000f;            // مسافة أكبر باش الدائرة توصل وتتفعل
    static final int PULL_STEPS = 20;                // خطوات السحب
    static final int HOLD_STEPS = 10;                // كيبقى الإصبع شوية فالنهاية
    static final long PULL_STEP_MS = 25;             // سرعة كل خطوة

    WebView webViewAI, webViewFB;
    static final int FILE_CHOOSER_REQ = 4711;
    volatile boolean assetAccountOk = false; // واش facebook.json فيه c_user و xs
    volatile boolean fbLoginKnown = false;   // واش عرفنا الحالة الحقيقية (من صفحة فيسبوك)
    volatile boolean fbLoggedIn = false;     // الحالة الحقيقية: مسجل الدخول ولا لا
    int loginRetries = 0;                    // محاولات إعادة تطبيق الكوكيز + reload
    static final int PICK_IMG_REQ = 4712; // اختيار الصور مباشرة (بلا WebView)
    ValueCallback<Uri[]> fileCallback;
    volatile File pendingImageFile = null;   // الصورة اللي غادي نعطيو لفيسبوك ملي يحل المعرض
    volatile boolean imageChosenFlag = false;
    FrameLayout container;
    Button btnTabAI, btnTabFB;
    Handler handler = new Handler(Looper.getMainLooper());
    volatile boolean running = false;
    boolean botStarted = false;
    volatile boolean visitingProfile = false;
    volatile boolean returningFromProfile = false;
    volatile boolean waitingForReply = false;
    volatile boolean pulling = false;
    // طابور الإرسال: النص والصور كيتصيفطو واحد بواحد
    ArrayDeque<Runnable> sendQueue = new ArrayDeque<Runnable>();
    boolean sendBusy = false;
    boolean taskRunning = false;
    int sendGen = 0;
    volatile String lastDeliveredBody = null; // آخر رد وصل للشات (باش ما يتكررش)
    volatile long lastDeliveredAt = 0;
    volatile String lastSentText = null; // النص اللي صيفطنا: كنقارنو بيه آخر تعليق
    volatile boolean jsBusy = false; // سكريبت كيخدم (ترتيب/رد): ممنوع السحب فهاد الوقت
    volatile boolean postLoadedOnce = false; // رابط المنشور كيتحمل مرة وحدة فقط
    int profileVisits = 0;
    int refreshTries = 0;
    long lastProfileVisit = 0;
    String postUrl = "https://www.facebook.com/groups/2086448822074318/posts/2086449138740953/";
    ConcurrentHashMap<String, Boolean> handled = new ConcurrentHashMap<String, Boolean>();

    Runnable refreshRunnable = new Runnable() {
        public void run() {
            runPullRefresh();
        }
    };

    void scheduleRefresh() {
        handler.removeCallbacks(refreshRunnable);
        handler.postDelayed(refreshRunnable, REFRESH_INTERVAL_MS);
    }

    void cancelRefresh() {
        handler.removeCallbacks(refreshRunnable);
    }

    // ---------- حلقة الـ refresh ----------
    void runPullRefresh() {
        if (!running || !waitingForReply || pulling) return;
        if (jsBusy) { scheduleRefresh(); return; }

        if (refreshTries >= MAX_REFRESH_TRIES) {
            waitingForReply = false;
            cancelRefresh();
            hideTyping();
            return;
        }

        refreshTries++;
        cancelRefresh();

        // الـ refresh كيتدار غير داخل تعليق "بدأ" (صفحة Replies). إلا خرجنا للمنشور نرجعو ليه.
        webViewFB.evaluateJavascript(
                "(function(){try{return window.__botIsReplies()?'R':'P';}catch(e){return 'U';}})()",
                new ValueCallback<String>() {
                    public void onReceiveValue(String v) {
                        if (!running || !waitingForReply) return;
                        if (v != null && v.contains("R")) {
                            pullInReplies();
                        } else if (v != null && v.contains("P")) {
                            reopenReplies();
                        } else {
                            injectWatch(); // السكريبت ما محقونش بعد
                            scheduleRefresh();
                        }
                    }
                });
    }

    // خرجنا للمنشور: كنرجعو لصفحة Replies (كنضغطو Reply تحت "بدأ")
    void reopenReplies() {
        scheduleRefresh();
        webViewFB.evaluateJavascript("(function(){try{return window.__botOpenReplies();}catch(e){return 'err';}})()", null);
        handler.postDelayed(new Runnable() {
            public void run() {
                readComments();
            }
        }, 3000);
    }

    // سحب (refresh) داخل صفحة Replies: كنرجعو اللائحة لفوق، والسحب كيبدا من داخل اللائحة (ماشي من الهيدر)
    void pullInReplies() {
        scheduleRefresh();
        webViewFB.evaluateJavascript(
                "(function(){window.scrollTo(0,0);var a=document.querySelectorAll('*');for(var i=0;i<a.length;i++){var e=a[i];if(e.scrollTop>0&&e.scrollHeight>e.clientHeight){e.scrollTop=0;}}})()", null);
        handler.postDelayed(new Runnable() {
            public void run() {
                if (!running || !waitingForReply) return;
                // نوقفو الفحص ديال السكريبت وقت السحب (باش ما ينزلش لتحت وسط السحب)
                webViewFB.evaluateJavascript("window.__botPulling=true;window.__botPullingAt=Date.now();", null);
                startPull(REPLIES_PULL_START_Y, REPLIES_PULL_END_Y, new Runnable() {
                    public void run() {
                        handler.postDelayed(new Runnable() {
                            public void run() {
                                readComments();
                            }
                        }, REFRESH_WAIT_MS);
                    }
                });
            }
        }, 400);
    }

    // سحب بطيء ومتدرج: الإصبع كينزل بشوية شوية، كيبقى فالنهاية، وبعدها كيتحرر
    void startPull(final float startY, final float endY, final Runnable onDone) {
        if (webViewFB.getWidth() <= 0) {
            logChat("ما قدرتش ندير السحب: صفحة فيسبوك ما محسوباش");
            return;
        }

        pulling = true;
        final float x = webViewFB.getWidth() / 2f;
        final long downTime = SystemClock.uptimeMillis();
        sendTouch(MotionEvent.ACTION_DOWN, x, startY, downTime);

        final int[] step = {0};
        handler.postDelayed(new Runnable() {
            public void run() {
                step[0]++;
                if (step[0] <= PULL_STEPS) {
                    // مرحلة السحب: كنزيدو المسافة شوية بشوية
                    float t = step[0] / (float) PULL_STEPS;
                    float y = startY + (endY - startY) * t;
                    sendTouch(MotionEvent.ACTION_MOVE, x, y, downTime);
                    handler.postDelayed(this, PULL_STEP_MS);
                } else if (step[0] <= PULL_STEPS + HOLD_STEPS) {
                    // مرحلة التوقف: الإصبع كيبقى فالنهاية
                    sendTouch(MotionEvent.ACTION_MOVE, x, endY, downTime);
                    handler.postDelayed(this, PULL_STEP_MS);
                } else {
                    // تحرير الإصبع
                    sendTouch(MotionEvent.ACTION_UP, x, endY, downTime);
                    pulling = false;
                    if (onDone != null) onDone.run();
                }
            }
        }, PULL_STEP_MS);
    }

    // كيرسل حدث لمس بنفس خصائص الإصبع الحقيقي (pressure و size و finger)
    void sendTouch(int action, float x, float y, long downTime) {
        MotionEvent.PointerProperties[] props = new MotionEvent.PointerProperties[1];
        props[0] = new MotionEvent.PointerProperties();
        props[0].id = 0;
        props[0].toolType = MotionEvent.TOOL_TYPE_FINGER;

        MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[1];
        coords[0] = new MotionEvent.PointerCoords();
        coords[0].x = x;
        coords[0].y = y;
        coords[0].pressure = 1f;
        coords[0].size = 1f;

        MotionEvent e = MotionEvent.obtain(downTime, SystemClock.uptimeMillis(), action,
                1, props, coords, 0, 0, 1f, 1f, 0, 0,
                InputDevice.SOURCE_TOUCHSCREEN, 0);
        webViewFB.dispatchTouchEvent(e);
        e.recycle();
    }

    // كيقرا التعليقات الجديدة ويصيفطها لشات AI، وكيكمل الحلقة
    void readComments() {
        if (!running || !waitingForReply) return;
        injectWatch();
        // نهبطو لآخر الصفحة ونشوفو واش كاين تعليق جديد
        webViewFB.evaluateJavascript("(function(){window.__botPulling=false;try{window.__botScanNow();}catch(e){}})()", null);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0f0f1a"));

        LinearLayout tabBar = new LinearLayout(this);
        tabBar.setOrientation(LinearLayout.HORIZONTAL);

        btnTabAI = new Button(this);
        btnTabAI.setText("AI Chat");
        btnTabAI.setBackgroundColor(Color.parseColor("#7c5cff"));
        btnTabAI.setTextColor(Color.WHITE);

        btnTabFB = new Button(this);
        btnTabFB.setText("فيسبوك");
        btnTabFB.setBackgroundColor(Color.parseColor("#2d2d44"));
        btnTabFB.setTextColor(Color.WHITE);

        LinearLayout.LayoutParams btnParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        tabBar.addView(btnTabAI, btnParams);
        tabBar.addView(btnTabFB, btnParams);

        container = new FrameLayout(this);
        LinearLayout.LayoutParams containerParams = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);

        root.addView(tabBar);
        root.addView(container, containerParams);
        setContentView(root);

        // ---- WebView الشات (AI) ----
        webViewAI = new WebView(this);
        WebSettings s1 = webViewAI.getSettings();
        s1.setJavaScriptEnabled(true);
        s1.setDomStorageEnabled(true);
        webViewAI.addJavascriptInterface(new BridgeAI(), "AndroidBridge");

        webViewAI.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                if (!botStarted) {
                    botStarted = true;
                    new BridgeAI().startBot();
                }
            }
        });
        // اختيار الصور من المعرض (زر الصورة فالشات): WebView كيحتاج WebChromeClient باش يحل المعرض
        webViewAI.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    i.setType("image/*");
                    i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                    startActivityForResult(Intent.createChooser(i, "Choose images"), FILE_CHOOSER_REQ);
                } catch (Exception e) {
                    fileCallback = null;
                    callback.onReceiveValue(null);
                    return false;
                }
                return true;
            }
        });
        webViewAI.loadUrl("file:///android_asset/index.html");

        // ---- WebView فيسبوك ----
        webViewFB = new WebView(this);
        WebSettings s2 = webViewFB.getSettings();
        s2.setJavaScriptEnabled(true);
        s2.setDomStorageEnabled(true);
        s2.setUserAgentString(FB_UA);
        s2.setMediaPlaybackRequiresUserGesture(true);
        webViewFB.addJavascriptInterface(new BridgeJS(), "AndroidBridgeJS");
        webViewFB.setWebViewClient(new FbClient());
        // ملي فيسبوك كيحل المعرض (بعد الضغط على أيقونة الصورة): كنعطيو الصورة ديال البوت أوتوماتيكيا
        webViewFB.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                File f = pendingImageFile;
                if (f != null && f.exists()) {
                    callback.onReceiveValue(new Uri[]{Uri.fromFile(f)});
                    imageChosenFlag = true;
                    return true;
                }
                callback.onReceiveValue(null);
                return true;
            }
        });

        container.addView(webViewAI);
        container.addView(webViewFB);
        // INVISIBLE بدل GONE: باش تبقى محسوبة وتخدم حركة السحب
        webViewFB.setVisibility(View.INVISIBLE);

        btnTabAI.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                webViewAI.setVisibility(View.VISIBLE);
                webViewFB.setVisibility(View.INVISIBLE);
                btnTabAI.setBackgroundColor(Color.parseColor("#7c5cff"));
                btnTabFB.setBackgroundColor(Color.parseColor("#2d2d44"));
            }
        });

        btnTabFB.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                webViewAI.setVisibility(View.INVISIBLE);
                webViewFB.setVisibility(View.VISIBLE);
                btnTabFB.setBackgroundColor(Color.parseColor("#7c5cff"));
                btnTabAI.setBackgroundColor(Color.parseColor("#2d2d44"));
            }
        });

        initCookiesOnce();
    }

    // كوكيز facebook.json كتتطبق مرة وحدة فقط (أول مرة، ولا ملي الملف يتبدل). من بعد الجلسة كتبقى محفوظة
    // فالـWebView وفيسبوك كيجددها بوحدو. إعادة تطبيق الكوكيز القديمة كل مرة كانت كتقتل الجلسة.
    volatile boolean cookiesAppliedThisRun = false;

    void initCookiesOnce() {
        try {
            String raw = readAsset("facebook.json");
            String sig = raw.length() + ":" + raw.hashCode();
            android.content.SharedPreferences sp = getSharedPreferences("bot", MODE_PRIVATE);
            if (!sig.equals(sp.getString("cookiesSig", ""))) {
                final String fsig = sig;
                final android.content.SharedPreferences fsp = sp;
                wipeWebData(new Runnable() {
                    public void run() {
                        loadCookiesFromAsset();
                        cookiesAppliedThisRun = true;
                        fsp.edit().putString("cookiesSig", fsig).apply();
                    }
                });
            } else {
                // نفس الملف: ما كنلمسوش الجلسة المحفوظة
                java.util.ArrayList<String[]> items = parseCookies(raw);
                boolean u = false, x = false;
                for (int i = 0; i < items.size(); i++) {
                    if (items.get(i)[0].equals("c_user")) u = true;
                    if (items.get(i)[0].equals("xs")) x = true;
                }
                assetAccountOk = u && x;
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // كنخزنو الكوكيز فالقرص ملي كنخرجو من التطبيق (باش الجلسة المجددة ما تضيعش)
    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onStop() {
        super.onStop();
        CookieManager.getInstance().flush();
    }

    // ---------- m.facebook.com فقط ----------
    long rewriteWindowStart = 0;
    int rewriteCount = 0;

    // free./zero./www./web./touch. ... -> m.facebook.com (نفس المسار)
    String toMobile(String url) {
        if (url == null) return null;
        try {
            Uri u = Uri.parse(url);
            String h = u.getHost();
            if (h == null) return null;
            h = h.toLowerCase();
            if (h.equals("free.facebook.com") || h.equals("zero.facebook.com") || h.equals("0.facebook.com")
                    || h.equals("other.facebook.com") || h.equals("touch.facebook.com")
                    || h.equals("www.facebook.com") || h.equals("web.facebook.com") || h.equals("facebook.com")) {
                // حماية من الحلقة اللانهائية: أكثر من 6 تحويلات فـ10 ثواني = نوقفو
                long now = System.currentTimeMillis();
                if (now - rewriteWindowStart > 10000) { rewriteWindowStart = now; rewriteCount = 0; }
                if (++rewriteCount > 6) return null;
                return u.buildUpon().authority("m.facebook.com").build().toString();
            }
        } catch (Exception e) { }
        return null;
    }

    // ---------- مسح داتا فيسبوك كاملة ----------
    // كيمسح الكوكيز + التخزين + الكاش ديال فيسبوك (باش الحسابات/الجلسات القديمة ما تخلطش الدخول).
    // ما كيمسحش تخزين صفحة الشات (file://)
    void wipeWebData(final Runnable then) {
        try {
            android.webkit.WebStorage ws = android.webkit.WebStorage.getInstance();
            String[] origins = {"https://m.facebook.com", "https://www.facebook.com", "https://facebook.com", "https://touch.facebook.com"};
            for (int i = 0; i < origins.length; i++) {
                try { ws.deleteOrigin(origins[i]); } catch (Throwable t) { }
            }
            webViewFB.clearCache(true);
            webViewFB.clearHistory();
            webViewFB.clearFormData();
        } catch (Throwable t) { }

        final CookieManager cm = CookieManager.getInstance();
        cm.removeAllCookies(new ValueCallback<Boolean>() {
            public void onReceiveValue(Boolean done) {
                cm.flush();
                if (then != null) then.run();
            }
        });
    }

    // مسح كامل + تطبيق الكوكيز + تحميل فيسبوك من جديد
    void fullReset(final WebView view) {
        wipeWebData(new Runnable() {
            public void run() {
                loadCookiesFromAsset();
                view.loadUrl("https://m.facebook.com/");
            }
        });
    }

    // ---------- WebViewClient ----------
    class FbClient extends WebViewClient {
        long lastRecover = 0;
        int recoverCount = 0;

        private boolean allow(String url) {
            return url != null && (url.startsWith("http://") || url.startsWith("https://"));
        }

        @Override
        public boolean shouldOverrideUrlLoading(final WebView view, String url) {
            final String m = toMobile(url);
            if (m != null && !m.equals(url)) {
                handler.post(new Runnable() { public void run() { view.loadUrl(m); } });
                return true;
            }
            return !allow(url);
        }

        @Override
        public boolean shouldOverrideUrlLoading(final WebView view, WebResourceRequest request) {
            String url = request.getUrl().toString();
            final String m = toMobile(url);
            if (m != null && !m.equals(url)) {
                handler.post(new Runnable() { public void run() { view.loadUrl(m); } });
                return true;
            }
            return !allow(url);
        }

        // ERR_TOO_MANY_REDIRECTS على free./zero.: نرجعو لـ m.facebook.com (بلا مسح الجلسة)
        @Override
        public void onReceivedError(final WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
            super.onReceivedError(view, request, error);
            if (request.isForMainFrame()) {
                final String m = toMobile(request.getUrl().toString());
                if (m != null) {
                    handler.post(new Runnable() { public void run() { view.loadUrl(m); } });
                }
            }
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            String u = request.getUrl().toString().toLowerCase();

            boolean isImage = u.contains("scontent") || u.contains(".jpg") || u.contains(".jpeg")
                    || u.contains(".png") || u.contains(".webp");
            if (isImage) {
                return new WebResourceResponse("image/png", null, new ByteArrayInputStream(PIXEL));
            }

            boolean isVideo = (u.contains("video.") && u.contains("fbcdn"))
                    || u.contains(".mp4") || u.contains(".m3u8") || u.contains(".gif");
            if (isVideo) {
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }

            return super.shouldInterceptRequest(view, request);
        }

        @Override
        public void onPageFinished(final WebView view, String url) {
            checkLogin(view);
            if (!running) return;
            if (navActive) return; // التنقل (☰ ← Groups ← Chat ← المنشور) كيتحكم فيه navRunnable

            if (visitingProfile || returningFromProfile) return;

            // أثناء انتظار الرد: الـ refresh كيتم غير بالسحب (الدائرة الزرقاء).
            // ممنوع نعاودو ندخلو لنفس الرابط، نقراو التعليقات غير.
            if (waitingForReply) {
                if (!pulling) {
                    injectWatch();
                }
                return;
            }

            boolean onPost = url != null && (url.contains("/posts/") || url.contains("story_fbid"));
            if (!onPost) {
                goBackToPost();
                injectWatch(); // داخل Replies مثلا: كنكملو المراقبة بلا ما نخرجو
                return;
            }

            view.evaluateJavascript(
                "(function(){return (document.body && document.body.innerText.indexOf('out of data') !== -1) ? '1' : '0';})()",
                new ValueCallback<String>() {
                    public void onReceiveValue(String v) {
                        if (v != null && v.contains("1")) {
                            goBackToPost();
                            injectWatch();
                        } else if (waitingForReply) {
                            injectWatch();
                            scheduleRefresh();
                        } else {
                            recoverCount = 0;
                            injectWatch();
                        }
                    }
                });
        }

        void goBackToPost() {
            if (postLoadedOnce) return; // ما ندخلوش لرابط المنشور مرة ثانية
            if (waitingForReply) return; // ما نعاودوش نحملو الرابط وحنا كنسناو الرد
            long now = System.currentTimeMillis();
            if (now - lastRecover < 60000 || recoverCount >= 5) return;
            lastRecover = now;
            recoverCount++;
            handler.postDelayed(new Runnable() {
                public void run() {
                    if (running) webViewFB.loadUrl(postUrl.replace("www.", "m."));
                }
            }, 1000);
        }
    }

    // ---------- تحقق حقيقي من تسجيل الدخول ----------
    // كنشوفو واش الصفحة صفحة login/checkpoint، وواش الكوكيز (c_user + xs) كاينين فعلا فالمتصفح
    void checkLogin(final WebView view) {
        view.evaluateJavascript(
                "(function(){try{var u=location.href;var l=/\\/login|checkpoint|recover|two_step/.test(u)"
                        + "||!!document.querySelector('input[name=pass],input[type=password]');"
                        + "var c=/Use another profile|Create new account|استخدام ملف شخصي آخر|إنشاء حساب جديد|Utiliser un autre profil|Créer un nouveau compte/i.test(document.body?document.body.innerText:'');"
                        + "return c?'C':(l?'L':'O');}catch(e){return 'O';}})()",
                new ValueCallback<String>() {
                    public void onReceiveValue(String v) {
                        boolean chooser = v != null && v.contains("C");
                        boolean loginPage = chooser || (v != null && v.contains("L"));
                        String ck = CookieManager.getInstance().getCookie("https://m.facebook.com");
                        boolean has = ck != null && ck.contains("c_user=") && ck.contains("xs=");
                        boolean ok = has && !loginPage;
                        setFbLoginState(ok);
                        if (loginPage && cookiesAppliedThisRun && loginRetries < 1) {
                            // كوكيز جداد تطبقو دابا ولكن الدخول ما تمش: محاولة وحدة (مسح + تطبيق + reload)
                            loginRetries++;
                            fullReset(view);
                        } else if (chooser && loginRetries < 4) {
                            // مازال صفحة اختيار الحساب: كنضغطو على الحساب بضغطة حقيقية
                            loginRetries++;
                            tapProfileOnChooser();
                        } else if (loginPage) {
                            showToast("الجلسة ما بقاتش صالحة. بدل facebook.json بكوكيز جداد. كوكيز فالمتصفح: " + cookieNamesInJar() + " | الصفحة: " + view.getUrl());
                        } else if (ok) {
                            loginRetries = 0;
                        }
                    }
                });
    }

    // كيشغل nav.js: فصفحة اختيار الحساب كيضغط على اسم الحساب
    void tapProfileOnChooser() {
        if (navActive) return; // nav.js كيدير هادشي بوحدو
        handler.postDelayed(new Runnable() {
            public void run() {
                try {
                    if (navSrc == null) navSrc = readAsset("nav.js");
                    webViewFB.evaluateJavascript(navSrc + ";window.__navStep()", null);
                } catch (Exception e) { }
            }
        }, 700);
    }

    void setFbLoginState(boolean ok) {
        boolean changed = !fbLoginKnown || fbLoggedIn != ok;
        fbLoginKnown = true;
        fbLoggedIn = ok;
        if (changed) {
            handler.post(new Runnable() {
                public void run() {
                    webViewAI.evaluateJavascript("try{updateStatus();}catch(e){}", null);
                }
            });
        }
    }

    // ---------- التنقل للمنشور: ☰ ← Groups ← Chat ← "بدأ محادثة" ----------
    static final long NAV_POLL_MS = 350;
    static final long NAV_TIMEOUT_MS = 45000;
    volatile boolean navActive = false;
    long navStart = 0;
    String navSrc = null; // نص nav.js كيتقرا مرة وحدة

    Runnable navRunnable = new Runnable() {
        public void run() {
            stepNav();
        }
    };

    void startNav() {
        navActive = true;
        navStart = System.currentTimeMillis();
        handler.removeCallbacks(navRunnable);
        webViewFB.loadUrl("https://m.facebook.com/");
        handler.postDelayed(navRunnable, 800);
    }

    void stopNav() {
        navActive = false;
        handler.removeCallbacks(navRunnable);
    }

    // إلا فشل التنقل أو طال: كنحملو رابط المنشور مباشرة (احتياط)
    void navFallback() {
        navActive = false;
        webViewFB.loadUrl(postUrl.replace("www.", "m."));
    }

    void stepNav() {
        if (!running || !navActive) return;
        if (System.currentTimeMillis() - navStart > NAV_TIMEOUT_MS) {
            navFallback();
            return;
        }
        String js;
        try {
            if (navSrc == null) navSrc = readAsset("nav.js");
            js = navSrc + ";window.__navStep()";
        } catch (Exception e) {
            navFallback();
            return;
        }
        webViewFB.evaluateJavascript(js, new ValueCallback<String>() {
            public void onReceiveValue(String v) {
                if (!running || !navActive) return;
                if (v != null && v.contains("done")) {
                    navActive = false;
                    injectWatch();
                } else if (v != null && v.contains("fail")) {
                    navFallback();
                } else {
                    handler.postDelayed(navRunnable, NAV_POLL_MS);
                }
            }
        });
    }

    // ---------- أدوات ----------
    void showToast(final String msg) {
        handler.post(new Runnable() {
            public void run() {
                Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show();
            }
        });
    }

    void hideTyping() {
        handler.post(new Runnable() {
            public void run() {
                webViewAI.evaluateJavascript("hideTyping()", null);
            }
        });
    }

    // اللوغات ما بقاتش كتبان فالشات: كتمشي غير لـ Logcat
    void logChat(final String msg) {
        android.util.Log.d("BotLog", msg);
    }

    String readAsset(String name) throws Exception {
        InputStream is;
        try {
            is = getAssets().open(name);
        } catch (Exception e) {
            showToast("ما لقيتش الملف: " + name);
            throw e;
        }
        BufferedReader br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            sb.append(line).append("\n");
        }
        br.close();
        return sb.toString();
    }

    // كيحقن watch.js مع تعريف واش كنسناو الرد (باش ما يضيعش بعد reload للصفحة)
    void injectWatch() {
        String sentJs = (lastSentText != null) ? ("window.__botSent=" + JSONObject.quote(lastSentText) + ";") : "";
        inject("watch.js", "window.__botWaiting=" + (waitingForReply ? "true" : "false") + ";" + sentJs);
    }

    void inject(String asset, String prefix) {
        try {
            String js = readAsset(asset);
            if (prefix != null) js = prefix + js;
            webViewFB.evaluateJavascript(js, null);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // كيحول data URL لملف فـ cache باش نعطيوه لفيسبوك
    void prepareImageFile(String dataUrl) {
        pendingImageFile = null;
        imageChosenFlag = false;
        try {
            int comma = dataUrl.indexOf(',');
            byte[] bytes = Base64.decode(dataUrl.substring(comma + 1), Base64.DEFAULT);
            File f = new File(getCacheDir(), "fbimg_" + System.currentTimeMillis() + ".jpg");
            FileOutputStream out = new FileOutputStream(f);
            out.write(bytes);
            out.close();
            pendingImageFile = f;
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ---------- طابور الإرسال ----------
    void enqueueSend(Runnable r) {
        sendQueue.add(r);
        if (!sendBusy) nextSend();
    }

    void nextSend() {
        Runnable r = sendQueue.poll();
        if (r == null) {
            sendBusy = false;
            return;
        }
        sendBusy = true;
        r.run();
    }

    // كيسالي الإرسال الحالي ويدوز للّي موراه (مرة وحدة فقط)
    void finishSendTask() {
        if (!taskRunning) return;
        taskRunning = false;
        handler.postDelayed(new Runnable() {
            public void run() {
                nextSend();
            }
        }, 1500);
    }

    void startSendTask(String asset, String extraPrefix, String sentText) {
        if (sentText != null) lastSentText = sentText;
        String prefix = "try{window.__botBaseKey=undefined;sessionStorage.removeItem('__botBase');window.__botMarkBase&&window.__botMarkBase();}catch(e){}" + extraPrefix + "window.__botWaiting=true;"
                + (sentText != null ? ("window.__botSent=" + JSONObject.quote(sentText) + ";") : "")
                + "window.__botSendId=" + System.currentTimeMillis() + ";"
                + "window.__botTyping=true;window.__botTypingAt=Date.now();";
        jsBusy = true; // الـ refresh كيبدا غير من بعد ما السكريبت يسالي (replyFinished)
        taskRunning = true;
        waitingForReply = true;
        refreshTries = 0;
        cancelRefresh();
        inject(asset, prefix);
        final int gen = ++sendGen;
        // أمان: إلا السكريبت ما رجعش، نحرر بعد 60 ثانية
        handler.postDelayed(new Runnable() {
            public void run() {
                if (gen == sendGen && taskRunning) {
                    jsBusy = false;
                    if (waitingForReply) scheduleRefresh();
                    pendingImageFile = null;
                    imageChosenFlag = false;
                    finishSendTask();
                }
            }
        }, 60000);
    }

    // ---------- الجسور (JavaScript -> Java) ----------
    class BridgeAI {
        // فتح معرض الصور فالحين (بلا المرور من input/WebView ولا createChooser)
        // واش كاين حساب داخل (كوكيز facebook.json)
        @JavascriptInterface
        public boolean accountReady() {
            return fbLoginKnown ? fbLoggedIn : assetAccountOk;
        }

        @JavascriptInterface
        public void pickImages() {
            handler.post(new Runnable() {
                public void run() {
                    try {
                        Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                        i.addCategory(Intent.CATEGORY_OPENABLE);
                        i.setType("image/*");
                        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                        startActivityForResult(i, PICK_IMG_REQ);
                    } catch (Exception e) {
                        showToast("ما قدرتش نحل المعرض");
                    }
                }
            });
        }

        @JavascriptInterface
        public void startBot() {
            handler.post(new Runnable() {
                public void run() {
                    handled.clear();
                    sendQueue.clear();
                    sendBusy = false;
                    taskRunning = false;
                    lastSentText = null;
                    visitingProfile = false;
                    returningFromProfile = false;
                    waitingForReply = false;
                    pulling = false;
                    refreshTries = 0;
                    cancelRefresh();
                    profileVisits = 0;
                    lastProfileVisit = 0;
                    running = true;
                    postLoadedOnce = true;
                    startNav();
                }
            });
        }

        @JavascriptInterface
        public void stopBot() {
            running = false;
            waitingForReply = false;
            cancelRefresh();
            stopNav();
            hideTyping();
        }

        @JavascriptInterface
        public void sendReplyToFB(final String text) {
            handler.post(new Runnable() {
                public void run() {
                    enqueueSend(new Runnable() {
                        public void run() {
                            startSendTask("replyInThread.js", "var replyText = " + JSONObject.quote(text) + ";", text);
                        }
                    });
                }
            });
        }

        // صورة (data URL) مع نص اختياري
        @JavascriptInterface
        public void sendImageToFB(final String dataUrl, final String caption) {
            handler.post(new Runnable() {
                public void run() {
                    enqueueSend(new Runnable() {
                        public void run() {
                            String cap = (caption == null) ? "" : caption;
                            prepareImageFile(dataUrl);
                            String extra = "var imageData = " + JSONObject.quote(dataUrl) + ";"
                                    + "var captionText = " + JSONObject.quote(cap) + ";";
                            startSendTask("replyImage.js", extra, cap.length() > 0 ? cap : null);
                        }
                    });
                }
            });
        }
    }

    class BridgeJS {
        @JavascriptInterface
        public void onFbReply(final String key, final String author, final String body) {
            if (!running) return;
            if (handled.putIfAbsent(key, Boolean.TRUE) != null) return;

            // نفس النص بنفس الكاتب خلال دقيقتين = نفس الرد (مفاتيح مختلفة): كنتجاهلوه
            String nb = (author + "|" + body).replaceAll("\\s+", " ").trim();
            long nowMs = System.currentTimeMillis();
            if (nb.equals(lastDeliveredBody) && nowMs - lastDeliveredAt < 120000) return;
            lastDeliveredBody = nb;
            lastDeliveredAt = nowMs;

            if (waitingForReply) { // رد جديد حقيقي كيوقف الانتظار
                waitingForReply = false;
                cancelRefresh();
            }
            lastSentText = null;

            handler.post(new Runnable() {
                public void run() {
                    webViewAI.evaluateJavascript(
                        "onFbReply(" + JSONObject.quote(key) + "," +
                        JSONObject.quote(author) + "," +
                        JSONObject.quote(body) + ")", null);
                }
            });
        }

        @JavascriptInterface
        public boolean imageChosen() {
            return imageChosenFlag;
        }

        @JavascriptInterface
        public void setBusy(final boolean b) {
            handler.post(new Runnable() {
                public void run() {
                    jsBusy = b;
                    if (!b && waitingForReply) scheduleRefresh();
                }
            });
        }

        @JavascriptInterface
        public void replyFinished() {
            handler.post(new Runnable() {
                public void run() {
                    jsBusy = false;
                    refreshTries = 0;
                    if (waitingForReply) scheduleRefresh();
                    pendingImageFile = null;
                    imageChosenFlag = false;
                    finishSendTask();
                }
            });
        }

        // ضغطة لمس حقيقية على إحداثيات CSS (كيجيو من JavaScript)
        @JavascriptInterface
        public void nativeTap(final double cssX, final double cssY) {
            handler.post(new Runnable() {
                public void run() {
                    float d = webViewFB.getResources().getDisplayMetrics().density;
                    final float px = (float) (cssX * d);
                    final float py = (float) (cssY * d);
                    final long downTime = SystemClock.uptimeMillis();
                    sendTouch(MotionEvent.ACTION_DOWN, px, py, downTime);
                    handler.postDelayed(new Runnable() {
                        public void run() {
                            sendTouch(MotionEvent.ACTION_UP, px, py, downTime);
                        }
                    }, 70);
                }
            });
        }

        @JavascriptInterface
        public void logToChat(final String msg) {
            android.util.Log.d("BotLog", msg);
        }
    }

    // ---------- الكوكيز ----------
    // كيقرا facebook.json بجميع الصيغ المعروفة ويرجع لائحة {name, value, domain, path, secure, httpOnly, maxAge}:
    // 1) لائحة JSON  2) {"cookies":[...]}  3) {"name":"value",...}  4) Netscape (cookies.txt)  5) نص "a=1; b=2"
    java.util.ArrayList<String[]> parseCookies(String raw) {
        java.util.ArrayList<String[]> items = new java.util.ArrayList<String[]>();
        long nowSec = System.currentTimeMillis() / 1000;
        if (raw == null) return items;
        raw = raw.replace("\uFEFF", "").trim();
        try {
            JSONArray arr = null;
            if (raw.startsWith("[")) {
                arr = new JSONArray(raw);
            } else if (raw.startsWith("{")) {
                JSONObject root = new JSONObject(raw);
                if (root.optJSONArray("cookies") != null) {
                    arr = root.optJSONArray("cookies");
                } else {
                    java.util.Iterator<String> it = root.keys();
                    while (it.hasNext()) {
                        String k = it.next();
                        Object v = root.opt(k);
                        if (v instanceof String) items.add(new String[]{k, (String) v, ".facebook.com", "/", "1", "0", ""});
                    }
                    return items;
                }
            }
            if (arr != null) {
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject o = arr.optJSONObject(i);
                    if (o == null) continue;
                    String name = o.optString("name", o.optString("Name", o.optString("key", "")));
                    String value = o.optString("value", o.optString("Value", ""));
                    if (name.length() == 0) continue;
                    String domain = o.optString("domain", o.optString("Domain", ".facebook.com"));
                    if (domain.length() == 0) domain = ".facebook.com";
                    String path = o.optString("path", "/");
                    if (path.length() == 0) path = "/";
                    String secure = o.optBoolean("secure", true) ? "1" : "0";
                    String httpOnly = o.optBoolean("httpOnly", false) ? "1" : "0";
                    String maxAge = "";
                    double exp = o.optDouble("expirationDate", o.optDouble("expires", o.optDouble("expiry", -1)));
                    if (exp > 0) {
                        if (exp > 1e11) exp = exp / 1000;
                        long left = (long) exp - nowSec;
                        if (left <= 0) continue;
                        maxAge = String.valueOf(left);
                    }
                    items.add(new String[]{name, value, domain, path, secure, httpOnly, maxAge});
                }
                return items;
            }
        } catch (Exception e) {
            items.clear();
        }

        // Netscape: domain \t flag \t path \t secure \t expiry \t name \t value
        if (raw.contains("\t")) {
            String[] lines = raw.split("\\r?\\n");
            for (int i = 0; i < lines.length; i++) {
                String ln = lines[i].trim();
                boolean httpOnlyLine = ln.startsWith("#HttpOnly_");
                if (httpOnlyLine) ln = ln.substring(10);
                if (ln.length() == 0 || ln.startsWith("#")) continue;
                String[] c = ln.split("\t");
                if (c.length < 7) continue;
                String maxAge = "";
                try {
                    long exp = Long.parseLong(c[4].trim());
                    if (exp > 0) {
                        long left = exp - nowSec;
                        if (left <= 0) continue;
                        maxAge = String.valueOf(left);
                    }
                } catch (Exception e) { }
                items.add(new String[]{c[5].trim(), c[6].trim(), c[0].trim(), c[2].trim(),
                        c[3].trim().equalsIgnoreCase("TRUE") ? "1" : "0", httpOnlyLine ? "1" : "0", maxAge});
            }
            if (!items.isEmpty()) return items;
        }

        // نص عادي: "a=1; b=2; c=3"
        String[] parts = raw.split(";");
        for (int i = 0; i < parts.length; i++) {
            String p = parts[i].trim();
            int eq = p.indexOf('=');
            if (eq <= 0) continue;
            items.add(new String[]{p.substring(0, eq).trim(), p.substring(eq + 1).trim(), ".facebook.com", "/", "1", "0", ""});
        }
        return items;
    }

    // أسماء الكوكيز لي فعلا كاينين فالمتصفح (بلا قيم) باش نعرفو شنو دخل
    String cookieNamesInJar() {
        String ck = CookieManager.getInstance().getCookie("https://m.facebook.com");
        if (ck == null || ck.length() == 0) return "(خاوي)";
        StringBuilder sb = new StringBuilder();
        String[] parts = ck.split(";");
        for (int i = 0; i < parts.length; i++) {
            String p = parts[i].trim();
            int eq = p.indexOf('=');
            if (eq > 0) { if (sb.length() > 0) sb.append(", "); sb.append(p.substring(0, eq)); }
        }
        return sb.toString();
    }

    // كل كوكي كيتحط بوحدو: CookieManager.setCookie كياخد كوكي واحد (Set-Cookie)
    void loadCookiesFromAsset() {
        try {
            java.util.ArrayList<String[]> items = parseCookies(readAsset("facebook.json"));
            if (items.isEmpty()) {
                assetAccountOk = false;
                showToast("facebook.json خاوي ولا الصيغة ما معروفاش، ولا كل الكوكيز منتهية");
                return;
            }

            boolean hasUser = false, hasXs = false;
            for (int i = 0; i < items.size(); i++) {
                if (items.get(i)[0].equals("c_user")) hasUser = true;
                if (items.get(i)[0].equals("xs")) hasXs = true;
            }
            assetAccountOk = hasUser && hasXs;
            if (!assetAccountOk) showToast("facebook.json ما فيهش c_user ولا xs: " + (hasUser ? "" : "c_user ") + (hasXs ? "" : "xs"));

            CookieManager cookieManager = CookieManager.getInstance();
            cookieManager.setAcceptCookie(true);

            String[] urls = {"https://m.facebook.com", "https://www.facebook.com", "https://facebook.com"};
            for (int k = 0; k < items.size(); k++) {
                String[] it = items.get(k);
                StringBuilder sc = new StringBuilder();
                sc.append(it[0]).append("=").append(it[1]);
                sc.append("; Domain=").append(it[2].startsWith(".") ? it[2] : "." + it[2].replaceFirst("^www\\.", ""));
                sc.append("; Path=").append(it[3]);
                if (it[6].length() > 0) sc.append("; Max-Age=").append(it[6]);
                if (it[4].equals("1")) sc.append("; Secure");
                if (it[5].equals("1")) sc.append("; HttpOnly");
                for (int i = 0; i < urls.length; i++) {
                    cookieManager.setCookie(urls[i], sc.toString());
                }
            }
            cookieManager.flush();
        } catch (Exception e) {
            e.printStackTrace();
            showToast("ما قدرتش نحمل الكوكيز: " + e.getMessage());
        }
    }

    // كيقرا الصورة، كيصغرها (1280 كحد أقصى) ويرجعها data URL
    String uriToDataUrl(Uri uri) {
        try {
            android.graphics.BitmapFactory.Options o = new android.graphics.BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            InputStream is = getContentResolver().openInputStream(uri);
            android.graphics.BitmapFactory.decodeStream(is, null, o);
            is.close();
            int sample = 1;
            while (Math.max(o.outWidth, o.outHeight) / sample > 2560) sample *= 2;
            o = new android.graphics.BitmapFactory.Options();
            o.inSampleSize = sample;
            is = getContentResolver().openInputStream(uri);
            android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeStream(is, null, o);
            is.close();
            if (bmp == null) return null;

            int rot = 0;
            try {
                InputStream es = getContentResolver().openInputStream(uri);
                int ori = new android.media.ExifInterface(es).getAttributeInt(
                        android.media.ExifInterface.TAG_ORIENTATION, android.media.ExifInterface.ORIENTATION_NORMAL);
                es.close();
                if (ori == android.media.ExifInterface.ORIENTATION_ROTATE_90) rot = 90;
                else if (ori == android.media.ExifInterface.ORIENTATION_ROTATE_180) rot = 180;
                else if (ori == android.media.ExifInterface.ORIENTATION_ROTATE_270) rot = 270;
            } catch (Throwable t) { }

            float k = Math.min(1f, 1280f / Math.max(bmp.getWidth(), bmp.getHeight()));
            android.graphics.Matrix m = new android.graphics.Matrix();
            m.postScale(k, k);
            if (rot != 0) m.postRotate(rot);
            android.graphics.Bitmap out = android.graphics.Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);

            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            out.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, bos);
            return "data:image/jpeg;base64," + Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP);
        } catch (Throwable t) {
            return null;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_IMG_REQ) {
            if (resultCode != RESULT_OK || data == null) return;
            final java.util.ArrayList<Uri> uris = new java.util.ArrayList<Uri>();
            if (data.getClipData() != null) {
                for (int i = 0; i < data.getClipData().getItemCount(); i++) uris.add(data.getClipData().getItemAt(i).getUri());
            } else if (data.getData() != null) {
                uris.add(data.getData());
            }
            new Thread(new Runnable() {
                public void run() {
                    final JSONArray arr = new JSONArray();
                    for (Uri u : uris) {
                        String d = uriToDataUrl(u);
                        if (d != null) arr.put(d);
                    }
                    handler.post(new Runnable() {
                        public void run() {
                            webViewAI.evaluateJavascript("addPickedImages(" + arr.toString() + ")", null);
                        }
                    });
                }
            }).start();
            return;
        }
        if (requestCode != FILE_CHOOSER_REQ || fileCallback == null) return;
        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int n = data.getClipData().getItemCount();
                result = new Uri[n];
                for (int i = 0; i < n; i++) result[i] = data.getClipData().getItemAt(i).getUri();
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }
        fileCallback.onReceiveValue(result);
        fileCallback = null;
    }
}
