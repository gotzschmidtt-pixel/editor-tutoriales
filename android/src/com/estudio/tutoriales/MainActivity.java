package com.estudio.tutoriales;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * «Estudio» en el celular: abre la app del PC (la misma página que en el navegador) y la controla desde aquí.
 * El PC hace todo el trabajo. La primera vez pide la dirección que muestra «📲 Celular» en la app del PC
 * (la del Wi‑Fi de casa o la de Tailscale para datos móviles) y la recuerda. El PIN lo pide la propia app del PC.
 */
public class MainActivity extends Activity {
    private static final int ELEGIR_ARCHIVO = 1;
    private static final int FONDO = Color.rgb(6, 7, 12), ROSA = Color.rgb(255, 43, 214);

    private SharedPreferences prefs;
    private WebView web;
    private FrameLayout raiz;
    private View pantallaCompleta;
    private WebChromeClient.CustomViewCallback salirPantallaCompleta;
    private ValueCallback<Uri[]> archivos;

    @Override
    protected void onCreate(Bundle guardado) {
        super.onCreate(guardado);
        prefs = getSharedPreferences("estudio", MODE_PRIVATE);
        raiz = new FrameLayout(this);
        raiz.setBackgroundColor(FONDO);
        setContentView(raiz);
        String pc = prefs.getString("pc", "");
        if (pc.isEmpty()) pedirDireccion(null);
        else abrir(pc);
    }

    /** «192.168.1.20» → «http://192.168.1.20:8765». */
    static String normalizar(String s) {
        s = s.trim();
        if (s.isEmpty()) return s;
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
        Uri u = Uri.parse(s);
        if (u.getPort() == -1 && "http".equals(u.getScheme())) s = u.getScheme() + "://" + u.getHost() + ":8765" + (u.getPath() == null ? "" : u.getPath());
        return s.replaceAll("/+$", "");
    }

    private void pedirDireccion(String aviso) {
        if (web != null) { web.destroy(); web = null; }
        raiz.removeAllViews();
        LinearLayout caja = new LinearLayout(this);
        caja.setOrientation(LinearLayout.VERTICAL);
        caja.setGravity(Gravity.CENTER);
        int m = (int) (24 * getResources().getDisplayMetrics().density);
        caja.setPadding(m, m, m, m);

        TextView titulo = texto("📱 Estudio de tutoriales", 24);
        TextView ayuda = texto("Escribe la dirección de tu PC. La ves en la app del PC, botón «📲 Celular».\n\n"
                + "• En casa: la de «Wi‑Fi de casa» (192.168…)\n"
                + "• Con datos móviles: la de «Tailscale» (100.…), con Tailscale abierto en este celular", 15);
        EditText campo = new EditText(this);
        campo.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        campo.setHint("192.168.1.20:8765");
        campo.setText(prefs.getString("pc", ""));
        campo.setTextColor(Color.WHITE);
        campo.setHintTextColor(Color.GRAY);
        Button entrar = new Button(this);
        entrar.setText("Conectar");
        entrar.setBackgroundColor(ROSA);
        entrar.setTextColor(Color.WHITE);
        entrar.setOnClickListener(v -> {
            String pc = normalizar(campo.getText().toString());
            if (pc.isEmpty()) return;
            prefs.edit().putString("pc", pc).apply();
            abrir(pc);
        });
        caja.addView(titulo);
        caja.addView(ayuda);
        if (aviso != null) {
            TextView error = texto(aviso, 15);
            error.setTextColor(Color.rgb(255, 77, 109));
            caja.addView(error);
        }
        caja.addView(campo);
        caja.addView(entrar);
        raiz.addView(caja, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private TextView texto(String s, int tam) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(tam);
        t.setTextColor(Color.WHITE);
        t.setPadding(0, 0, 0, (int) (16 * getResources().getDisplayMetrics().density));
        return t;
    }

    private void abrir(String pc) {
        raiz.removeAllViews();
        web = new WebView(this);
        web.setBackgroundColor(FONDO);
        WebSettings w = web.getSettings();
        w.setJavaScriptEnabled(true);
        w.setDomStorageEnabled(true);
        w.setMediaPlaybackRequiresUserGesture(false);
        w.setSupportMultipleWindows(false);  // «Vista previa», «Pistas»… se abren aquí mismo; «atrás» vuelve
        w.setJavaScriptCanOpenWindowsAutomatically(true);
        w.setLoadWithOverviewMode(true);
        w.setUseWideViewPort(true);
        w.setBuiltInZoomControls(true);
        w.setDisplayZoomControls(false);
        CookieManager.getInstance().setAcceptCookie(true);  // el PIN queda recordado

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame())
                    pedirDireccion("No pude conectar con " + pc + ".\nRevisa que la app del PC esté abierta, con «📲 Celular» activado, "
                            + "y que estés en el mismo Wi‑Fi o con Tailscale encendido.");
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (Uri.parse(pc).getHost().equals(u.getHost())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u));  // enlaces de afuera (YouTube, consolas de IA…) en el navegador
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (archivos != null) archivos.onReceiveValue(null);
                archivos = cb;
                try {  // subir un video o una foto del celular, o grabar un video en el momento
                    Intent elegir = Intent.createChooser(p.createIntent(), "Subir al proyecto");
                    String tipos = android.text.TextUtils.join(",", p.getAcceptTypes());
                    java.util.List<Intent> camara = new java.util.ArrayList<>();
                    if (tipos.isEmpty() || tipos.contains("video") || tipos.contains("*"))
                        camara.add(new Intent(MediaStore.ACTION_VIDEO_CAPTURE));
                    elegir.putExtra(Intent.EXTRA_INITIAL_INTENTS, camara.toArray(new Intent[0]));
                    startActivityForResult(elegir, ELEGIR_ARCHIVO);
                } catch (Exception e) {
                    archivos = null;
                    return false;
                }
                return true;
            }

            @Override
            public void onShowCustomView(View vista, CustomViewCallback cb) {  // video a pantalla completa
                pantallaCompleta = vista;
                salirPantallaCompleta = cb;
                raiz.addView(vista, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            }

            @Override
            public void onHideCustomView() {
                if (pantallaCompleta != null) raiz.removeView(pantallaCompleta);
                pantallaCompleta = null;
            }
        });
        web.setDownloadListener((url, agente, disposicion, tipo, largo) -> {  // bajar el video terminado al celular
            DownloadManager.Request d = new DownloadManager.Request(Uri.parse(url));
            String nombre = URLUtil.guessFileName(url, disposicion, tipo);
            d.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
            d.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            d.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, nombre);
            ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(d);
            Toast.makeText(this, "Bajando " + nombre + " a Descargas", Toast.LENGTH_LONG).show();
        });
        raiz.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web.loadUrl(pc + "/");
    }

    @Override
    protected void onActivityResult(int pedido, int resultado, Intent datos) {
        if (pedido == ELEGIR_ARCHIVO && archivos != null) {
            archivos.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultado, datos));
            archivos = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (pantallaCompleta != null) {
            salirPantallaCompleta.onCustomViewHidden();
        } else if (web != null && web.canGoBack()) {
            web.goBack();
        } else if (web != null) {
            new AlertDialog.Builder(this)
                    .setTitle("Estudio")
                    .setItems(new String[]{"Cambiar la dirección del PC", "Recargar", "Salir"}, (d, i) -> {
                        if (i == 0) pedirDireccion(null);
                        else if (i == 1) web.reload();
                        else finish();
                    }).show();
        } else {
            super.onBackPressed();
        }
    }
}
