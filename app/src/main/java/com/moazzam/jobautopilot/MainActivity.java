package com.moazzam.jobautopilot;

import android.app.Activity;
import android.app.Dialog;
import android.widget.Button;
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

    private void openLogin() {
        Dialog dialog = new Dialog(this, android.R.style.Theme_Material_Light_NoActionBar);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        WebView login = new WebView(this);
        login.getSettings().setJavaScriptEnabled(true);
        login.getSettings().setDomStorageEnabled(true);
        login.getSettings().setAllowFileAccess(false);
        login.getSettings().setAllowContentAccess(false);
        login.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                android.net.Uri uri = request.getUrl();
                String host = uri.getHost();
                return !"https".equals(uri.getScheme()) || host == null ||
                        !(host.equals("naukri.com") || host.endsWith(".naukri.com"));
            }
        });
        // Never expose the dashboard JavaScript bridge to remote login pages.
        layout.addView(login, new LinearLayout.LayoutParams(-1, 0, 1));
        Button save = new Button(this);
        save.setText("Save Login & Return");
        save.setOnClickListener(v -> {
            new Bridge().captureSession();
            CookieManager.getInstance().flush();
            dialog.dismiss();
        });
        layout.addView(save);
        dialog.setContentView(layout);
        dialog.setOnDismissListener(d -> login.destroy());
        dialog.show();
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
            final String msg = cookies.isEmpty() ? "Login cookies nahi mile. Naukri me login karke phir Save Login dabao." : "Naukri login session saved.";
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
