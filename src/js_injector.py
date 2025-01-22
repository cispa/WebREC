from mitmproxy import http
import base64
import os

from config import SCRIPT_PATH

# Usage: mitmdump -s "js_injector.py src"
# The JS Injector adds the configured script in the front of every HTML response
# aand additionally adds the script to iFrames.

base_dir = os.path.dirname(os.path.realpath(__file__))
SCRIPT = open(os.path.join(base_dir, SCRIPT_PATH), "r").read()
SCRIPT64 = base64.b64encode(SCRIPT.encode()).decode()

IFRAME_HOOK = """
// Hook into srcdoc
function hookSrcdoc() {
    const scriptToInject = '<scr' + 'ipt>eval(atob("%s"))</scr' + 'ipt>';
    const originalSrcdoc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'srcdoc');

    Object.defineProperty(HTMLIFrameElement.prototype, 'srcdoc', {
        enumerable: originalSrcdoc.enumerable,
        configurable: true,

        get: function() {
            return originalSrcdoc.get.call(this);
        },

        set: function(value) {
            const newValue = scriptToInject + value;
            originalSrcdoc.set.call(this, newValue);
        }
    });
}

// Hook into appendChild for iframes

function hookAppendChild() {
    const originalAppendChild = Node.prototype.appendChild;
    Node.prototype.appendChild = function(child) {
        if (child.tagName === 'IFRAME') {            
            const existingOnload = child.onload;
            child.onload = () => {
                if (child.contentWindow.location.href == 'about:blank') {
                    const script = document.createElement('script');
                    script.textContent = 'eval(atob("%s"))';
                    try {
                        if (child.contentDocument) {
                            child.contentDocument.head.insertBefore(script, child.contentDocument.head.firstChild);
                        }
                    } catch (e) {
                        console.error("Error accessing iframe contents:", e);
                    }
                }
                if (existingOnload) {
                    existingOnload.call(child);
                }
            };
        }
        return originalAppendChild.call(this, child);
    };
}

hookSrcdoc();
hookAppendChild();
""" % (SCRIPT64, SCRIPT64)

def response(flow: http.HTTPFlow) -> None:
    if "content-type" not in flow.response.headers:
        return

    if 'text/html' in flow.response.headers["content-type"]:
        html = flow.response.content
        script = f"<script type='application/javascript'>{SCRIPT} {IFRAME_HOOK}</script>"
        flow.response.content = script.encode() + html