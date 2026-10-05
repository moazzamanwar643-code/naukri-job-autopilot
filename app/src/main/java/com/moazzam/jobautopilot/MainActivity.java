package com.moazzam.jobautopilot;

import android.app.Activity;
import android.app.Dialog;
import android.widget.Button;
import android.widget.TextView;
import android.graphics.Color;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.os.Build;
import android.webkit.WebResourceError;
import android.webkit.WebResourceResponse;
import android.widget.LinearLayout;
import android.webkit.WebResourceRequest;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

public class MainActivity extends Activity {
    private WebView webView;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("job_autopilot", MODE_PRIVATE);
        webView = new WebView(this);
        setContentView(webView);
        applySystemInsets(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " JobAutopilot/1.0");

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(webView, true);

        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(new Bridge(), "Android");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return true; // Dashboard is local trusted content only.
            }
        });

        loadDashboard();
    }

    private void loadDashboard() {
        runOnUiThread(() -> webView.loadUrl("file:///android_asset/index.html"));
    }

    private void applySystemInsets(View root) {
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                                | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets.consumeSystemWindowInsets();
        });
        root.requestApplyInsets();
    }

    private void openLogin() {
        Dialog dialog = new Dialog(this, android.R.style.Theme_Material_Light_NoActionBar);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.WHITE);
        TextView status = new TextView(this);
        status.setText("Naukri login loading...");
        status.setTextColor(Color.DKGRAY);
        status.setPadding(16, 8, 16, 8);
        layout.addView(status);
        WebView login = new WebView(this);
        WebSettings settings = login.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(login, true);
        login.setWebChromeClient(new WebChromeClient());
        login.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                boolean blocked = !LoginNavigationPolicy.isAllowed(
                        request.getUrl().toString(), request.isForMainFrame());
                if (blocked && request.isForMainFrame()) {
                    status.setText("This link cannot open here. Use Naukri email or phone login.");
                }
                return blocked;
            }
            @Override
            public void onPageFinished(WebView view, String url) {
                status.setText("Complete Naukri login, then tap Save below.");
                CookieManager.getInstance().flush();
            }
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) status.setText("Page failed to load. Check connection and tap Reload.");
            }
            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame()) status.setText("Naukri returned HTTP " + response.getStatusCode() + ". Try again later.");
            }
        });
        // No JavaScript bridge or credentials are exposed to remote content.
        layout.addView(login, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout controls = new LinearLayout(this);
        Button reload = new Button(this);
        reload.setText("Reload");
        reload.setOnClickListener(v -> login.reload());
        controls.addView(reload, new LinearLayout.LayoutParams(0, -2, 1));
        Button save = new Button(this);
        save.setText("Save Login & Return");
        save.setOnClickListener(v -> {
            String url = login.getUrl();
            if (url == null || url.contains("/nlogin/") || url.contains("/login")) {
                status.setText("Complete login first. This is still the login page.");
                return;
            }
            String cookies = CookieManager.getInstance().getCookie("https://www.naukri.com/");
            if (cookies == null || cookies.isEmpty()) {
                status.setText("No session found. Complete login first.");
                return;
            }
            CookieManager.getInstance().flush();
            new Bridge().captureSession();
            dialog.dismiss();
        });
        controls.addView(save, new LinearLayout.LayoutParams(0, -2, 2));
        layout.addView(controls);
        dialog.setContentView(layout);
        dialog.setOnDismissListener(d -> login.destroy());
        dialog.show();
        dialog.getWindow().setLayout(-1, -1);
        dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        applySystemInsets(layout);
        login.loadUrl("https://www.naukri.com/nlogin/login");
    }

    @Override
    public void onBackPressed() {
        String url = webView.getUrl();
        if (url != null && !url.startsWith("file:///android_asset/")) {
            loadDashboard();
        } else if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public class Bridge {
        @JavascriptInterface
        public void openNaukriLogin() {
            runOnUiThread(() -> openLogin());
        }

        @JavascriptInterface
        public void captureSession() {
            String cookies = CookieManager.getInstance().getCookie("https://www.naukri.com/");
            if (cookies == null) cookies = "";
            prefs.edit().putString("naukri_cookies", cookies).apply();
            final String msg = cookies.isEmpty() ? "Login cookies nahi mile. Naukri me login karke phir Save Login dabao." : "Session saved. Backend verification is still required.";
            runOnUiThread(() -> {
                Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show();
                loadDashboard();
            });
        }

        @JavascriptInterface
        public String getNaukriCookies() {
            return prefs.getString("naukri_cookies", "");
        }

        @JavascriptInterface
        public void clearNaukriCookies() {
            prefs.edit().remove("naukri_cookies").apply();
            CookieManager.getInstance().removeAllCookies(null);
        }

        @JavascriptInterface
        public void backToDashboard() {
            loadDashboard();
        }

        @JavascriptInterface
        public void setPref(String key, String value) {
            prefs.edit().putString(key, value == null ? "" : value).apply();
        }

        @JavascriptInterface
        public String getPref(String key) {
            return prefs.getString(key, "");
        }

        @JavascriptInterface
        public void toast(String text) {
            runOnUiThread(() -> Toast.makeText(MainActivity.this, text, Toast.LENGTH_SHORT).show());
        }
    }
}
