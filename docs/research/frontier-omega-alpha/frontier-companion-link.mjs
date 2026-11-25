const companionOrigin = 'http://127.0.0.1:38463';
const hex = bytes => Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');

// Open from an explicit user interaction. The grant and the tab's proof stay
// out of navigation, URL history, shared document storage, and public services.
export function connectCompanion(language, signal) {
  if (signal?.aborted) return Promise.resolve(null);
  const route = language === 'fr' ? 'fr' : 'en';
  const popup = window.open(`${companionOrigin}/frontier-connect?lang=${route}`, '_blank',
    'popup,width=560,height=520');
  if (!popup) return Promise.resolve(null);

  const channel = new MessageChannel();
  const proof = hex(crypto.getRandomValues(new Uint8Array(32)));
  return new Promise(resolve => {
    let finished = false;
    const openDeadline = setTimeout(abort, 12000);
    const checkWindow = setInterval(() => { if (popup.closed) abort(); }, 350);

    function finish(result) {
      if (finished) return;
      finished = true;
      clearTimeout(openDeadline);
      clearInterval(checkWindow);
      window.removeEventListener('message', ready);
      signal?.removeEventListener('abort', abort);
      channel.port1.close();
      channel.port2.close();
      popup.close();
      resolve(result);
    }

    function abort() { finish(null); }

    async function ready(event) {
      if (event.source !== popup || event.origin !== companionOrigin || event.data?.type !== 'frontier-pair-ready') return;
      window.removeEventListener('message', ready);
      try {
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(proof));
        if (finished) return;
        popup.postMessage({type: 'frontier-pair-request', proof: hex(new Uint8Array(digest))}, companionOrigin, [channel.port2]);
        clearTimeout(openDeadline);
      } catch {
        abort();
      }
    }

    channel.port1.onmessage = ({data}) => {
      if (typeof data?.approval === 'string' && /^[A-Za-z0-9_-]{43}$/.test(data.approval)) {
        return finish({approval: data.approval, proof});
      }
      abort();
    };
    channel.port1.onmessageerror = abort;
    window.addEventListener('message', ready);
    signal?.addEventListener('abort', abort, {once: true});
  });
}
