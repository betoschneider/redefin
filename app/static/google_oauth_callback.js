// Callback do Google OAuth: repassa o authorization code e o state ao popup
// original via postMessage. Arquivo separado (e não inline) para a CSP
// `script-src 'self'` funcionar sem 'unsafe-inline'.
(function () {
  try {
    // Extrai o authorization code da query string (?code=...)
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    if (window.opener && code) {
      window.opener.postMessage(
        { type: 'google-auth-code', code: code, state: state },
        window.location.origin
      );
    }
  } catch (e) {
    console.error('callback error', e);
  }
  // Fecha o popup
  try { window.close(); } catch (e) {}
})();
