package com.hooplifenba.app;

import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Capacitor'ın varsayılan davranışı HTTPS URL'leri Chrome'da açar.
        // Bunu engellemek için özel bir WebViewClient kullanıyoruz.
        WebView webView = getBridge().getWebView();
        if (webView != null) {
            webView.setWebViewClient(new BridgeWebViewClient(getBridge()) {
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
