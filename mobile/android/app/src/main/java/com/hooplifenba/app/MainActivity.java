package com.hooplifenba.app;

import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {

    // Streamlit chrome elementlerini gizleyen CSS'i enjekte et
    private void injectHideStreamlitCSS(WebView webView) {
        String js = "(function() {" +
            "if (document.getElementById('hooplife-native-hide')) return;" +
            "var s = document.createElement('style');" +
            "s.id = 'hooplife-native-hide';" +
            "s.textContent = '" +
            "[data-testid=\"stHeader\"]," +
            "[data-testid=\"stToolbar\"]," +
            "[data-testid=\"stDecoration\"]," +
            "[data-testid=\"stStatusWidget\"]," +
            "[data-testid=\"stBottom\"]," +
            "[data-testid=\"stFooter\"]," +
            "[data-testid=\"stMainMenu\"]," +
            "[data-testid=\"stRunningMan\"]," +
            "[data-testid=\"stAppRunningIndicator\"]," +
            "[data-testid=\"manage-app-button\"]," +
            "header, footer, #MainMenu," +
            ".stDeployButton, .stActionButton," +
            ".stApp > header," +
            "div[class*=\"viewerBadge\"]," +
            "a[href*=\"streamlit.io\"]," +
            "a[href*=\"github.com/streamlit\"] {" +
            "  display: none !important;" +
            "  visibility: hidden !important;" +
            "  height: 0 !important;" +
            "  overflow: hidden !important;" +
            "  opacity: 0 !important;" +
            "}';" +
            "if (document.head) { document.head.appendChild(s); }" +
            "else { document.addEventListener('DOMContentLoaded', function() { document.head.appendChild(s); }); }" +
            "})();";
        webView.evaluateJavascript(js, null);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Capacitor'ın varsayılan davranışı HTTPS URL'leri Chrome'da açar.
        // Bunu engellemek için özel bir WebViewClient kullanıyoruz.
        WebView webView = getBridge().getWebView();
        if (webView != null) {
            webView.setWebViewClient(new BridgeWebViewClient(getBridge()) {
                @Override
                public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                    super.onPageStarted(view, url, favicon);
                    // Streamlit sayfası yüklenmeye başlar başlamaz chrome gizleme CSS'i enjekte et
                    if (url != null && url.contains("streamlit")) {
                        injectHideStreamlitCSS(view);
                    }
                }

                @Override
                public void onPageFinished(WebView view, String url) {
                    super.onPageFinished(view, url);
                    // Sayfa yüklendikten sonra da CSS'i tekrar enjekte et (güvenlik için)
                    if (url != null && url.contains("streamlit")) {
                        injectHideStreamlitCSS(view);
                    }
                }

                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    String url = request.getUrl().toString();

                    // Streamlit ve uygulama URL'lerini WebView içinde tut
                    if (url.contains("streamlit.app") || url.contains("streamlit.io")) {
                        return false; // WebView'de kal
                    }

                    // Diğer tüm HTTP/HTTPS URL'lerini de WebView'de tut
                    if (url.startsWith("http://") || url.startsWith("https://")) {
                        return false;
                    }

                    // Özel şemalar (tel:, mailto: vb.) için sistem davranışı
                    return super.shouldOverrideUrlLoading(view, request);
                }

                @SuppressWarnings("deprecation")
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, String url) {
                    if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
                        return false;
                    }
                    return super.shouldOverrideUrlLoading(view, url);
                }
            });
        }
    }
}
